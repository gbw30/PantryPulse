"""Real PostgreSQL HTTP/security and persisted native-solver journey.

The journey starts the production supervisor and real terminable method children.
No synthetic provider or fake queue result is labeled a solver/API integration pass.
"""

import hashlib
import os
import select
import signal
import subprocess
import sys
import time
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from fastapi.testclient import TestClient
from wq_support import API_ROOT, alembic_config, database_url

from app.main import app
from app.models.or_records import DatasetState, InputPackageRecord, PlanRecord
from app.repositories.jobs import QueueRepository, create_queue_engine
from app.services.jobs.contracts import RuntimeProfile
from app.services.or_runtime import ORRuntime
from app.workers.registries import load_registry

pytestmark = pytest.mark.integration
ORIGIN = "http://testserver"
PASSWORD = "test-only-presenter-password"
ORG = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def http(monkeypatch):
    url = database_url()
    schema = "or_http_" + uuid4().hex[:16]
    raw = sa.create_engine(url)
    with raw.begin() as conn:
        assert conn.scalar(sa.text("SELECT current_database()")).endswith("_test")
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = create_queue_engine(url, schema=schema)
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    salt = bytes(range(16))
    digest = hashlib.scrypt(PASSWORD.encode(), salt=salt, n=16384, r=8, p=1, dklen=64)
    monkeypatch.setenv("PP_PRESENTER_USERNAME", "presenter")
    monkeypatch.setenv(
        "PP_PRESENTER_PASSWORD_HASH", f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"
    )
    monkeypatch.setenv("PP_PRESENTER_ORGANIZATION_ID", str(ORG))
    monkeypatch.setenv("PP_ALLOWED_ORIGINS", ORIGIN)
    monkeypatch.setenv("PP_COOKIE_SECURE", "false")
    monkeypatch.setenv("PP_OR_SCHEMA", schema)
    registry = load_registry("production")
    queue = QueueRepository(engine, registry=registry, profile=RuntimeProfile())
    previous = getattr(app.state, "or_runtime", None)
    app.state.or_runtime = ORRuntime(engine, queue, ORG)
    if hasattr(app.state, "or_login_limiter"):
        del app.state.or_login_limiter
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, engine, schema
    app.state.or_runtime = previous
    engine.dispose()
    with raw.begin() as conn:
        conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
    raw.dispose()


def _login(client):
    response = client.post(
        "/api/v1/presenter/login",
        json={"username": "presenter", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200, response.text
    assert "httponly" in response.headers["set-cookie"].lower()
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": response.json()["csrf_token"],
        "Idempotency-Key": str(uuid4()),
    }


def _seed(client, headers):
    response = client.post(
        "/api/v1/demo/seed", json={"fixture": "six-beneficiary-v1"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def _scenario(client, headers, seed, *, mode="HUB_ONLY", multiplier="1"):
    modifiers = [{**m, "multiplier": multiplier} for m in seed["modifiers"]]
    response = client.post(
        "/api/v1/scenarios",
        json={
            "input_package_id": seed["input_package_id"],
            "policy_id": seed["policy_id"],
            "transfer_mode": mode,
            "planning_days": 3,
            "modifiers": modifiers,
            "intent": "CURRENT",
            "expected_source_revision": seed["source_revision_token"],
        },
        headers={**headers, "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    return response.json()


class RealSupervisor:
    def __init__(self, schema):
        env = {**os.environ, "DATABASE_URL": database_url()}
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "app.workers.supervisor",
                "--registry",
                "production",
                "--schema",
                schema,
            ],
            cwd=API_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        ready, _, _ = select.select([self.process.stdout], [], [], 15)
        assert ready, "production supervisor did not start"
        line = self.process.stdout.readline()
        assert "SUPERVISOR_RUNNING" in line, line

    def close(self):
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(10)
        self.process.stdout.close()
        self.process.stderr.close()


def _pair(client, headers, scenario):
    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/compare-methods",
        json={
            "expected_scenario_hash": scenario["operational_hash"],
            "intent": scenario["intent"],
        },
        headers={**headers, "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 202, response.text
    accepted = response.json()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        response = client.get(accepted["status_url"])
        assert response.status_code == 200, response.text
        job = response.json()
        if job["state"] not in {"QUEUED", "RUNNING", "STOPPING"}:
            assert job["state"] == "SUCCEEDED", job
            assert job["result_completeness"] == "TWO_OF_TWO"
            return job
        time.sleep(0.1)
    raise AssertionError("real persisted pair did not finish within accepted deadline")


def test_presenter_origin_csrf_body_limit_and_safe_errors(http):
    # OR-DEC-014 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    client, engine, _ = http
    response = client.post(
        "/api/v1/demo/seed",
        json={"fixture": "six-beneficiary-v1"},
        headers={"Idempotency-Key": "unauth"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "PRESENTER_REQUIRED"
    assert response.headers["x-request-id"] == response.json()["request_id"]
    response = client.post(
        "/api/v1/presenter/login",
        json={"username": "presenter", "password": PASSWORD},
        headers={"Origin": "https://other.example"},
    )
    assert response.status_code == 403
    headers = _login(client)
    missing = {k: v for k, v in headers.items() if k != "X-CSRF-Token"}
    assert (
        client.post(
            "/api/v1/demo/seed", json={"fixture": "six-beneficiary-v1"}, headers=missing
        ).status_code
        == 403
    )
    forged = {**headers, "X-Forwarded-Origin": ORIGIN, "X-PP-Proxy-Token": "forged"}
    assert (
        client.post(
            "/api/v1/demo/seed", json={"fixture": "six-beneficiary-v1"}, headers=forged
        ).status_code
        == 403
    )
    response = client.post(
        "/api/v1/scenarios", content="{", headers={**headers, "Content-Type": "application/json"}
    )
    assert response.status_code == 400 and response.json()["error"]["code"] == "MALFORMED_JSON"
    response = client.post(
        "/api/v1/scenarios", content=b"x" * (4 * 1024 * 1024 + 1), headers=headers
    )
    assert response.status_code == 413
    assert PASSWORD not in response.text and "scrypt" not in response.text
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM compute_jobs")) == 0


def test_login_rate_limit_and_logout_revokes_session(http):
    client, _, _ = http
    headers = _login(client)
    assert client.get("/api/v1/presenter/session").json()["authenticated"] is True
    assert client.post("/api/v1/presenter/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/presenter/session").json()["authenticated"] is False
    for _ in range(4):
        assert (
            client.post(
                "/api/v1/presenter/login",
                json={"username": "presenter", "password": "wrong"},
                headers={"Origin": ORIGIN},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/presenter/login",
            json={"username": "presenter", "password": "wrong"},
            headers={"Origin": ORIGIN},
        ).status_code
        == 429
    )


def test_explicit_mode_idempotency_saved_reads_and_unavailable_source(http):
    client, engine, _ = http
    headers = _login(client)
    seed = _seed(client, headers)
    assert _seed(client, headers) == seed
    body = {
        "input_package_id": seed["input_package_id"],
        "policy_id": seed["policy_id"],
        "planning_days": 3,
        "modifiers": seed["modifiers"],
        "intent": "CURRENT",
        "expected_source_revision": seed["source_revision_token"],
    }
    assert client.post("/api/v1/scenarios", json=body, headers=headers).status_code == 422
    scenario = _scenario(client, headers, seed)
    assert client.get(f"/api/v1/scenarios/{scenario['id']}").json()["transfer_mode"] == "HUB_ONLY"
    assert len(client.get("/api/v1/scenarios").json()) == 1
    assert client.get("/api/v1/scenarios?limit=0").status_code == 422
    assert client.get("/api/v1/scenarios?cursor=invalid").status_code == 422
    source = client.post(
        "/api/v1/or/input-packages/from-sources",
        json={
            "organization_id": str(ORG),
            "expected_source_revision": "x",
            "result_ids": [],
        },
        headers=headers,
    )
    assert source.status_code == 503
    assert source.json()["error"]["code"] == "SOURCE_INTEGRATION_UNAVAILABLE"
    submit = client.post(
        f"/api/v1/scenarios/{scenario['id']}/compare-methods",
        json={"expected_scenario_hash": scenario["operational_hash"], "intent": "CURRENT"},
        headers=headers,
    )
    assert submit.status_code == 503, submit.text
    for route in (
        f"/api/v1/scenarios/{scenario['id']}",
        "/api/v1/readiness",
        "/api/v1/capabilities",
    ):
        assert client.get(route).status_code == 200
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM compute_jobs")) == 0
        assert conn.scalar(sa.text("SELECT count(*) FROM or_scenarios")) == 1


def test_current_revision_conflict_and_public_live_fail_closed(http):
    client, engine, _ = http
    headers = _login(client)
    seed = _seed(client, headers)
    scenario = _scenario(client, headers, seed)
    with engine.begin() as conn:
        conn.execute(sa.update(DatasetState).values(revision_token="sim-v2"))
    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/compare-methods",
        json={"expected_scenario_hash": scenario["operational_hash"], "intent": "CURRENT"},
        headers=headers,
    )
    assert response.status_code == 409
    assert client.get(f"/api/v1/scenarios/{scenario['id']}").json()["stale"] is True
    # Package payload is presenter-only even for saved synthetic inputs.
    client.post("/api/v1/presenter/logout", headers=headers)
    response = client.get(f"/api/v1/or/input-packages/{seed['input_package_id']}")
    assert response.status_code == 200 and response.json()["payload"] is None
    assert client.get(f"/api/v1/scenarios/{uuid4()}").status_code == 404


def test_persisted_http_native_pair_disruption_review_outage_and_reset(http):
    client, engine, schema = http
    headers = _login(client)
    seed = _seed(client, headers)
    supervisor = RealSupervisor(schema)
    try:
        scenario = _scenario(client, headers, seed)
        job = _pair(client, headers, scenario)
        result = client.get(f"/api/v1/comparisons/{job['comparison_id']}")
        assert result.status_code == 200, result.text
        comparison = result.json()
        assert comparison["result"]["outcome"] == "SUCCEEDED"
        methods = comparison["result"]["methods"]
        assert [m["method"] for m in methods] == ["CLASSICAL_GP", "EGP_PI_INSPIRED"]
        assert methods[0]["objective"] == {"numerator": 163, "denominator": 50}
        assert methods[1]["objective"] == {"numerator": 1393, "denominator": 300}
        assert methods[0]["physical_fingerprint"] == methods[1]["physical_fingerprint"]
        plan = client.get(f"/api/v1/plans/{job['plans'][0]['plan_id']}").json()
        review = client.post(
            f"/api/v1/plans/{plan['id']}/review",
            json={
                "action": "REVIEWED",
                "expected_result_hash": plan["result_hash"],
                "note": "Simulated recommendation; no stock movement",
            },
            headers={**headers, "Idempotency-Key": "review-once"},
        )
        assert review.status_code == 201, review.text
        review_again = client.post(
            f"/api/v1/plans/{plan['id']}/review",
            json={
                "action": "REVIEWED",
                "expected_result_hash": plan["result_hash"],
                "note": "Simulated recommendation; no stock movement",
            },
            headers={**headers, "Idempotency-Key": "review-once"},
        )
        assert review_again.json()["id"] == review.json()["id"]
        changed = _scenario(client, headers, seed, mode="HUB_AND_PANTRY", multiplier="1.5")
        assert changed["id"] != scenario["id"]
        changed_job = _pair(client, headers, changed)
        assert len(changed_job["plans"]) == 2
        assert client.get(f"/api/v1/comparisons/{job['comparison_id']}").json() == comparison
    finally:
        supervisor.close()
    # Saved reads remain available after the worker is stopped; GET does no work.
    assert client.get(f"/api/v1/plans/{plan['id']}").status_code == 200
    assert client.get("/api/v1/readiness").json()["compute_available"] is False
    response = client.post(
        "/api/v1/demo/reset", json={"dataset_id": seed["dataset_id"]}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["history_retained"] is True
    assert client.get(f"/api/v1/plans/{plan['id']}").json()["stale"] is True
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(PlanRecord)) == 4
        assert conn.scalar(sa.text("SELECT count(*) FROM or_reviews")) == 1
        assert conn.scalar(sa.select(sa.func.count()).select_from(InputPackageRecord)) == 1


def test_chunked_oversize_and_resource_key_conflict_leave_no_extra_rows(http):
    client, engine, _ = http
    headers = _login(client)
    chunks = (b"x" * (1024 * 1024) for _ in range(5))
    response = client.post(
        "/api/v1/scenarios", content=chunks, headers={**headers, "Content-Type": "application/json"}
    )
    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "BODY_TOO_LARGE"
    seed = _seed(client, headers)
    body = {
        "input_package_id": seed["input_package_id"],
        "policy_id": seed["policy_id"],
        "transfer_mode": "HUB_ONLY",
        "planning_days": 3,
        "modifiers": seed["modifiers"],
        "intent": "CURRENT",
        "expected_source_revision": seed["source_revision_token"],
    }
    first = client.post("/api/v1/scenarios", json=body, headers=headers)
    assert first.status_code == 201, first.text
    second = client.post(
        "/api/v1/scenarios", json={**body, "transfer_mode": "HUB_AND_PANTRY"}, headers=headers
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM or_scenarios")) == 1
        assert conn.scalar(sa.text("SELECT count(*) FROM compute_jobs")) == 0


def test_saved_live_scope_is_not_public_and_expired_session_fails_closed(http):
    from app.models.or_records import PresenterSession
    from app.repositories.or_repository import ORRepository
    from app.schemas.or_inputs import ORInputPackage

    client, engine, _ = http
    headers = _login(client)
    seed = _seed(client, headers)
    response = client.get(f"/api/v1/or/input-packages/{seed['input_package_id']}")
    payload = response.json()["payload"]
    assert payload is not None
    payload["source_kind"] = "LIVE"
    # Deliberate internal test fixture exercises access denial only. It is never source
    # adapter or LIVE journey evidence; the public creation route cannot assert LIVE.
    with engine.begin() as conn:
        live = ORRepository(conn).put_package(
            ORInputPackage.model_validate(payload), uuid4(), trusted_live=True
        )
        conn.execute(sa.update(PresenterSession).values(revoked_at=sa.func.clock_timestamp()))
    assert client.get(f"/api/v1/or/input-packages/{live['id']}").status_code == 404
    response = client.post(
        "/api/v1/demo/seed", json={"fixture": "six-beneficiary-v1"}, headers=headers
    )
    assert response.status_code == 401
    assert (
        client.get(f"/api/v1/or/input-packages/{seed['input_package_id']}").json()["payload"]
        is None
    )
