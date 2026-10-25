"""Actual PostgreSQL integrity and transaction evidence for OR-DEC-009/012/015/020.

Each test owns an isolated schema inside the explicitly named *_test database. A missing
URL is NOT RUN; SQLite and mocked transactions never qualify these checks.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.exc import DBAPIError
from wq_support import alembic_config, database_url

from app.models.jobs import compute_attempts, compute_control, compute_jobs
from app.models.or_records import (
    AuditEvent,
    DatasetState,
    InputPackageRecord,
    PlanRecord,
    PolicyRecord,
    RequestKey,
    ReviewRecord,
    ScenarioRecord,
    VerificationRecord,
)
from app.repositories.jobs import create_queue_engine
from app.repositories.or_repository import ORRepository, ORStorageError
from app.schemas.or_inputs import ORScenarioPayload
from app.schemas.or_outputs import Candidate, MethodOutcome, RouteQuantity
from app.services.jobs.registry import PublicationIdentity, PublicationRejected
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.packing import pack
from app.services.optimization.verify import verify

pytestmark = pytest.mark.integration
FIXTURE = Path(__file__).resolve().parents[4] / "data/demo/or-v1/six-beneficiary-v1.snapshot.json"


@pytest.fixture
def pg():
    url = database_url()
    schema = "or_storage_" + uuid4().hex[:16]
    raw = sa.create_engine(url)
    with raw.begin() as conn:
        assert conn.scalar(sa.text("SELECT current_database()")).endswith("_test")
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = create_queue_engine(url, schema=schema)
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    yield engine
    engine.dispose()
    with raw.begin() as conn:
        conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
    raw.dispose()


@pytest.fixture
def snapshot():
    return ORScenarioPayload.model_validate_json(FIXTURE.read_text())


def _seed(conn, snapshot, *, demo=True):
    actor = uuid4()
    repo = ORRepository(conn)
    package = repo.put_package(snapshot.package, actor, demo_scope=demo)
    policy = repo.put_policy(snapshot.package.organization_id, snapshot.policy, actor)
    scenario = repo.put_scenario(
        snapshot,
        package["id"],
        policy["id"],
        actor,
        expected_revision=snapshot.package.source_revision_token,
    )
    return actor, package, policy, scenario


def _running(conn, org):
    now = conn.scalar(sa.text("SELECT clock_timestamp()"))
    job, attempt, supervisor = uuid4(), uuid4(), uuid4()
    conn.execute(
        sa.insert(compute_jobs).values(
            job_id=job,
            lane_id="default",
            organization_id=org,
            requested_by_ref="test-presenter",
            operation_kind="COMPARISON",
            handler_contract="or.test.v1",
            input_schema_version="v1",
            input_package={},
            input_sha256="a" * 64,
            current_attempt_id=attempt,
            state="RUNNING",
            created_at=now,
            updated_at=now,
        )
    )
    conn.execute(
        sa.insert(compute_attempts).values(
            attempt_id=attempt,
            job_id=job,
            attempt_number=1,
            lane_id="default",
            organization_id=org,
            state="RUNNING",
            state_version=1,
            enqueued_at=now,
            queue_deadline_at=now + timedelta(seconds=900),
            supervisor_id=supervisor,
            supervisor_generation=1,
            execution_token=uuid4(),
            started_at=now,
            execution_deadline_at=now + timedelta(seconds=60),
            diagnostics={},
        )
    )
    conn.execute(
        sa.update(compute_control)
        .where(compute_control.c.lane_id == "default")
        .values(
            supervisor_id=supervisor,
            generation=1,
            state="READY",
            heartbeat_at=now,
            active_attempt_id=attempt,
        )
    )
    return PublicationIdentity(job, attempt, org, "or.test.v1", "a" * 64)


def _zero(snapshot):
    problem = prepare_problem(snapshot)
    quantities = tuple(
        RouteQuantity(route_id=c.route_id, product_id=c.product_id, units=0)
        for c in problem.candidates
    )
    candidate = Candidate(route_quantities=quantities, assignments=pack(problem, quantities))
    report = verify(problem, candidate, "CLASSICAL_GP")
    assert report.passed, report.violations
    return MethodOutcome(
        method="CLASSICAL_GP",
        transfer_mode=snapshot.transfer_mode,
        operational_hash=snapshot.operational_hash,
        policy_hash=snapshot.policy_hash,
        settings_hash="b" * 64,
        decision_ids=snapshot.decision_ids,
        native_status="OPTIMAL",
        outcome="VERIFIED",
        candidate=candidate,
        verification=report,
        objective=report.metrics.classical_objective,
    )


def test_upgrade_downgrade_upgrade_and_model_columns(pg):
    with pg.begin() as conn:
        names = set(sa.inspect(conn).get_table_names())
        assert {"or_scenarios", "or_plans", "compute_jobs", "presenter_sessions"} <= names
        command.downgrade(alembic_config(conn), "0001_jobs_foundation")
        assert "or_plans" not in sa.inspect(conn).get_table_names()
        assert "compute_jobs" in sa.inspect(conn).get_table_names()
        command.upgrade(alembic_config(conn), "head")
        from app.models.or_records import Base

        inspector = sa.inspect(conn)
        for table in Base.metadata.sorted_tables:
            assert {c.name for c in table.columns} == {
                c["name"] for c in inspector.get_columns(table.name)
            }


def test_round_trip_replay_and_content_dedup(pg, snapshot):
    with pg.begin() as conn:
        actor, package, policy, scenario = _seed(conn, snapshot)
        repo = ORRepository(conn)
        assert repo.put_package(snapshot.package, actor)["id"] == package["id"]
        assert (
            repo.put_policy(snapshot.package.organization_id, snapshot.policy, actor)["id"]
            == policy["id"]
        )
        assert (
            repo.put_scenario(
                snapshot,
                package["id"],
                policy["id"],
                actor,
                expected_revision=snapshot.package.source_revision_token,
            )["id"]
            == scenario["id"]
        )
        replay = repo.get(ScenarioRecord, snapshot.package.organization_id, scenario["id"])
        assert ORScenarioPayload.model_validate(replay["payload"]) == snapshot
        assert conn.scalar(sa.select(sa.func.count()).select_from(AuditEvent)) == 3


@pytest.mark.parametrize("table", ["or_input_packages", "or_policies", "or_scenarios"])
@pytest.mark.parametrize("action", ["UPDATE", "DELETE"])
def test_historical_records_immutable_in_database(pg, snapshot, table, action):
    # OR-DEC-012 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    with pg.begin() as conn:
        _seed(conn, snapshot)
    statement = f"DELETE FROM {table}" if action == "DELETE" else f"UPDATE {table} SET id=id"
    with pytest.raises(DBAPIError), pg.begin() as conn:
        conn.execute(sa.text(statement))


def test_cross_org_lookup_and_composite_foreign_key(pg, snapshot):
    with pg.begin() as conn:
        actor, package, policy, scenario = _seed(conn, snapshot)
        with pytest.raises(ORStorageError, match="NOT_FOUND"):
            ORRepository(conn).get(ScenarioRecord, uuid4(), scenario["id"])
    with pytest.raises(DBAPIError), pg.begin() as conn:
        values = {k: v for k, v in scenario.items() if k != "created_at"}
        values.update(id=uuid4(), organization_id=uuid4())
        conn.execute(sa.insert(ScenarioRecord).values(**values))


@pytest.mark.parametrize(
    "updates",
    [
        {"planning_days": 0},
        {"transfer_mode": "hub_only"},
        {"org_epoch": -1},
    ],
)
def test_invalid_database_scenario_inserts_rejected(pg, snapshot, updates):
    with pg.begin() as conn:
        _, _, _, scenario = _seed(conn, snapshot)
    with pytest.raises(DBAPIError), pg.begin() as conn:
        values = {k: v for k, v in scenario.items() if k != "created_at"}
        values.update(id=uuid4(), operational_hash="e" * 64, **updates)
        conn.execute(sa.insert(ScenarioRecord).values(**values))


def test_transaction_rollback_includes_snapshot_epoch_and_audit(pg, snapshot):
    with pytest.raises(RuntimeError, match="deliberate"), pg.begin() as conn:
        _seed(conn, snapshot)
        raise RuntimeError("deliberate rollback")
    with pg.connect() as conn:
        for model in (InputPackageRecord, PolicyRecord, ScenarioRecord, AuditEvent, DatasetState):
            assert conn.scalar(sa.select(sa.func.count()).select_from(model)) == 0


def test_revision_change_stales_current_but_historical_stays_readable(pg, snapshot):
    # OR-DEC-015 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    with pg.begin() as conn:
        actor, _, _, scenario = _seed(conn, snapshot)
        package2 = snapshot.package.model_copy(update={"source_revision_token": "sim-v2"})
        repo = ORRepository(conn)
        with pytest.raises(ORStorageError, match="SOURCE_REVISION_MISMATCH"):
            repo.put_package(package2, actor)
        repo.put_package(package2, actor, expected_revision="sim-v1")
        old = repo.get(ScenarioRecord, snapshot.package.organization_id, scenario["id"])
        with pytest.raises(ORStorageError, match="SOURCE_REVISION_MISMATCH"):
            repo.assert_current(old)
        assert old["operational_hash"] == snapshot.operational_hash


def test_live_assertion_and_bad_manifest_cannot_be_published(pg, snapshot):
    # OR-DEC-020 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    with pg.begin() as conn:
        repo = ORRepository(conn)
        with pytest.raises(ORStorageError, match="SOURCE_INTEGRATION_UNAVAILABLE"):
            repo.put_package(snapshot.package.model_copy(update={"source_kind": "LIVE"}), uuid4())
        with pytest.raises(ValueError, match="SOURCE_MANIFEST_HASH_MISMATCH"):
            repo.put_package(
                snapshot.package.model_copy(update={"source_manifest_hash": "f" * 64}), uuid4()
            )


def test_request_key_race_reuses_exact_identity_and_conflicts_mismatch(pg):
    org, actor = uuid4(), uuid4()

    def insert_key(_):
        with pg.begin() as conn:
            return ORRepository(conn).request_key(
                org, actor, "scenario-create", "race", "a" * 64, uuid4()
            )

    with ThreadPoolExecutor(max_workers=6) as executor:
        ids = list(executor.map(insert_key, range(12)))
    assert len(set(ids)) == 1
    with pg.begin() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(RequestKey)) == 1
        with pytest.raises(ORStorageError, match="IDEMPOTENCY_CONFLICT"):
            ORRepository(conn).request_key(org, actor, "scenario-create", "race", "b" * 64, uuid4())


def test_package_race_has_one_record_and_one_audit(pg, snapshot):
    def create_package(_):
        with pg.begin() as conn:
            return ORRepository(conn).put_package(snapshot.package, uuid4())["id"]

    with ThreadPoolExecutor(max_workers=6) as executor:
        ids = list(executor.map(create_package, range(12)))
    assert len(set(ids)) == 1
    with pg.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(InputPackageRecord)) == 1
        assert conn.scalar(sa.select(sa.func.count()).select_from(AuditEvent)) == 1


def test_atomic_verified_plan_and_append_only_review(pg, snapshot):
    outcome = _zero(snapshot)
    with pg.begin() as conn:
        actor, _, _, scenario = _seed(conn, snapshot)
        identity = _running(conn, snapshot.package.organization_id)
        repo = ORRepository(conn)
        plan = repo.publish_plan(identity, scenario["id"], outcome)
        review = repo.review(
            snapshot.package.organization_id,
            plan["id"],
            actor,
            "REVIEWED",
            plan["result_hash"],
            "Simulation only",
        )
        assert review["plan_result_hash"] == plan["result_hash"]
    with pg.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(PlanRecord)) == 1
        assert conn.scalar(sa.select(sa.func.count()).select_from(VerificationRecord)) == 1
        assert conn.scalar(sa.select(sa.func.count()).select_from(ReviewRecord)) == 1
        assert not any("stock" in n or "ledger" in n for n in sa.inspect(conn).get_table_names())
    with pytest.raises(DBAPIError), pg.begin() as conn:
        conn.execute(sa.update(ReviewRecord).values(note="rewritten"))
    with pg.begin() as conn:
        with pytest.raises(ORStorageError, match="RESULT_REVISION_MISMATCH"):
            ORRepository(conn).review(
                snapshot.package.organization_id, plan["id"], actor, "REJECTED", "f" * 64
            )


def test_plan_without_atomic_verification_rejected_at_commit(pg, snapshot):
    with pg.begin() as conn:
        _, _, _, scenario = _seed(conn, snapshot)
        identity = _running(conn, snapshot.package.organization_id)
    with pytest.raises(DBAPIError), pg.begin() as conn:
        conn.execute(
            sa.insert(PlanRecord).values(
                id=uuid4(),
                organization_id=identity.organization_id,
                scenario_id=scenario["id"],
                job_id=identity.job_id,
                attempt_id=identity.attempt_id,
                method="CLASSICAL_GP",
                native_status="OPTIMAL",
                outcome="VERIFIED",
                settings_hash="c" * 64,
                result={},
                result_hash="d" * 64,
                verified_at=sa.func.clock_timestamp(),
            )
        )
    with pg.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(PlanRecord)) == 0


def test_result_replay_detects_corrupt_hash(pg, snapshot):
    with pg.begin() as conn:
        _, _, _, scenario = _seed(conn, snapshot)
        identity = _running(conn, snapshot.package.organization_id)
        plan = ORRepository(conn).publish_plan(identity, scenario["id"], _zero(snapshot))
    with pg.begin() as conn:
        # The trigger protects mutation; inserting a wrong hash into a new record is also
        # caught when read. This deliberately uses SQL rather than the trusted publisher.
        conn.execute(sa.text("ALTER TABLE or_plans DISABLE TRIGGER trg_or_plans_immutable"))
        conn.execute(
            sa.update(PlanRecord).where(PlanRecord.id == plan["id"]).values(result_hash="0" * 64)
        )
        conn.execute(sa.text("ALTER TABLE or_plans ENABLE TRIGGER trg_or_plans_immutable"))
    with pg.connect() as conn, pytest.raises(ORStorageError, match="RESULT_HASH_MISMATCH"):
        ORRepository(conn).get(PlanRecord, identity.organization_id, plan["id"])


def test_publication_fenced_after_cancel_or_epoch_change(pg, snapshot):
    outcome = _zero(snapshot)
    with pg.begin() as conn:
        _, _, _, scenario = _seed(conn, snapshot)
        identity = _running(conn, snapshot.package.organization_id)
        conn.execute(
            sa.update(compute_attempts)
            .where(compute_attempts.c.attempt_id == identity.attempt_id)
            .values(
                state="STOPPING",
                state_version=2,
                stop_requested_at=sa.func.clock_timestamp(),
                stop_reason="CANCEL_REQUESTED",
            )
        )
        with pytest.raises(PublicationRejected, match="OR_PUBLICATION_FENCED"):
            ORRepository(conn).publish_plan(identity, scenario["id"], outcome)


def test_reset_requires_demo_scope_and_fences_old_scenarios(pg, snapshot):
    with pg.begin() as conn:
        actor, package, policy, scenario = _seed(conn, snapshot, demo=False)
        repo = ORRepository(conn)
        with pytest.raises(ORStorageError, match="DEMO_SCOPE_REQUIRED"):
            repo.reset_demo(snapshot.package.organization_id, snapshot.package.dataset_id, actor)
        conn.execute(sa.update(DatasetState).values(is_demo=True))
        assert (
            repo.reset_demo(snapshot.package.organization_id, snapshot.package.dataset_id, actor)
            == 1
        )
        old = repo.get(ScenarioRecord, snapshot.package.organization_id, scenario["id"])
        with pytest.raises(ORStorageError, match="DATASET_EPOCH_MISMATCH"):
            repo.assert_current(old)
        new = repo.put_scenario(
            snapshot,
            package["id"],
            policy["id"],
            actor,
            expected_revision=snapshot.package.source_revision_token,
        )
        assert new["id"] != old["id"] and new["org_epoch"] == 1
        assert conn.scalar(sa.select(sa.func.count()).select_from(ScenarioRecord)) == 2


def test_publication_transaction_rollback_removes_plan_transfers_and_check(pg, snapshot):
    with pg.begin() as conn:
        _, _, _, scenario = _seed(conn, snapshot)
        identity = _running(conn, snapshot.package.organization_id)
    with pytest.raises(RuntimeError, match="publication rollback"), pg.begin() as conn:
        ORRepository(conn).publish_plan(identity, scenario["id"], _zero(snapshot))
        raise RuntimeError("publication rollback")
    with pg.connect() as conn:
        for model in (PlanRecord, VerificationRecord):
            assert conn.scalar(sa.select(sa.func.count()).select_from(model)) == 0
        assert conn.scalar(sa.select(sa.func.count()).select_from(ScenarioRecord)) == 1


def test_publication_epoch_guard_rejects_late_candidate(pg, snapshot):
    with pg.begin() as conn:
        _, _, _, scenario = _seed(conn, snapshot)
        identity = _running(conn, snapshot.package.organization_id)
        conn.execute(sa.update(DatasetState).values(org_epoch=1))
        with pytest.raises(ORStorageError, match="DATASET_EPOCH_MISMATCH"):
            ORRepository(conn).publish_plan(identity, scenario["id"], _zero(snapshot))
        assert conn.scalar(sa.select(sa.func.count()).select_from(PlanRecord)) == 0


def test_parent_rejects_fabricated_objective_before_publishing(pg, snapshot):
    from app.schemas.or_inputs import Rational

    with pg.begin() as conn:
        _, _, _, scenario = _seed(conn, snapshot)
        identity = _running(conn, snapshot.package.organization_id)
        fake = _zero(snapshot).model_copy(update={"objective": Rational.of(0)})
        with pytest.raises(PublicationRejected, match="OR_OBJECTIVE_MISMATCH"):
            ORRepository(conn).publish_plan(identity, scenario["id"], fake)
        assert conn.scalar(sa.select(sa.func.count()).select_from(PlanRecord)) == 0
