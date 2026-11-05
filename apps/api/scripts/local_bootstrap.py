"""Local install start-up, run by the compose `seed` service on every `docker compose up`.

- Generates the local login once: the password goes only to a 0600 file on the host
  (`.pantrypulse/local-login.txt`), the database keeps only its scrypt hash (`local_logins`).
  If the file and the stored hash no longer match (e.g. after `docker compose down -v`), both
  are regenerated so the file never shows a password the install does not accept.
- Generates the trusted proxy token once, into a file on the volume shared with `api` and `web`.
  It never passes through a shell, an environment variable or the logs.
- Seeds the local organization and the sample networks. Never resets or deletes data.
"""

import os
import secrets
import sys
from datetime import date
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.database import database_engine  # noqa: E402
from app.models.networks import local_logins  # noqa: E402
from app.services.presenter_access import hash_password, verify_password  # noqa: E402
from scripts import seed_local  # noqa: E402

USERNAME = "local"


def web_port() -> str:
    return os.environ.get("PP_WEB_PORT") or "3000"


def startup_line(port: str | None = None) -> str:
    return (f"Open http://127.0.0.1:{port or web_port()} — username: {USERNAME} — "
            "password: see .pantrypulse/local-login.txt")


def _write_file(path: Path, text: str, mode: int) -> None:
    """Atomically replace `path` with `text`, created with `mode` and never wider."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.unlink(missing_ok=True)
    with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode), "w",
                   encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(tmp, mode)
    owner = path.parent.stat()
    if os.geteuid() == 0 and owner.st_uid != 0:
        # The seed runs as root; on a Linux bind mount, give the file to the folder's owner.
        try:
            os.chown(tmp, owner.st_uid, owner.st_gid)
        except OSError:
            pass  # Bind mounts that do not support ownership (Docker Desktop) keep the default.
    os.replace(tmp, path)


def _file_password(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    fields = dict(line.split(": ", 1) for line in lines if ": " in line)
    return fields.get("password") if fields.get("username") == USERNAME else None


def ensure_login(session, login_file: Path) -> bool:
    """Make the host file and the stored hash agree; return True when a password was generated."""
    stored = session.scalar(
        sa.select(local_logins.c.password_hash).where(local_logins.c.username == USERNAME)
    )
    current = _file_password(login_file)
    if stored and current and verify_password(current, stored):
        return False
    password = secrets.token_urlsafe(18)
    hashed = hash_password(password)
    _write_file(login_file, f"username: {USERNAME}\npassword: {password}\n", 0o600)
    session.execute(
        insert(local_logins)
        .values(username=USERNAME, password_hash=hashed)
        .on_conflict_do_update(index_elements=["username"], set_={"password_hash": hashed})
    )
    return True


def ensure_proxy_token(token_file: Path) -> bool:
    """Create the proxy token once; return True when it was created."""
    try:
        if token_file.read_text(encoding="utf-8").strip():
            return False
    except FileNotFoundError:
        pass
    # 0644: the web server runs as a non-root user. The volume is mounted only into seed,
    # api and web, never on the host.
    _write_file(token_file, secrets.token_urlsafe(32) + "\n", 0o644)
    return True


def run(engine, *, login_file: Path, token_file: Path, web_port: str, today: date) -> None:
    with Session(engine) as session, session.begin():
        login_created = ensure_login(session, login_file)
        summary = seed_local.seed(session, today)
    token_created = ensure_proxy_token(token_file)
    print(f"Local login {'generated' if login_created else 'unchanged'}.")
    print(f"Proxy token {'generated' if token_created else 'unchanged'}.")
    print(summary)
    print(startup_line(web_port), flush=True)


def main() -> int:
    missing = [name for name in ("DATABASE_URL", "PP_LOCAL_LOGIN_FILE",
                                 "PP_TRUSTED_PROXY_TOKEN_FILE") if not os.environ.get(name)]
    if missing:
        print(f"Missing required settings: {', '.join(missing)}.", file=sys.stderr)
        return 1
    engine = database_engine(os.environ["DATABASE_URL"])
    try:
        run(engine, login_file=Path(os.environ["PP_LOCAL_LOGIN_FILE"]),
            token_file=Path(os.environ["PP_TRUSTED_PROXY_TOKEN_FILE"]),
            web_port=web_port(), today=date.today())
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
