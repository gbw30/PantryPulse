"""Presenter sessions following the existing OR branch's provisional cookie convention.

Server configuration fixes the tenant/actor. Neither request JSON nor forwarded
tenant headers can select them. Store opaque-token hashes, never passwords/tokens.
"""

import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa

from app.models.forecasts import PresenterSession
from app.repositories.jobs import TrustedScope

SESSION_COOKIE = "pp_presenter"
CSRF_COOKIE = "pp_csrf"


class AccessError(ValueError):
    def __init__(self, code, status):
        super().__init__(code)
        self.code, self.status = code, status


def token_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_origin(request):
    origin = request.headers.get("origin")
    forwarded = request.headers.get("x-forwarded-origin")
    if forwarded is not None:
        secret = os.environ.get("PP_TRUSTED_PROXY_TOKEN", "")
        supplied = request.headers.get("x-pp-proxy-token", "")
        if not secret or not hmac.compare_digest(secret, supplied):
            raise AccessError("PROXY_FORBIDDEN", 403)
        origin = forwarded
    allowed = {
        v.strip().rstrip("/")
        for v in os.environ.get("PP_ALLOWED_ORIGINS", "").split(",")
        if v.strip()
    }
    if origin is None or origin.rstrip("/") not in allowed:
        raise AccessError("ORIGIN_FORBIDDEN", 403)


def verify_password(password, encoded):
    try:
        algorithm, n, r, p, salt, digest = encoded.split("$")
        if (algorithm, n, r, p) != ("scrypt", "16384", "8", "1"):
            return False
        salt_bytes, expected = bytes.fromhex(salt), bytes.fromhex(digest)
        if len(salt_bytes) < 16 or len(expected) != 64:
            return False
        actual = hashlib.scrypt(password.encode(), salt=salt_bytes, n=16384, r=8, p=1, dklen=64)
        return hmac.compare_digest(actual, expected)
    except (ValueError, MemoryError):
        return False


class LoginLimiter:
    def __init__(self):
        self.entries = defaultdict(deque)
        self.lock = threading.Lock()

    def consume(self, address):
        now = time.monotonic()
        with self.lock:
            for key in tuple(self.entries):
                while self.entries[key] and self.entries[key][0] <= now - 60:
                    self.entries[key].popleft()
                if not self.entries[key]:
                    del self.entries[key]
            if len(self.entries) >= 4096 or len(self.entries[address]) >= 5:
                raise AccessError("LOGIN_RATE_LIMITED", 429)
            self.entries[address].append(now)


def login(request, response, runtime, credentials):
    require_origin(request)
    request.app.state.login_limiter.consume(request.client.host if request.client else "unknown")
    username = os.environ.get("PP_PRESENTER_USERNAME", "")
    password_hash = os.environ.get("PP_PRESENTER_PASSWORD_HASH", "")
    organization = os.environ.get("PP_PRESENTER_ORGANIZATION_ID", "")
    secure = os.environ.get("PP_COOKIE_SECURE", "true").lower() != "false"
    if not secure and request.url.hostname not in {"localhost", "127.0.0.1", "testserver"}:
        raise AccessError("INSECURE_COOKIE_CONFIGURATION", 503)
    if not username or not password_hash or not organization:
        raise AccessError("PRESENTER_UNAVAILABLE", 503)
    valid_password = verify_password(credentials.password, password_hash)
    if (
        not hmac.compare_digest(username.encode(), credentials.username.encode())
        or not valid_password
    ):
        raise AccessError("INVALID_CREDENTIALS", 401)
    org = UUID(organization)
    actor = uuid5(org, username)
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with runtime.engine.begin() as conn:
        exists = conn.scalar(sa.text("SELECT 1 FROM organizations WHERE id = :o"), {"o": org})
        if not exists:
            raise AccessError("PRESENTER_UNAVAILABLE", 503)
        now = conn.scalar(sa.text("SELECT clock_timestamp()"))
        conn.execute(
            sa.insert(PresenterSession).values(
                id=uuid4(),
                organization_id=org,
                actor_id=str(actor),
                token_hash=token_hash(token),
                csrf_hash=token_hash(csrf),
                expires_at=now + timedelta(hours=8),
            )
        )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=28800,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite="strict", max_age=28800, path="/"
    )
    return dict(actor_id=actor, organization_id=org, csrf_token=csrf, expires_in_seconds=28800)


def authenticate(request, runtime, *, mutation=False):
    token = request.cookies.get(SESSION_COOKIE)
    if not token or len(token) > 128:
        raise AccessError("PRESENTER_REQUIRED", 401)
    with runtime.engine.connect() as conn:
        row = (
            conn.execute(
                sa.select(PresenterSession.__table__).where(
                    PresenterSession.token_hash == token_hash(token),
                    PresenterSession.revoked_at.is_(None),
                    PresenterSession.expires_at > sa.func.clock_timestamp(),
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise AccessError("PRESENTER_REQUIRED", 401)
    if mutation:
        require_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(token_hash(supplied), row["csrf_hash"]):
            raise AccessError("CSRF_FORBIDDEN", 403)
    return TrustedScope(row["organization_id"], row["actor_id"])


VISITOR_ACTOR = "visitor:read-only"


def read_scope(request, runtime):
    """GET-only reads: the presenter session when present, else the opt-in read-only visitor.

    PP_VISITOR_ORGANIZATION_ID (user decision 2026-10-25) lets visitors see saved Overview data for
    one demo organization. Unset means presenter-only, as before. It never applies to mutations.
    """
    try:
        return authenticate(request, runtime, mutation=False)
    except AccessError as error:
        visitor = os.environ.get("PP_VISITOR_ORGANIZATION_ID", "").strip()
        if error.code != "PRESENTER_REQUIRED" or not visitor:
            raise
        try:
            organization = UUID(visitor)
        except ValueError:
            raise AccessError("VISITOR_ACCESS_MISCONFIGURED", 503) from None
        return TrustedScope(organization, VISITOR_ACTOR)


def logout(request, response, runtime):
    authenticate(request, runtime, mutation=True)
    with runtime.engine.begin() as conn:
        conn.execute(
            sa.update(PresenterSession)
            .where(PresenterSession.token_hash == token_hash(request.cookies[SESSION_COOKIE]))
            .values(revoked_at=sa.func.clock_timestamp())
        )
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"revoked": True}
