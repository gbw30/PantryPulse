"""OR-DEC-011/016 [PROVISIONAL]: checked step commits and honest partial outcomes."""

import dataclasses
import time
import uuid

import pytest
import sqlalchemy as sa
from fake_driver import FakeDriver
from wq_support import TEST_PROFILE

from app.repositories.jobs import Fenced, QueueRepository
from app.services.jobs.contracts import AttemptState, StepOutcome, StepStatus
from app.services.jobs.registry import Registry
from app.workers.supervisor import Supervisor, SupervisorConfig
from app.workers.testing import REGISTRY, FixturePublisher

pytestmark = pytest.mark.integration


class IncrementalPublisher(FixturePublisher):
    def __init__(self):
        super().__init__("comparison")

    def publish_step(self, connection, identity, validated, outcome):
        if outcome.status is not StepStatus.COMPLETED:
            return None
        if outcome.output["native_status"] not in ("OPTIMAL", "FEASIBLE"):
            return None
        connection.execute(
            sa.text("INSERT INTO wq_step_fixture_results VALUES (:a,:m) ON CONFLICT DO NOTHING"),
            {"a": identity.attempt_id, "m": outcome.name},
        )
        return {"step": outcome.name, "verified_fixture": True}

    def publish(self, connection, identity, package):
        manifest = super().publish(connection, identity, package)
        count = connection.scalar(
            sa.text("SELECT count(*) FROM wq_step_fixture_results WHERE attempt_id=:a"),
            {"a": identity.attempt_id},
        )
        return {**manifest, "outcome": "SUCCEEDED" if count == 2 else "PARTIAL"}


@pytest.fixture
def incremental(db):
    with db.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE IF NOT EXISTS wq_step_fixture_results "
                "(attempt_id uuid,method text,PRIMARY KEY(attempt_id,method))"
            )
        )
        conn.execute(sa.text("TRUNCATE wq_step_fixture_results"))
    reg = dataclasses.replace(REGISTRY.get("test.comparison.v1"), publisher=IncrementalPublisher())
    registry = Registry([reg])
    repo = QueueRepository(db, registry=registry, profile=TEST_PROFILE)
    driver = FakeDriver(registry=registry)
    sup = Supervisor(repo, registry, driver, SupervisorConfig("test", TEST_PROFILE))
    assert sup.start()
    yield repo, driver, sup
    sup.shutdown_immediate(timeout_s=2)


def pump(sup, condition, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        sup.tick()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("supervisor condition not reached")


def test_checked_first_step_is_durable_before_partner_and_survives_cancel(incremental, scope, db):
    # OR-DEC-011 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    repo, driver, sup = incremental
    accepted = repo.submit(
        scope,
        "test.comparison.v1",
        {
            "methods": {"EGP_PI_INSPIRED": {"sleep_s": 30}},
        },
        str(uuid.uuid4()),
    )
    pump(sup, lambda: len(driver.started) == 2)
    with db.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM wq_step_fixture_results")) == 1
    view = repo.get_job(scope, accepted.job_id)
    assert view.state is AttemptState.RUNNING
    assert "CLASSICAL_GP" in view.attempts[0].diagnostics["published_steps"]
    repo.cancel(scope, accepted.job_id, str(uuid.uuid4()))
    pump(sup, lambda: repo.get_job(scope, accepted.job_id).state is AttemptState.CANCELLED)
    view = repo.get_job(scope, accepted.job_id)
    assert view.attempts[0].diagnostics["result_completeness"] == "ONE_OF_TWO"
    with db.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM wq_step_fixture_results")) == 1
    assert driver.started[1].term_sent


def test_one_readable_method_finishes_partial_without_substitution(incremental, scope, db):
    # OR-DEC-016 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    repo, _, sup = incremental
    accepted = repo.submit(
        scope,
        "test.comparison.v1",
        {
            "methods": {"EGP_PI_INSPIRED": {"native_status": "UNKNOWN"}},
        },
        str(uuid.uuid4()),
    )
    pump(sup, lambda: repo.get_job(scope, accepted.job_id).state is AttemptState.PARTIAL)
    view = repo.get_job(scope, accepted.job_id)
    assert view.attempts[0].result_manifest["outcome"] == "PARTIAL"
    assert view.attempts[0].diagnostics["result_completeness"] == "ONE_OF_TWO"
    with db.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM wq_step_fixture_results")) == 1


def test_late_or_cancelled_step_publication_is_fenced(incremental, scope, db):
    from datetime import timedelta

    repo, _, sup = incremental
    accepted = repo.submit(scope, "test.comparison.v1", {"methods": {}}, str(uuid.uuid4()))
    claim = repo.claim_next(sup.own)
    outcome = StepOutcome("CLASSICAL_GP", StepStatus.COMPLETED, output={"native_status": "OPTIMAL"})
    with pytest.raises(Fenced):
        repo.publish_step(
            sup.own,
            claim,
            {"methods": {}},
            outcome,
            method_deadline_at=claim.started_at - timedelta(seconds=1),
        )
    repo.cancel(scope, accepted.job_id, str(uuid.uuid4()))
    with pytest.raises(Fenced):
        repo.publish_step(sup.own, claim, {"methods": {}}, outcome)
    with db.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM wq_step_fixture_results")) == 0
    repo.finalize(sup.own, claim)


def test_or_manual_retry_creates_linked_new_job_and_preserves_old_terminal(incremental, scope):
    repo, _, sup = incremental
    original_reg = REGISTRY.get("test.echo.v1")
    registration = dataclasses.replace(original_reg, contract="or-allocation-v1")
    registry = Registry([registration])
    queue = QueueRepository(repo.engine, registry=registry, profile=TEST_PROFILE)
    # Advertise the same shared slot's registered OR capability, not another worker.
    advertisement = queue.control().effective_limits
    advertisement["capabilities"]["handler_contracts"] = [registration.contract]
    with repo.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE compute_control SET effective_limits=CAST(:e AS jsonb) "
                "WHERE lane_id='default'"
            ),
            {"e": __import__("json").dumps(advertisement)},
        )
    original = queue.submit(scope, registration.contract, {"value": 1}, str(uuid.uuid4()))
    queue.cancel(scope, original.job_id, str(uuid.uuid4()))
    key = str(uuid.uuid4())
    retried = queue.retry(scope, original.job_id, key)
    assert retried.job_id != original.job_id
    assert retried.attempt_id != original.attempt_id
    assert queue.get_job(scope, original.job_id).state is AttemptState.CANCELLED
    fresh = queue.get_job(scope, retried.job_id)
    assert fresh.retry_of_job_id == original.job_id
    assert fresh.retry_of_attempt_id == original.attempt_id
    assert fresh.attempts[0].attempt_number == 1
    assert queue.retry(scope, original.job_id, key).job_id == retried.job_id
    another_key = queue.retry(scope, original.job_id, str(uuid.uuid4()))
    assert another_key.job_id == retried.job_id
    assert another_key.replayed
    queue.cancel(scope, retried.job_id, str(uuid.uuid4()))


def test_identical_active_or_payloads_reuse_one_job_and_waiting_slot(incremental, scope):
    repo, _, _ = incremental
    registration = dataclasses.replace(REGISTRY.get("test.echo.v1"), contract="or-allocation-v1")
    registry = Registry([registration])
    queue = QueueRepository(repo.engine, registry=registry, profile=TEST_PROFILE)
    advertisement = queue.control().effective_limits
    advertisement["capabilities"]["handler_contracts"] = [registration.contract]
    with repo.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE compute_control SET effective_limits=CAST(:e AS jsonb) "
                "WHERE lane_id='default'"
            ),
            {"e": __import__("json").dumps(advertisement)},
        )
    first = queue.submit(scope, registration.contract, {"value": 1}, str(uuid.uuid4()))
    duplicate = queue.submit(scope, registration.contract, {"value": 1}, str(uuid.uuid4()))
    assert first.job_id == duplicate.job_id
    assert first.attempt_id == duplicate.attempt_id
    assert duplicate.replayed
    with repo.engine.connect() as conn:
        assert (
            conn.scalar(sa.text("SELECT count(*) FROM compute_attempts WHERE state='QUEUED'")) == 1
        )
    queue.cancel(scope, first.job_id, str(uuid.uuid4()))
