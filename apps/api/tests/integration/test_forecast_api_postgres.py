"""Actual PostgreSQL + HTTP + real baseline computation/publication, isolated schema.

This does not attest Linux process containment: execution invokes the real handler
directly so Windows can verify storage and HTTP without claiming a live worker.
"""

import hashlib
import os
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Thread
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from test_operational_postgres import migrate

from app.database import database_engine
from app.main import create_app
from app.models import operational as m
from app.models.forecasts import ForecastPointRecord, ForecastRun, PresenterSession
from app.repositories.forecast_history import HistoryRejected, load_input
from app.repositories.forecast_results import read_committed_forecast
from app.repositories.jobs import (
    Fenced,
    QueueRepository,
    QueueStorageUnavailable,
    TrustedScope,
    create_queue_engine,
)
from app.schemas.forecast_api import ForecastRequest
from app.services.forecast_runtime import ForecastRuntime
from app.services.jobs.contracts import (
    PRODUCTION_PROFILE,
    ReasonCode,
    StepOutcome,
    StepStatus,
    SupervisorState,
)
from app.services.jobs.policies import supervisor_advertisement
from app.services.jobs.registry import ExecutionContext, PublicationRejected
from app.workers.forecasting import REGISTRATION
from app.workers.registries import load_registry
from scripts.load_forecast_demo import seed_history

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def forecast_storage():
    url = os.environ.get("PP19_TEST_DATABASE_URL")
    if not url or os.environ.get("PP19_TEST_SCHEMA_ISOLATION") != "1":
        pytest.skip("requires explicit PostgreSQL isolated-schema opt-in")
    admin = database_engine(url)
    schema = "pp45_test_" + uuid4().hex
    assert re.fullmatch(r"pp45_test_[0-9a-f]{32}", schema)
    with admin.begin() as conn:
        conn.execute(sa.schema.CreateSchema(schema))
        migrate(conn, schema)
        conn.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        demo = seed_history(conn)
    engine = create_queue_engine(admin.url, schema=schema)
    queue = QueueRepository(
        engine, registry=load_registry("production"), profile=PRODUCTION_PROFILE
    )
    queue._test_heartbeat_handles = []
    try:
        yield ForecastRuntime(engine, queue), demo
    finally:
        for stop, thread in queue._test_heartbeat_handles:
            stop.set()
            thread.join(timeout=5)
        engine.dispose()
        assert re.fullmatch(r"pp45_test_[0-9a-f]{32}", schema)
        with admin.begin() as conn:
            conn.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture
def api(forecast_storage, monkeypatch):
    runtime, demo = forecast_storage
    salt = "37" * 16
    digest = hashlib.scrypt(
        b"test-password", salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=64
    ).hex()
    for name, value in dict(
        PP_PRESENTER_USERNAME="tester",
        PP_PRESENTER_PASSWORD_HASH=(f"scrypt$16384$8$1${salt}${digest}"),
        PP_PRESENTER_ORGANIZATION_ID=demo["organization_id"],
        PP_COOKIE_SECURE="false",
        PP_ALLOWED_ORIGINS="http://testserver",
    ).items():
        monkeypatch.setenv(name, value)
    with TestClient(create_app(runtime)) as client:
        response = client.post(
            "/api/v1/presenter/login",
            json={"username": "tester", "password": "test-password"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 200, response.text
        headers = {"Origin": "http://testserver", "X-CSRF-Token": response.json()["csrf_token"]}
        yield client, headers, runtime, demo


def advertise(queue, contracts=None):
    own = queue.acquire_ownership(
        supervisor_id=uuid4(),
        host_identity="TEST_ADMISSION_ONLY",
        effective_limits=supervisor_advertisement(
            PRODUCTION_PROFILE,
            handler_contracts=contracts or ["forecast.v1"],
            process_containment=True,
        ),
    )
    assert own is not None
    assert queue.set_state(own, SupervisorState.READY)
    # Test admission stand-in only: keep its heartbeat alive while real DB checks run.
    # It never advertises a production worker or validates Linux containment.
    stop = Event()

    def heartbeat():
        while not stop.wait(1):
            try:
                if not queue.heartbeat(own):
                    return
            except QueueStorageUnavailable:
                # Retry transient control-row contention, as the real supervisor does.
                continue

    thread = Thread(target=heartbeat, daemon=True)
    queue._test_heartbeat_handles.append((stop, thread))
    thread.start()
    return own


def compute(queue, own):
    claim = queue.claim_next(own)
    assert claim is not None
    validated = claim.input_package["input"]
    context = ExecutionContext(claim.job_id, claim.attempt_id, "primary", 298, 15)
    output = REGISTRATION.handler.execute_step("primary", validated, (), context)
    package = REGISTRATION.publisher.validate(
        validated, [StepOutcome("primary", StepStatus.COMPLETED, output=output)]
    )
    return claim, package


def test_actual_database_http_forecast_publication_and_reuse(api):
    client, headers, runtime, demo = api
    q = runtime.queue
    own = advertise(q)
    try:
        request = demo["request"]
        response = client.post(
            "/api/v1/forecasts", json=request, headers=headers | {"Idempotency-Key": "actual-flow"}
        )
        assert response.status_code == 202, response.text
        accepted = response.json()
        assert client.get(accepted["result_url"]).status_code == 409
        # A repeated identical request, including a different key, shares one job.
        duplicate = client.post(
            "/api/v1/forecasts", json=request, headers=headers | {"Idempotency-Key": "other-key"}
        )
        assert duplicate.json()["job_id"] == accepted["job_id"]
        claim, package = compute(q, own)
        q.publish(own, claim, package)
        saved = client.get(accepted["result_url"])
        assert saved.status_code == 200, saved.text
        result = saved.json()
        assert result["planning_ready"] is True
        assert len(result["forecast"]["series"]) == 26
        assert sum(len(s["points"]) for s in result["forecast"]["series"]) == 182
        assert result["forecast"]["actual_providers"] == ["SEASONAL_NAIVE"]
        assert "SIMULATED_SOURCE" in result["forecast"]["warnings"]
        assert all(p["p90"] is None for s in result["forecast"]["series"] for p in s["points"])
        assert client.get(accepted["status_url"]).json()["state"] == "SUCCEEDED"
        frozen, raw = read_committed_forecast(
            runtime.engine, UUID(demo["organization_id"]), UUID(accepted["job_id"])
        )
        assert raw.model_dump(mode="json") == result["forecast"]
        assert raw.input_hash == frozen.input_hash
        with runtime.engine.connect() as conn:
            assert conn.scalar(sa.select(sa.func.count()).select_from(ForecastPointRecord)) == 182
            assert conn.scalar(sa.select(sa.func.count()).select_from(m.InventoryLot)) == 0
        q.release(own)
        offline = client.post(
            "/api/v1/forecasts",
            json=request,
            headers=headers | {"Idempotency-Key": "offline-reuse"},
        )
        assert offline.json()["job_id"] == accepted["job_id"]
        assert client.get(accepted["result_url"]).json() == result
        # Explicit refresh still requires healthy compute, even with saved results.
        refresh = client.post(
            "/api/v1/forecasts",
            json=request | {"force_refresh": True},
            headers=headers | {"Idempotency-Key": "force-offline"},
        )
        assert refresh.status_code == 503
        conflict = client.post(
            "/api/v1/forecasts",
            json=request | {"force_refresh": True},
            headers=headers | {"Idempotency-Key": "actual-flow"},
        )
        assert conflict.status_code == 409
    finally:
        q.release(own)


def test_auth_scope_csrf_limits_and_error_redaction(api):
    client, headers, runtime, demo = api
    assert client.get("/api/v1/forecast-catalog").status_code == 200
    assert (
        client.post(
            "/api/v1/forecasts",
            json=demo["request"],
            headers={"Idempotency-Key": "missing-csrf", "Origin": "http://testserver"},
        ).status_code
        == 403
    )
    bad = client.post(
        "/api/v1/forecasts",
        json=demo["request"] | {"organization_id": str(uuid4())},
        headers=headers | {"Idempotency-Key": "bad-tenant"},
    )
    assert bad.status_code == 422
    assert "organization_id" not in bad.text
    assert bad.json()["request_id"] == bad.headers["x-request-id"]
    assert bad.json()["error"]["details"] == {}
    malformed = client.post(
        "/api/v1/forecasts", content=b'{"source_id":',
        headers=headers | {"Content-Type": "application/json", "Idempotency-Key": "malformed"},
    )
    assert malformed.status_code == 400
    assert malformed.json()["request_id"] == malformed.headers["x-request-id"]
    assert client.post("/api/v1/forecasts", content=b"x" * 65_537).status_code == 413
    with pytest.raises(IntegrityError), runtime.engine.begin() as conn:
        conn.execute(sa.update(PresenterSession).values(organization_id=uuid4()))
    with runtime.engine.begin() as conn:
        other = uuid4()
        conn.execute(
            sa.insert(m.Organization).values(id=other, name="Other test tenant", is_demo=True)
        )
        conn.execute(sa.update(PresenterSession).values(organization_id=other))
    with runtime.engine.connect() as conn:
        job = conn.scalar(sa.select(ForecastRun.job_id).limit(1))
    if job:
        assert client.get(f"/api/v1/jobs/{job}").status_code == 404
        assert client.get(f"/api/v1/forecasts/{job}").status_code == 404
    assert client.get("/api/v1/forecast-catalog").json()["sources"] == []


def test_precision_and_source_ownership(forecast_storage):
    runtime, demo = forecast_storage
    from app.repositories.forecast_history import exact_float

    with pytest.raises(HistoryRejected, match="QUANTITY_NOT_EXACT"):
        exact_float(2**53 + 1)
    request = ForecastRequest.model_validate(demo["request"])
    with pytest.raises(HistoryRejected, match="SOURCE_NOT_FOUND"):
        load_input(runtime.engine, uuid4(), request)
    inputs = load_input(runtime.engine, UUID(demo["organization_id"]), request)
    assert len(inputs.series) == 26
    assert {s.scope.key.site_id for s in inputs.series if s.scope.key.target_type == "DEMAND"}
    assert (
        len({s.scope.key.site_id for s in inputs.series if s.scope.key.target_type == "DEMAND"})
        == 6
    )


def test_atomic_rollback_and_cancel_fence(forecast_storage, monkeypatch):
    runtime, demo = forecast_storage
    queue = runtime.queue
    own = advertise(queue)
    scope = TrustedScope(UUID(demo["organization_id"]), "publication-test")
    inputs = load_input(
        runtime.engine, scope.organization_id, ForecastRequest.model_validate(demo["request"])
    )
    payload = dict(forecast_input=inputs.model_dump(mode="json"))
    accepted = queue.submit(scope, "forecast.v1", payload, "rollback-test")
    claim, package = compute(queue, own)
    original = REGISTRATION.publisher.publish

    def broken(conn, identity, staged):
        original(conn, identity, staged)
        raise PublicationRejected("TEST_AFTER_ALL_INSERTS")

    try:
        with monkeypatch.context() as local:
            local.setattr(REGISTRATION.publisher, "publish", broken)
            with pytest.raises(PublicationRejected):
                queue.publish(own, claim, package)
        with runtime.engine.connect() as conn:
            assert (
                conn.scalar(sa.select(ForecastRun.id).where(ForecastRun.job_id == accepted.job_id))
                is None
            )
        assert queue.get_job(scope, accepted.job_id).state == "RUNNING"
        queue.request_stop(own, claim, ReasonCode.CANCEL_REQUESTED)
        with pytest.raises(Fenced):
            queue.publish(own, claim, package)
        queue.finalize(own, claim)
        assert queue.get_job(scope, accepted.job_id).state == "CANCELLED"
    finally:
        queue.release(own)


def test_concurrent_dedup_and_explicit_refresh(forecast_storage):
    runtime, demo = forecast_storage
    queue = runtime.queue
    own = advertise(queue)
    scope = TrustedScope(UUID(demo["organization_id"]), "concurrency-test")
    request = ForecastRequest.model_validate(demo["request"])
    # Different policy ensures this checks active admission rather than an earlier saved run.
    request = request.model_copy(
        update={"policy": request.policy.model_copy(update={"strategy": "MOVING_AVERAGE"})}
    )
    inputs = load_input(runtime.engine, scope.organization_id, request)
    payload = dict(forecast_input=inputs.model_dump(mode="json"))
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            accepted = list(
                pool.map(
                    lambda i: queue.submit(
                        scope, "forecast.v1", payload, f"concurrent-{i}", deduplicate=True
                    ),
                    range(4),
                )
            )
        assert len({a.job_id for a in accepted}) == 1
        assert sum(not a.replayed for a in accepted) == 1
        claim, package = compute(queue, own)
        queue.publish(own, claim, package)
        refresh = queue.submit(scope, "forecast.v1", payload, "healthy-refresh", deduplicate=False)
        assert refresh.job_id != accepted[0].job_id
        claim, package = compute(queue, own)
        queue.publish(own, claim, package)
        reused = queue.submit(
            scope, "forecast.v1", payload, "reuse-after-refresh", deduplicate=True
        )
        assert reused.job_id == refresh.job_id
        with pytest.raises(IntegrityError), runtime.engine.begin() as conn:
            conn.execute(
                sa.update(ForecastRun)
                .where(ForecastRun.id == refresh.job_id)
                .values(planning_ready=False)
            )
    finally:
        queue.release(own)


def test_insufficient_history_is_saved_but_never_planning_ready(api):
    client, headers, runtime, demo = api
    source = uuid4()
    with runtime.engine.begin() as conn:
        conn.execute(
            sa.insert(m.DataSource).values(
                id=source,
                organization_id=UUID(demo["organization_id"]),
                name="Empty simulated source",
                classification="SIMULATED",
                recorded_at="2026-07-01T00:00:00Z",
            )
        )
    request = demo["request"] | {"source_id": str(source)}
    request["policy"] = request["policy"] | {"strategy": "MOVING_AVERAGE", "allow_fallback": False}
    own = advertise(runtime.queue)
    try:
        response = client.post(
            "/api/v1/forecasts",
            json=request,
            headers=headers | {"Idempotency-Key": "missing-history"},
        )
        assert response.status_code == 202, response.text
        claim, package = compute(runtime.queue, own)
        runtime.queue.publish(own, claim, package)
        saved = client.get(response.json()["result_url"]).json()
        assert saved["planning_ready"] is False
        assert all(
            s["status"] == "INSUFFICIENT_DATA" and not s["points"]
            for s in saved["forecast"]["series"]
        )
        with pytest.raises(HistoryRejected, match="NOT_PLANNING_READY"):
            read_committed_forecast(runtime.engine, UUID(demo["organization_id"]), claim.job_id)
        # Manual retry/cancel use the existing durable command lifecycle, not rerun-on-GET.
        refresh = client.post(
            "/api/v1/forecasts",
            json=request,
            headers=headers | {"Idempotency-Key": "missing-again"},
        )
        assert refresh.json()["job_id"] != response.json()["job_id"]
        cancelled = client.post(
            refresh.json()["status_url"] + "/cancel",
            headers=headers | {"Idempotency-Key": "cancel-missing"},
        )
        assert cancelled.status_code == 202 and cancelled.json()["state"] == "CANCELLED"
        retried = client.post(
            refresh.json()["status_url"] + "/retry",
            headers=headers | {"Idempotency-Key": "retry-missing"},
        )
        assert retried.status_code == 202 and retried.json()["state"] == "QUEUED"
        assert retried.json()["attempt_id"] != refresh.json()["attempt_id"]
        client.post(
            refresh.json()["status_url"] + "/cancel",
            headers=headers | {"Idempotency-Key": "cancel-retry"},
        )
        assert client.post("/api/v1/presenter/logout", headers=headers).status_code == 200
        assert client.get("/api/v1/forecast-catalog").status_code == 401
    finally:
        runtime.queue.release(own)
