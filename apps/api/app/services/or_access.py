"""Presenter sessions: opaque server-side hashes, explicit origin and CSRF checks."""

import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa
from fastapi import Request, Response

from app.models.or_records import PresenterSession

SESSION_COOKIE = "pp_presenter"
CSRF_COOKIE = "pp_csrf"


class AccessError(ValueError):
    def __init__(self, code: str, status: int):
        super().__init__(code)
        self.code, self.status = code, status


@dataclass(frozen=True)
class Presenter:
    organization_id: UUID
    actor_id: UUID
    session_id: UUID
    csrf_hash: str


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def allowed_origins() -> set[str]:
    return {
        x.strip().rstrip("/")
        for x in os.environ.get("PP_ALLOWED_ORIGINS", "").split(",")
        if x.strip()
    }


def require_origin(request: Request) -> None:
    # OR-DEC-014 [PROVISIONAL]: direct backend mutations enforce the same origin gate.
    origin = request.headers.get("origin")
    forwarded = request.headers.get("x-forwarded-origin")
    if forwarded is not None:
        trusted = os.environ.get("PP_TRUSTED_PROXY_TOKEN", "")
        supplied = request.headers.get("x-pp-proxy-token", "")
        if not trusted or not hmac.compare_digest(trusted, supplied):
            raise AccessError("PROXY_FORBIDDEN", 403)
        origin = forwarded
    if origin is None or origin.rstrip("/") not in allowed_origins():
        raise AccessError("ORIGIN_FORBIDDEN", 403)


def verify_password(password: str, encoded: str) -> bool:
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
    """Bounded local-demo login limiter; not tied to supervisor availability."""

    def __init__(self):
        self._entries = defaultdict(deque)
        self._lock = threading.Lock()

    def consume(self, address: str) -> None:
        now = time.monotonic()
        with self._lock:
            for key in tuple(self._entries):
                while self._entries[key] and self._entries[key][0] <= now - 60:
                    self._entries[key].popleft()
                if not self._entries[key]:
                    del self._entries[key]
            attempts = self._entries[address]
            if len(attempts) >= 5:
                raise AccessError("LOGIN_RATE_LIMITED", 429)
            if len(self._entries) > 4096:
                raise AccessError("LOGIN_RATE_LIMITED", 429)
            attempts.append(now)


def login(request: Request, response: Response, runtime, username: str, password: str) -> dict:
    require_origin(request)
    limiter = getattr(request.app.state, "or_login_limiter", None)
    if limiter is None:
        limiter = request.app.state.or_login_limiter = LoginLimiter()
    limiter.consume(request.client.host if request.client else "unknown")
    expected_user = os.environ.get("PP_PRESENTER_USERNAME")
    encoded = os.environ.get("PP_PRESENTER_PASSWORD_HASH")
    organization = os.environ.get("PP_PRESENTER_ORGANIZATION_ID")
    if not expected_user or not encoded or not organization:
        raise AccessError("PRESENTER_UNAVAILABLE", 503)
    correct_password = verify_password(password, encoded)
    if (
        not hmac.compare_digest(username.encode("utf-8"), expected_user.encode("utf-8"))
        or not correct_password
    ):
        raise AccessError("INVALID_CREDENTIALS", 401)
    org = UUID(organization)
    actor = uuid5(org, username)
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with runtime.engine.begin() as conn:
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
    secure = os.environ.get("PP_COOKIE_SECURE", "true").lower() != "false"
    if not secure and request.url.hostname not in {"localhost", "127.0.0.1", "testserver"}:
        raise AccessError("INSECURE_COOKIE_CONFIGURATION", 503)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=8 * 3600,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=8 * 3600,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )
    return {
        "actor_id": actor,
        "organization_id": org,
        "csrf_token": csrf,
        "expires_in_seconds": 8 * 3600,
    }


def authenticate(
    request: Request, runtime, *, required: bool = True, mutation: bool = False
) -> Presenter | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        if required:
            raise AccessError("PRESENTER_REQUIRED", 401)
        return None
    with runtime.engine.connect() as conn:
        now = conn.scalar(sa.text("SELECT clock_timestamp()"))
        row = (
            conn.execute(
                sa.select(PresenterSession.__table__).where(
                    PresenterSession.token_hash == token_hash(token),
                    PresenterSession.revoked_at.is_(None),
                    PresenterSession.expires_at > now,
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        if required:
            raise AccessError("PRESENTER_REQUIRED", 401)
        return None
    presenter = Presenter(
        row["organization_id"], UUID(row["actor_id"]), row["id"], row["csrf_hash"]
    )
    if mutation:
        require_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(token_hash(supplied), presenter.csrf_hash):
            raise AccessError("CSRF_FORBIDDEN", 403)
    return presenter


def logout(request: Request, response: Response, runtime) -> dict:
    presenter = authenticate(request, runtime, mutation=True)
    with runtime.engine.begin() as conn:
        conn.execute(
            sa.update(PresenterSession)
            .where(PresenterSession.id == presenter.session_id)
            .values(revoked_at=sa.func.clock_timestamp())
        )
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"logged_out": True}
