"""Run real browser tests on a fresh local PostgreSQL schema with disposable auth."""

import argparse
import hashlib
import os
import re
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.repositories.jobs import create_queue_engine

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-port", type=int, default=8012)
    parser.add_argument("--web-port", type=int, default=3012)
    args = parser.parse_args(argv)
    if not all(1024 <= port <= 65535 for port in (args.api_port, args.web_port)):
        parser.error("Choose unprivileged local ports")
    url = os.environ.get("PP_TEST_DATABASE_URL", "")
    try:
        parsed = sa.engine.make_url(url)
        valid = (
            parsed.drivername.startswith("postgresql")
            and parsed.host in {"localhost", "127.0.0.1", "::1"}
            and bool(parsed.database)
            and parsed.database.endswith("_test")
        )
    except sa.exc.ArgumentError:
        valid = False
    if not valid:
        parser.error("PP_TEST_DATABASE_URL must name a dedicated local PostgreSQL *_test database")
    schema = "or_e2e_" + uuid4().hex
    assert re.fullmatch(r"or_e2e_[a-f0-9]{32}", schema)
    logs = ROOT / "artifacts/or/browser"
    logs.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(24)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=64)
    env = {
        **os.environ,
        "DATABASE_URL": url,
        "PP_OR_SCHEMA": schema,
        "PP_PRESENTER_USERNAME": "presenter",
        "PP_PRESENTER_ORGANIZATION_ID": str(uuid4()),
        "PP_PRESENTER_PASSWORD_HASH": f"scrypt$16384$8$1${salt.hex()}${digest.hex()}",
        "OR_E2E_PASSWORD": password,
        "PP_COOKIE_SECURE": "false",
        "PP_ALLOWED_ORIGINS": f"http://127.0.0.1:{args.web_port}",
        "PP_API_BASE_URL": f"http://127.0.0.1:{args.api_port}",
        "PLAYWRIGHT_PORT": str(args.web_port),
    }
    raw = sa.create_engine(url)
    created = False
    processes, streams = [], []
    try:
        with raw.begin() as connection:
            assert connection.scalar(sa.text("SELECT current_database()")).endswith("_test")
            connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_queue_engine(url, schema=schema)
        try:
            with engine.begin() as connection:
                config = Config(str(API / "alembic.ini"))
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
        finally:
            engine.dispose()
        for name, parameters in (
            (
                "api",
                ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.api_port)],
            ),
            (
                "supervisor",
                ["scripts.or_supervisor", "--registry", "production", "--schema", schema],
            ),
        ):
            stream = (logs / f"{name}.log").open("w")
            streams.append(stream)
            processes.append(
                subprocess.Popen(
                    [sys.executable, "-m", *parameters],
                    cwd=API,
                    env=env,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
        with httpx.Client(base_url=env["PP_API_BASE_URL"], timeout=2) as client:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError("Isolated backend exited; inspect artifacts/or/browser logs")
                try:
                    response = client.get("/api/v1/readiness")
                    if response.is_success and response.json()["compute_available"]:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Isolated backend did not become ready")
        print("Isolated API/PostgreSQL/shared supervisor ready; starting real browser suite.")
        return subprocess.run(
            ["npm", "run", "test:e2e", "--workspace", "@pantrypulse/web", "--", "--workers=1"],
            cwd=ROOT,
            env=env,
            check=False,
        ).returncode
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
        for stream in streams:
            stream.close()
        if created:
            with raw.begin() as connection:
                connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        raw.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
