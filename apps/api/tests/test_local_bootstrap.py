# covers: V1-A04, V1-A05
"""W0-05: generated local login, shared proxy token and seed skeleton (isolated PostgreSQL)."""

import logging
import stat
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app
from app.repositories.jobs import QueueRepository, create_queue_engine
from app.services import samples
from app.services.forecast_runtime import ForecastRuntime
from app.services.jobs.contracts import PRODUCTION_PROFILE
from app.services.presenter_access import AccessError, require_origin, verify_password
from app.workers.registries import load_registry
from scripts import local_bootstrap, seed_local
from tests.integration.wq_support import alembic_config, database_url, reset_schema

pytestmark = pytest.mark.integration

SCHEMA = "v1_bootstrap_test"
TODAY = date(2026, 11, 4)
LINE = "Open http://127.0.0.1:{port} — username: local — password: see .pantrypulse/local-login.txt"


@pytest.fixture(scope="module")
def engine():
    url = database_url()
    reset_schema(url, SCHEMA)
    eng = create_queue_engine(url, schema=SCHEMA)
    with eng.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    yield eng
    eng.dispose()
    reset_schema(url, SCHEMA)


@pytest.fixture
def db(engine):
    with engine.begin() as conn:
        conn.execute(sa.text("TRUNCATE local_logins, organizations CASCADE"))
    return engine


@pytest.fixture
def paths(tmp_path):
    return dict(login_file=tmp_path / "host" / "local-login.txt",
                token_file=tmp_path / "shared" / "proxy-token")


def run(engine, paths):
    return local_bootstrap.run(engine, today=TODAY, web_port="3000", **paths)


def file_password(path):
    lines = dict(line.split(": ", 1) for line in path.read_text().splitlines())
    assert lines["username"] == "local"
    return lines["password"]


def stored_hash(engine):
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT username, password_hash FROM local_logins")).all()


def test_first_run_generates_credentials_once(db, paths, capsys):
    run(db, paths)
    login = paths["login_file"]
    assert stat.S_IMODE(login.stat().st_mode) == 0o600
    password = file_password(login)
    assert len(password) >= 20
    [(username, hashed)] = stored_hash(db)
    assert username == "local" and hashed.startswith("scrypt$") and password not in hashed
    assert verify_password(password, hashed)

    text = login.read_text()
    run(db, paths)
    assert login.read_text() == text
    assert stored_hash(db) == [("local", hashed)]


def test_matching_login_file_gets_its_mode_restored(db, paths):
    # A restore or manual chmod must not leave the plaintext password readable on the next start.
    run(db, paths)
    paths["login_file"].chmod(0o644)
    text = paths["login_file"].read_text()
    run(db, paths)
    assert stat.S_IMODE(paths["login_file"].stat().st_mode) == 0o600
    assert paths["login_file"].read_text() == text


def test_login_file_rewritten_when_database_was_reset(db, paths):
    # `docker compose down -v` drops the database but keeps the host file: the file must not
    # keep showing a password the new install never stored.
    run(db, paths)
    old = file_password(paths["login_file"])
    with db.begin() as conn:
        conn.execute(sa.text("DELETE FROM local_logins"))
    run(db, paths)
    new = file_password(paths["login_file"])
    [(_, hashed)] = stored_hash(db)
    assert new != old and verify_password(new, hashed)


def test_password_never_logged(db, paths, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    run(db, paths)
    password = file_password(paths["login_file"])
    token = paths["token_file"].read_text().strip()
    out, err = capsys.readouterr()
    for secret in (password, token):
        assert secret not in caplog.text
        assert secret not in out + err


def test_proxy_token_generated_and_shared_without_shell(db, paths, monkeypatch):
    run(db, paths)
    token_file = paths["token_file"]
    token = token_file.read_text().strip()
    assert len(token) >= 32
    run(db, paths)
    assert token_file.read_text().strip() == token

    # The backend reads the same file; no environment variable carries the token.
    monkeypatch.delenv("PP_TRUSTED_PROXY_TOKEN", raising=False)
    monkeypatch.setenv("PP_TRUSTED_PROXY_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("PP_ALLOWED_ORIGINS", "http://127.0.0.1:3000")

    def forwarded(supplied):
        return SimpleNamespace(headers={"origin": "http://web:3000",
                                        "x-forwarded-origin": "http://127.0.0.1:3000",
                                        "x-pp-proxy-token": supplied})

    require_origin(forwarded(token))
    with pytest.raises(AccessError):
        require_origin(forwarded(token + "x"))


def test_hash_with_dollar_round_trips(db, paths, monkeypatch):
    run(db, paths)
    [(_, hashed)] = stored_hash(db)
    assert "$" in hashed
    # Presenter login reads the hash from local_logins when the environment has none.
    monkeypatch.delenv("PP_PRESENTER_PASSWORD_HASH", raising=False)
    for key, value in dict(PP_PRESENTER_USERNAME="local",
                           PP_PRESENTER_ORGANIZATION_ID=str(seed_local.LOCAL_ORGANIZATION_ID),
                           PP_COOKIE_SECURE="false",
                           PP_ALLOWED_ORIGINS="http://testserver").items():
        monkeypatch.setenv(key, value)
    queue = QueueRepository(db, registry=load_registry("production"), profile=PRODUCTION_PROFILE)
    with TestClient(create_app(ForecastRuntime(db, queue))) as client:
        def login(password):
            return client.post("/api/v1/presenter/login", headers={"Origin": "http://testserver"},
                               json=dict(username="local", password=password))

        assert login("wrong-password").status_code == 401
        response = login(file_password(paths["login_file"]))
        assert response.status_code == 200, response.text
        assert response.json()["organization_id"] == str(seed_local.LOCAL_ORGANIZATION_ID)


@pytest.mark.parametrize(("env", "port"), [(None, "3000"), ("3555", "3555")])
def test_startup_line(db, paths, monkeypatch, capsys, env, port):
    if env is None:
        monkeypatch.delenv("PP_WEB_PORT", raising=False)
    else:
        monkeypatch.setenv("PP_WEB_PORT", env)
    assert local_bootstrap.startup_line() == LINE.format(port=port)
    local_bootstrap.run(db, today=TODAY, web_port=local_bootstrap.web_port(), **paths)
    assert capsys.readouterr().out.splitlines()[-1] == LINE.format(port=port)


def test_seed_calls_ensure_samples_and_never_resets(db, paths, monkeypatch):
    sentinel = "11111111-2222-4333-8444-555555555555"
    with db.begin() as conn:
        conn.execute(sa.text("INSERT INTO organizations (id, name, is_demo) "
                             "VALUES (:id, 'user network', false)"), {"id": sentinel})
    calls = []

    def fake(session, today):
        assert isinstance(session, Session)
        calls.append(today)
        return samples.SeedReport(loaded=())

    monkeypatch.setattr(samples, "ensure_samples", fake)
    run(db, paths)
    run(db, paths)
    assert calls == [TODAY, TODAY]
    with db.connect() as conn:
        ids = {str(i) for i in conn.scalars(sa.text("SELECT id FROM organizations"))}
    assert ids == {sentinel, str(seed_local.LOCAL_ORGANIZATION_ID)}
    for module in (local_bootstrap, seed_local):
        source = open(module.__file__, encoding="utf-8").read().upper()
        assert not any(word in source for word in ("DELETE ", "TRUNCATE", "DROP "))


def test_login_through_compose_proxy_on_loopback(db, paths, monkeypatch):
    # In compose the API is reached as http://api:8000; the browser is on 127.0.0.1. The
    # insecure-cookie guard must judge the verified browser origin, not the internal host.
    run(db, paths)
    monkeypatch.delenv("PP_PRESENTER_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("PP_TRUSTED_PROXY_TOKEN", raising=False)
    for key, value in dict(PP_PRESENTER_USERNAME="local",
                           PP_PRESENTER_ORGANIZATION_ID=str(seed_local.LOCAL_ORGANIZATION_ID),
                           PP_COOKIE_SECURE="false",
                           PP_TRUSTED_PROXY_TOKEN_FILE=str(paths["token_file"]),
                           PP_ALLOWED_ORIGINS="http://127.0.0.1:3000,http://pantry.example").items():
        monkeypatch.setenv(key, value)
    token = paths["token_file"].read_text().strip()
    password = file_password(paths["login_file"])
    queue = QueueRepository(db, registry=load_registry("production"), profile=PRODUCTION_PROFILE)
    app = create_app(ForecastRuntime(db, queue))
    with TestClient(app, base_url="http://api:8000") as client:
        def login(browser_origin):
            return client.post("/api/v1/presenter/login", json=dict(username="local",
                               password=password), headers={"X-Forwarded-Origin": browser_origin,
                                                            "X-PP-Proxy-Token": token})

        assert login("http://127.0.0.1:3000").status_code == 200
        # A non-loopback browser origin still never gets a non-Secure cookie.
        refused = login("http://pantry.example")
        assert refused.status_code == 503
        assert refused.json()["error"]["code"] == "INSECURE_COOKIE_CONFIGURATION"


def test_seed_date_is_the_samples_new_york_date():
    # CR-w3-samples-4 (a): at 02:00 UTC on Nov 10 it is still Nov 9 in New York.
    assert local_bootstrap.seed_today(datetime(2026, 11, 10, 2, tzinfo=UTC)) == date(2026, 11, 9)
    assert local_bootstrap.seed_today(datetime(2026, 11, 10, 12, tzinfo=UTC)) == date(2026, 11, 10)


def test_seed_runs_after_the_login_commits(db, paths, monkeypatch):
    # CR-w3-samples-4 (b): the seed has its own transaction, started after the login committed.
    seen = []

    def fake(session, today):
        with db.connect() as conn:
            seen.append(conn.scalar(sa.text("SELECT count(*) FROM local_logins")))
        return samples.SeedReport(loaded=())

    monkeypatch.setattr(samples, "ensure_samples", fake)
    run(db, paths)
    assert seen == [1]
