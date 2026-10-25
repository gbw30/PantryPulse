"""Database/HTTP contracts with actual inference and independently verified solves.

Process containment and browser transport are separate Linux journey gates.
"""

import hashlib
import os
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from test_operational_postgres import migrate

from app.database import database_engine
from app.main import create_app
from app.models.optimization import MethodVerification, PlanningAssumptions, PlanningScenario
from app.repositories.jobs import QueueRepository, create_queue_engine
from app.services.forecast_runtime import ForecastRuntime
from app.services.jobs.contracts import PRODUCTION_PROFILE, StepOutcome, StepStatus, SupervisorState
from app.services.jobs.policies import should_run_step, supervisor_advertisement
from app.services.jobs.registry import ExecutionContext
from app.workers.registries import load_registry
from scripts.load_optimization_demo import seed_demo

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def planning_storage():
    url = os.environ.get("PP19_TEST_DATABASE_URL")
    if not url or os.environ.get("PP19_TEST_SCHEMA_ISOLATION") != "1":
        pytest.skip("requires isolated PostgreSQL")
    admin = database_engine(url)
    schema = "ppor_test_" + uuid4().hex
    with admin.begin() as conn:
        conn.execute(sa.schema.CreateSchema(schema))
        migrate(conn, schema)
        conn.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
        demo = seed_demo(conn)
    engine = create_queue_engine(admin.url, schema=schema)
    queue = QueueRepository(
        engine, registry=load_registry("production"), profile=PRODUCTION_PROFILE
    )
    try:
        yield ForecastRuntime(engine, queue), demo
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture
def api(planning_storage, monkeypatch):
    rt, demo = planning_storage
    salt = "37" * 16
    digest = hashlib.scrypt(
        b"test-password", salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=64
    ).hex()
    for k, v in dict(
        PP_PRESENTER_USERNAME="tester",
        PP_PRESENTER_PASSWORD_HASH=f"scrypt$16384$8$1${salt}${digest}",
        PP_PRESENTER_ORGANIZATION_ID=demo["organization_id"],
        PP_COOKIE_SECURE="false",
        PP_ALLOWED_ORIGINS="http://testserver",
    ).items():
        monkeypatch.setenv(k, v)
    with TestClient(create_app(rt)) as client:
        response = client.post(
            "/api/v1/presenter/login",
            json=dict(username="tester", password="test-password"),
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 200, response.text
        headers = {"Origin": "http://testserver", "X-CSRF-Token": response.json()["csrf_token"]}
        yield client, headers, rt, demo


def complete(queue, ownership):
    claim = queue.claim_next(ownership)
    assert claim is not None
    reg = queue.registry.get(claim.contract)
    data = claim.input_package["input"]
    outcomes = []
    for step in reg.handler.steps(data, PRODUCTION_PROFILE):
        if not should_run_step(step, outcomes):
            continue
        result = reg.handler.execute_step(
            step.name,
            data,
            [o.summary() for o in outcomes],
            ExecutionContext(claim.job_id, claim.attempt_id, step.name, 150, 300),
        )
        outcomes.append(StepOutcome(step.name, StepStatus.COMPLETED, result))
    queue.publish(ownership, claim, reg.publisher.validate(data, outcomes))
    return claim


def exercise_connected_snapshot(api):
    client, headers, rt, demo = api
    q = rt.queue
    ownership = q.acquire_ownership(
        supervisor_id=uuid4(),
        host_identity="TEST_DIRECT_EXECUTION",
        effective_limits=supervisor_advertisement(
            PRODUCTION_PROFILE, handler_contracts=q.registry.contracts(), process_containment=True
        ),
    )
    assert ownership
    assert q.set_state(ownership, SupervisorState.READY)
    try:
        accepted = client.post(
            "/api/v1/forecasts",
            json=demo["request"],
            headers=headers | {"Idempotency-Key": "planning-forecast"},
        )
        assert accepted.status_code == 202, accepted.text
        complete(q, ownership)
        forecast_id = accepted.json()["job_id"]
        catalog = client.get("/api/v1/planning-catalog").json()
        assumptions = client.get(f"/api/v1/planning-assumptions/{demo['assumptions_id']}").json()
        payload = assumptions["payload"]
        body = dict(
            forecast_run_id=forecast_id,
            assumptions_id=demo["assumptions_id"],
            expected_source_revision=catalog["source_revision"],
            transfer_mode="HUB_ONLY",
            planning_days=3,
            modifiers=[
                dict(
                    site_id=r["site_id"],
                    product_id=r["product_id"],
                    mode="CENTRAL",
                    multiplier="1",
                    buffer_fraction=None,
                )
                for r in payload["reserves"]
            ],
        )
        assert client.post("/api/v1/scenarios", json=body).status_code == 403
        bad = client.post(
            "/api/v1/scenarios",
            json=body | {"expected_source_revision": "0" * 64},
            headers=headers | {"Idempotency-Key": "stale"},
        )
        assert bad.status_code == 409, bad.text
        saved = client.post(
            "/api/v1/scenarios", json=body, headers=headers | {"Idempotency-Key": "freeze"}
        )
        assert saved.status_code == 201, saved.text
        scenario = saved.json()
        assert not scenario["stale"] and not scenario["historical"]
        replay = client.post(
            "/api/v1/scenarios", json=body, headers=headers | {"Idempotency-Key": "freeze"}
        )
        assert replay.json()["id"] == scenario["id"]
        from concurrent.futures import ThreadPoolExecutor

        def concurrent_freeze(_):
            return client.post(
                "/api/v1/scenarios",
                json=body,
                headers=headers | {"Idempotency-Key": "concurrent-freeze"},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            copies = list(pool.map(concurrent_freeze, range(2)))
        assert [r.status_code for r in copies] == [201, 201], [r.text for r in copies]
        assert copies[0].json()["id"] == copies[1].json()["id"]
        assert client.get(f"/api/v1/scenarios/{uuid4()}").status_code == 404
        q.heartbeat(ownership)
        accepted = client.post(
            "/api/v1/comparisons",
            json=dict(scenario_id=scenario["id"], search_seconds=1),
            headers=headers | {"Idempotency-Key": "compare"},
        )
        assert accepted.status_code == 202, accepted.text
        claim = complete(q, ownership)
        assert claim.budget_s == 92
        result = client.get(accepted.json()["result_url"])
        assert result.status_code == 200, result.text
        assert result.json()["result"]["outcome"] == "SUCCEEDED"
        assert all(
            method["verification"]["passed"] for method in result.json()["result"]["methods"]
        )
        assert result.json()["settings"]["search_milliseconds"] == 1000
        with rt.engine.connect() as conn:
            assert conn.scalar(sa.select(sa.func.count()).select_from(MethodVerification)) == 2
        for model, identity in (
            (PlanningScenario, UUID(scenario["id"])),
            (PlanningAssumptions, UUID(demo["assumptions_id"])),
        ):
            with pytest.raises(IntegrityError), rt.engine.begin() as conn:
                conn.execute(sa.delete(model).where(model.id == identity))
        changed = client.post(
            "/api/v1/planning-assumptions",
            json=dict(
                name="Revised simulated policy",
                parent_id=demo["assumptions_id"],
                payload=payload | {"policy": payload["policy"] | {"beta_percent": 75}},
            ),
            headers=headers,
        )
        assert changed.status_code == 201, changed.text
        assert changed.json()["id"] != demo["assumptions_id"]
        assert (
            client.get(f"/api/v1/planning-assumptions/{demo['assumptions_id']}").json()["payload"]
            == payload
        )
        # Actual audited stock metadata change marks old saved results stale without
        # rewriting their frozen inputs or changing any source quantities.
        from sqlalchemy.orm import Session

        from app.models import operational as m
        from app.schemas.stock import DeclareLot, StockActor
        from app.services.inventory.stock import execute_stock

        with rt.engine.begin() as conn, Session(bind=conn) as session:
            lot = session.scalar(
                sa.select(m.InventoryLot).where(
                    m.InventoryLot.organization_id == UUID(demo["organization_id"])
                )
            )
            version = session.scalar(
                sa.select(m.InventoryVersion.version).where(
                    m.InventoryVersion.organization_id == lot.organization_id,
                    m.InventoryVersion.site_id == lot.site_id,
                    m.InventoryVersion.product_id == lot.product_id,
                )
            )
            execute_stock(
                session,
                StockActor(organization_id=lot.organization_id, actor="test-stock-auditor"),
                DeclareLot(
                    idempotency_key="mark-unknown",
                    reason="Test unknown expiry declaration",
                    expected_versions=(
                        dict(site_id=lot.site_id, product_id=lot.product_id, version=version),
                    ),
                    lot_id=lot.id,
                    eligibility="ELIGIBLE",
                    expiry=dict(kind="UNKNOWN", expires_on=None),
                ),
            )
            session.flush()
        old = client.get(f"/api/v1/scenarios/{scenario['id']}").json()
        assert old["stale"] is True and old["payload"] == scenario["payload"]
        assert client.get(accepted.json()["result_url"]).json()["stale"] is True
        stale = client.post(
            "/api/v1/scenarios",
            json=body,
            headers=headers | {"Idempotency-Key": "after-stock-change"},
        )
        assert stale.status_code == 409
    finally:
        q.release(ownership)


def test_connected_snapshot_comparison_replay_and_immutable_history(api):
    exercise_connected_snapshot(api)


@pytest.fixture
def saved_plan(api):
    with api[2].engine.connect() as conn:
        exists = conn.scalar(sa.select(sa.func.count()).select_from(PlanningScenario))
    if not exists:
        exercise_connected_snapshot(api)
    return api


def test_real_linux_partner_failure_publishes_verified_partial(saved_plan):
    import sys
    import time
    from pathlib import Path

    from app.repositories.jobs import TrustedScope
    from app.services.jobs.contracts import AttemptState
    from app.services.optimization.settings import solver_settings
    from app.workers.process_driver import PosixProcessDriver, linux_containment_available
    from app.workers.supervisor import Supervisor, SupervisorConfig

    if not linux_containment_available():
        pytest.skip("Requires real Linux child processes")
    _, _, rt, demo = saved_plan
    org = UUID(demo["organization_id"])
    with rt.engine.connect() as conn:
        row = (
            conn.execute(
                sa.select(PlanningScenario.__table__).where(PlanningScenario.organization_id == org)
            )
            .mappings()
            .first()
        )
    assert row is not None

    class FailPartner(PosixProcessDriver):
        def start(self, argv, stdin_bytes, **kwargs):
            if argv[-1] == "EGP_PI_INSPIRED":
                argv = [sys.executable, "-c", "raise SystemExit(3)"]
            return super().start(argv, stdin_bytes, **kwargs)

    driver = FailPartner(cwd=str(Path(__file__).resolve().parents[2]))
    supervisor = Supervisor(
        rt.queue, rt.queue.registry, driver, SupervisorConfig("production", PRODUCTION_PROFILE)
    )
    assert supervisor.start()
    scope = TrustedScope(org, "controlled-partner-failure-test")
    try:
        accepted = rt.queue.submit(
            scope,
            "or-comparison.v2",
            dict(scenario_id=str(row["id"]), scenario=row["payload"], settings=solver_settings(1)),
            str(uuid4()),
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            supervisor.tick()
            job = rt.queue.get_job(scope, accepted.job_id)
            if job.state == AttemptState.SUCCEEDED:
                break
            time.sleep(0.05)
        assert job.state == AttemptState.SUCCEEDED
        assert job.attempts[-1].result_manifest["comparison_outcome"] == "PARTIAL"
        assert job.attempts[-1].result_manifest["planning_ready"] is False
        with rt.engine.connect() as conn:
            records = (
                conn.execute(
                    sa.select(MethodVerification.__table__).where(
                        MethodVerification.comparison_id == job.job_id
                    )
                )
                .mappings()
                .all()
            )
            assert {r["outcome"] for r in records} == {"VERIFIED", "FAILED"}
        supervisor.shutdown_drain()
    finally:
        supervisor.close()


def test_planning_resources_and_submissions_are_tenant_isolated(saved_plan, monkeypatch):
    from app.models import operational as m
    from app.models.optimization import PlanningComparison

    client, headers, rt, demo = saved_plan
    with rt.engine.begin() as conn:
        other = uuid4()
        conn.execute(
            sa.insert(m.Organization).values(id=other, name="Isolated other tenant", is_demo=True)
        )
        scenario = conn.execute(sa.select(PlanningScenario.__table__)).mappings().first()
        comparison = conn.execute(sa.select(PlanningComparison.__table__)).mappings().first()
    assert scenario and comparison
    monkeypatch.setenv("PP_PRESENTER_ORGANIZATION_ID", str(other))
    login = client.post(
        "/api/v1/presenter/login",
        json=dict(username="tester", password="test-password"),
        headers={"Origin": "http://testserver"},
    )
    assert login.status_code == 200
    other_headers = headers | {
        "X-CSRF-Token": login.json()["csrf_token"],
        "Idempotency-Key": "other-tenant",
    }
    for resource, identity in (
        ("scenarios", scenario["id"]),
        ("comparisons", comparison["id"]),
        ("planning-assumptions", demo["assumptions_id"]),
        ("jobs", comparison["job_id"]),
    ):
        assert client.get(f"/api/v1/{resource}/{identity}").status_code == 404
    assert (
        client.post(
            "/api/v1/comparisons", json=dict(scenario_id=str(scenario["id"])), headers=other_headers
        ).status_code
        == 404
    )
    catalog = client.get("/api/v1/planning-catalog").json()
    assert all(
        catalog[key] == [] for key in ("scenarios", "comparisons", "assumptions", "forecasts")
    )


def test_catalog_cursor_preserves_records_with_equal_timestamps(api):
    from datetime import UTC, datetime

    from app.repositories.planning import catalog

    _, _, rt, demo = api
    org = UUID(demo["organization_id"])
    with rt.engine.begin() as conn:
        original = (
            conn.execute(
                sa.select(PlanningAssumptions.__table__).where(
                    PlanningAssumptions.id == UUID(demo["assumptions_id"])
                )
            )
            .mappings()
            .one()
        )
        identities = {uuid4() for _ in range(63)}
        for identity in identities:
            conn.execute(
                sa.insert(PlanningAssumptions).values(
                    id=identity,
                    organization_id=org,
                    parent_id=original["id"],
                    name="Cursor regression",
                    content_hash=original["content_hash"],
                    payload=original["payload"],
                    actor="pagination-test",
                    recorded_at=datetime(2020, 1, 1, tzinfo=UTC),
                )
            )
        seen = set()
        before = before_id = None
        for _ in range(10):
            page = catalog(conn, org, before, before_id)
            seen.update(row["id"] for row in page["assumptions"])
            before, before_id = page["next_before"], page["next_before_id"]
            if before is None:
                break
        assert identities <= seen
