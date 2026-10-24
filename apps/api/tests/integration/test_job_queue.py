"""WQ-02/05 queue repository against real PostgreSQL: admission, idempotency, FIFO, expiry,
claims, fencing, cancellation, retry and fenced publication (WQ-T05–T10, T19–T21)."""

import threading
import time
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from wq_support import TEST_PROFILE, advertisement, echo, make_ready

from app.repositories.jobs import (
    AdmissionRejected,
    CommitUncertain,
    Fenced,
    IdempotencyConflict,
    JobNotFound,
    JobStateConflict,
    OwnershipLost,
    QueueRepository,
    TrustedScope,
)
from app.services.jobs.contracts import (
    AttemptState,
    ReasonCode,
    StepOutcome,
    StepStatus,
    SupervisorState,
)
from app.services.jobs.registry import InputRejected, PublicationRejected
from app.workers.testing import FIXTURE_LABEL, REGISTRY

pytestmark = pytest.mark.integration
ECHO = "test.echo.v1"


def submit(repo, scope, key=None, value=1, contract=ECHO, **behavior):
    return repo.submit(scope, contract, echo(value, **behavior), key or str(uuid.uuid4()))


def echo_package(claim, value=1):
    reg = REGISTRY.get(claim.contract)
    outcome = StepOutcome(
        name="TEST_METHOD",
        status=StepStatus.COMPLETED,
        output={"value": value, "label": FIXTURE_LABEL},
    )
    return reg.publisher.validate(claim.input_package["input"], [outcome])


def queued_count(engine):
    with engine.connect() as conn:
        return conn.scalar(sa.text("SELECT count(*) FROM compute_attempts WHERE state='QUEUED'"))


def age_heartbeat(engine, seconds):
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE compute_control SET heartbeat_at = clock_timestamp()"
                " - make_interval(secs => :s)"
            ),
            {"s": seconds},
        )


# --- admission ---------------------------------------------------------------------------


def test_submission_is_durable_and_projected(repo, scope):
    make_ready(repo)
    accepted = submit(repo, scope)
    assert accepted.state is AttemptState.QUEUED and not accepted.replayed
    view = repo.get_job(scope, accepted.job_id)
    assert view.state is AttemptState.QUEUED
    assert [a.attempt_number for a in view.attempts] == [1]
    assert view.attempts[0].queue_deadline_at > view.attempts[0].enqueued_at
    events = [e["event_type"] for e in repo.audit_events(accepted.job_id)]
    assert events == ["COMMAND_ACCEPTED"]


def test_no_supervisor_means_unavailable(repo, scope):
    with pytest.raises(AdmissionRejected) as err:
        submit(repo, scope)
    assert err.value.code == "COMPUTE_UNAVAILABLE"
    assert queued_count(repo.engine) == 0


@pytest.mark.parametrize("age", [2.0, 2.5])
def test_stale_heartbeat_rejects_at_the_boundary(repo, scope, age):
    make_ready(repo)
    age_heartbeat(repo.engine, age)
    with pytest.raises(AdmissionRejected) as err:
        submit(repo, scope)
    assert err.value.code == "COMPUTE_UNAVAILABLE"


def test_fresh_heartbeat_admits(repo, scope):
    make_ready(repo)
    age_heartbeat(repo.engine, 1.5)
    submit(repo, scope)


def test_future_heartbeat_fails_closed(repo, scope):
    make_ready(repo)
    age_heartbeat(repo.engine, -5)
    with pytest.raises(AdmissionRejected):
        submit(repo, scope)


def test_unadvertised_contract_or_missing_containment_is_unavailable(repo, scope):
    make_ready(repo, contracts=["test.forecast.v1"])
    with pytest.raises(AdmissionRejected) as err:
        submit(repo, scope)
    assert err.value.code == "COMPUTE_UNAVAILABLE"


def test_invalid_input_is_rejected_before_admission(repo, scope):
    make_ready(repo)
    with pytest.raises(InputRejected):
        repo.submit(scope, ECHO, {"value": "x", "behavior": {}}, "k1")
    with pytest.raises(InputRejected):
        repo.submit(scope, "unknown.v1", {}, "k2")
    with pytest.raises(InputRejected):
        repo.submit(scope, ECHO, echo(), "bad key with spaces")
    assert queued_count(repo.engine) == 0


def test_healthy_busy_admits_two_waiters_then_reports_full(repo, scope):
    own = make_ready(repo)
    submit(repo, scope)
    assert repo.claim_next(own) is not None
    submit(repo, scope)
    submit(repo, scope)
    with pytest.raises(AdmissionRejected) as err:
        submit(repo, scope)
    assert err.value.code == "COMPUTE_QUEUE_FULL"


def test_idle_lane_with_two_waiters_rejects_a_third(repo, scope):
    make_ready(repo)
    submit(repo, scope)
    submit(repo, scope)
    with pytest.raises(AdmissionRejected) as err:
        submit(repo, scope)
    assert err.value.code == "COMPUTE_QUEUE_FULL"


def _concurrently(n, fn):
    barrier = threading.Barrier(n)
    results = [None] * n

    def run(i):
        barrier.wait()
        try:
            results[i] = fn(i)
        except Exception as exc:  # noqa: BLE001 - collected for assertions
            results[i] = exc

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return results


def test_concurrent_submissions_never_exceed_two_waiters(repo, scope):  # WQ-T05
    make_ready(repo)
    results = _concurrently(8, lambda i: submit(repo, scope, key=f"k-{i}"))
    accepted = [r for r in results if not isinstance(r, Exception)]
    rejected = [r for r in results if isinstance(r, AdmissionRejected)]
    assert len(accepted) == 2 and len(rejected) == 6
    assert {r.code for r in rejected} == {"COMPUTE_QUEUE_FULL"}
    assert queued_count(repo.engine) == 2


def test_concurrent_identical_command_creates_one_job(repo, scope):  # WQ-T06
    make_ready(repo)
    results = _concurrently(6, lambda i: submit(repo, scope, key="same-key"))
    assert not [r for r in results if isinstance(r, Exception)], results
    assert len({r.job_id for r in results}) == 1
    assert sum(1 for r in results if not r.replayed) == 1
    with repo.engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM compute_jobs")) == 1
        assert conn.scalar(sa.text("SELECT count(*) FROM compute_commands")) == 1
    with pytest.raises(IdempotencyConflict):
        submit(repo, scope, key="same-key", value=2)


def test_same_key_in_another_organization_is_independent(repo, scope):
    make_ready(repo)
    a = submit(repo, scope, key="shared")
    other = TrustedScope(organization_id=uuid.uuid4(), actor_ref="other")
    b = submit(repo, other, key="shared")
    assert a.job_id != b.job_id


def test_rejected_admission_consumes_no_key_and_replay_survives_outage(repo, scope):  # WQ-T07
    own = make_ready(repo)
    submit(repo, scope)
    submit(repo, scope)
    with pytest.raises(AdmissionRejected):
        submit(repo, scope, key="later")
    claim = repo.claim_next(own)
    accepted = submit(repo, scope, key="later")
    assert not accepted.replayed
    # Response lost; compute now unavailable; the client retries the same command.
    repo.set_state(own, SupervisorState.DRAINING)
    replay = submit(repo, scope, key="later")
    assert replay.replayed and replay.job_id == accepted.job_id
    assert claim is not None


def test_storage_failure_is_not_durable_acceptance(scope):
    broken = QueueRepository(
        sa.create_engine(
            "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none_test",
            connect_args={"connect_timeout": 1},
        ),
        registry=REGISTRY,
        profile=TEST_PROFILE,
    )
    with pytest.raises(Exception) as err:
        submit(broken, scope)
    assert getattr(err.value, "code", None) == "QUEUE_STORAGE_UNAVAILABLE"


# --- FIFO, expiry, restart ----------------------------------------------------------------


def test_fifo_with_equal_enqueue_time_tie_and_retry_at_tail(repo, scope):  # WQ-T09
    own = make_ready(repo)
    a = submit(repo, scope)
    b = submit(repo, scope)
    first = repo.claim_next(own)
    assert first.attempt_id == a.attempt_id
    repo.finalize(own, first, failure_reason=ReasonCode.HANDLER_FAILED)
    retried = repo.retry(scope, a.job_id, "retry-a")
    assert retried.attempt_id != a.attempt_id
    assert repo.claim_next(own).attempt_id == b.attempt_id


def test_equal_enqueue_times_order_by_attempt_id(engine, repo, scope):
    own = make_ready(repo)
    ids = [submit(repo, scope).attempt_id for _ in range(2)]
    with engine.begin() as conn:
        conn.execute(sa.text("ALTER TABLE compute_attempts DISABLE TRIGGER USER"))
        conn.execute(
            sa.text(
                "UPDATE compute_attempts SET enqueued_at = timestamptz '2026-10-24 12:00:00+00',"
                " queue_deadline_at = clock_timestamp() + interval '1 minute'"
            )
        )
        conn.execute(sa.text("ALTER TABLE compute_attempts ENABLE TRIGGER USER"))
    assert repo.claim_next(own).attempt_id == min(ids, key=lambda u: str(u))


def test_queued_work_survives_restart_and_expired_work_never_starts(db, scope):  # WQ-T10
    import dataclasses

    short = dataclasses.replace(TEST_PROFILE, queue_wait_s=0.6)
    repo = QueueRepository(db, registry=REGISTRY, profile=short)
    own = make_ready(repo)  # the supervisor survives an API restart
    kept = submit(repo, scope)
    repo2 = QueueRepository(db, registry=REGISTRY, profile=short)  # "restarted" API
    assert repo2.get_job(scope, kept.job_id).state is AttemptState.QUEUED
    time.sleep(0.7)
    # A saved read never mutates state, even past the deadline.
    assert repo2.get_job(scope, kept.job_id).state is AttemptState.QUEUED
    assert repo2.claim_next(own) is None
    view = repo2.get_job(scope, kept.job_id)
    assert view.state is AttemptState.EXPIRED
    assert view.attempts[0].reason_code == "QUEUE_DEADLINE_REACHED"
    assert view.attempts[0].started_at is None


# --- ownership, heartbeat, fencing --------------------------------------------------------


def test_second_supervisor_cannot_take_a_fresh_lane(repo):  # WQ-T08
    own = make_ready(repo)
    assert (
        repo.acquire_ownership(
            supervisor_id=uuid.uuid4(), host_identity="h2", effective_limits=advertisement()
        )
        is None
    )
    assert repo.heartbeat(own)


def test_stale_owner_is_fenced_after_takeover(repo, scope):  # WQ-T08
    old = make_ready(repo)
    submit(repo, scope)
    claim = repo.claim_next(old)
    age_heartbeat(repo.engine, 5)
    new = repo.acquire_ownership(
        supervisor_id=uuid.uuid4(), host_identity="h2", effective_limits=advertisement()
    )
    assert new is not None and new.generation == old.generation + 1
    assert repo.control().state is SupervisorState.RECOVERING
    assert repo.control().recovery_required
    assert not repo.heartbeat(old)
    with pytest.raises((Fenced, OwnershipLost)):
        repo.publish(old, claim, echo_package(claim))
    with pytest.raises(OwnershipLost):
        repo.finalize(old, claim, failure_reason=ReasonCode.HANDLER_FAILED)
    with repo.engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM wq_fixture_results")) == 0


def test_recovery_marks_lost_attempts_stopping_and_requires_evidence(repo, scope):
    old = make_ready(repo)
    job = submit(repo, scope)
    other = submit(repo, scope)
    claim = repo.claim_next(old)
    age_heartbeat(repo.engine, 5)
    new = repo.acquire_ownership(
        supervisor_id=uuid.uuid4(), host_identity="h2", effective_limits=advertisement()
    )
    items = repo.begin_recovery(new)
    assert [i.attempt_id for i in items] == [claim.attempt_id]
    assert repo.read_attempt(claim.attempt_id).state is AttemptState.STOPPING
    assert not repo.finish_recovery(new)  # slot still occupied
    state = repo.finalize_recovered(new, claim.attempt_id, {"method": "TEST_EVIDENCE"})
    assert state is AttemptState.INTERRUPTED
    assert repo.finish_recovery(new)
    assert repo.set_state(new, SupervisorState.READY)
    assert repo.get_job(scope, job.job_id).state is AttemptState.INTERRUPTED
    assert repo.get_job(scope, other.job_id).state is AttemptState.QUEUED
    assert repo.control().active_attempt_id is None


def test_quarantine_keeps_slot_and_blocks_admission(repo, scope):
    old = make_ready(repo)
    submit(repo, scope)
    claim = repo.claim_next(old)
    age_heartbeat(repo.engine, 5)
    new = repo.acquire_ownership(
        supervisor_id=uuid.uuid4(), host_identity="h2", effective_limits=advertisement()
    )
    repo.begin_recovery(new)
    assert repo.quarantine(new, "BOUNDARY_UNVERIFIABLE")
    ctl = repo.control()
    assert ctl.state is SupervisorState.QUARANTINED and ctl.active_attempt_id == claim.attempt_id
    with pytest.raises(AdmissionRejected):
        submit(repo, scope)
    state = repo.operator_attest_cleanup(claim.attempt_id, "operator-1", "container removed")
    assert state is AttemptState.INTERRUPTED
    attempt = repo.read_attempt(claim.attempt_id)
    assert attempt.diagnostics["recovery_evidence"]["method"] == "OPERATOR_ATTESTATION"
    assert not repo.control().recovery_required


# --- claim, cancel, retry ------------------------------------------------------------------


def test_claim_sets_fixed_deadlines_and_occupies_the_slot(repo, scope):
    own = make_ready(repo)
    submit(repo, scope)
    claim = repo.claim_next(own)
    assert claim.budget_s == TEST_PROFILE.allocation_total_s
    delta = (claim.execution_deadline_at - claim.started_at).total_seconds()
    assert delta == pytest.approx(TEST_PROFILE.allocation_total_s, abs=1e-3)
    assert repo.control().active_attempt_id == claim.attempt_id
    assert repo.claim_next(own) is None  # one active at a time


def test_forecast_claim_records_primary_deadline(repo, scope):
    own = make_ready(repo)
    repo.submit(scope, "test.forecast.v1", {"fallback_allowed": True}, "f1")
    claim = repo.claim_next(own)
    delta = (claim.primary_deadline_at - claim.started_at).total_seconds()
    assert delta == pytest.approx(TEST_PROFILE.forecast_primary_cutoff_s, abs=1e-3)


def test_tampered_input_fails_before_any_boundary(engine, repo, scope):
    own = make_ready(repo)
    accepted = submit(repo, scope)
    with engine.begin() as conn:
        conn.execute(sa.text("ALTER TABLE compute_jobs DISABLE TRIGGER USER"))
        conn.execute(sa.text("UPDATE compute_jobs SET input_package = '{\"input\": {}}'"))
        conn.execute(sa.text("ALTER TABLE compute_jobs ENABLE TRIGGER USER"))
    assert repo.claim_next(own) is None
    attempt = repo.get_job(scope, accepted.job_id).attempts[0]
    assert attempt.state is AttemptState.FAILED and attempt.reason_code == "INPUT_INTEGRITY"
    assert attempt.started_at is None


def test_cancel_queued_is_idempotent(repo, scope):
    make_ready(repo)
    accepted = submit(repo, scope)
    first = repo.cancel(scope, accepted.job_id, "c1")
    assert first.state is AttemptState.CANCELLED and first.completed
    again = repo.cancel(scope, accepted.job_id, "c1")
    assert again.replayed and again.state is AttemptState.CANCELLED
    with pytest.raises(JobStateConflict):
        repo.cancel(scope, accepted.job_id, "c2")


def test_cancel_running_requests_stop_and_fences_publication(repo, scope):  # WQ-T21
    own = make_ready(repo)
    accepted = submit(repo, scope)
    claim = repo.claim_next(own)
    result = repo.cancel(scope, accepted.job_id, "c1")
    assert result.state is AttemptState.STOPPING and not result.completed
    with pytest.raises(Fenced):
        repo.publish(own, claim, echo_package(claim))
    assert repo.finalize(own, claim) is AttemptState.CANCELLED
    assert repo.control().active_attempt_id is None


def test_cancel_after_publication_is_a_conflict_and_keeps_results(repo, scope):
    own = make_ready(repo)
    accepted = submit(repo, scope)
    claim = repo.claim_next(own)
    manifest = repo.publish(own, claim, echo_package(claim))
    assert manifest["label"] == FIXTURE_LABEL
    with pytest.raises(JobStateConflict):
        repo.cancel(scope, accepted.job_id, "late")
    assert repo.get_job(scope, accepted.job_id).state is AttemptState.SUCCEEDED


def test_queued_cancel_versus_claim_has_one_winner(repo, scope):  # WQ-T21
    own = make_ready(repo)
    for _ in range(5):
        accepted = submit(repo, scope)

        def race(i, job_id=accepted.job_id):
            if i == 0:
                return repo.claim_next(own)
            return repo.cancel(scope, job_id, str(uuid.uuid4()))

        results = _concurrently(2, race)
        claim, cancel = results
        state = repo.get_job(scope, accepted.job_id).state
        if claim is None:
            assert state is AttemptState.CANCELLED and cancel.completed
        else:
            assert state is AttemptState.STOPPING and not cancel.completed
            repo.finalize(own, claim)
        assert repo.get_job(scope, accepted.job_id).state is AttemptState.CANCELLED


def test_retry_creates_linked_attempt_with_unchanged_input(repo, scope):
    own = make_ready(repo)
    accepted = submit(repo, scope)
    claim = repo.claim_next(own)
    repo.finalize(own, claim, failure_reason=ReasonCode.HANDLER_FAILED)
    retried = repo.retry(scope, accepted.job_id, "r0")
    assert repo.retry(scope, accepted.job_id, "r0").replayed
    with pytest.raises(JobStateConflict):
        repo.retry(scope, accepted.job_id, "r0b")  # the new attempt is still queued
    view = repo.get_job(scope, accepted.job_id)
    assert view.current_attempt_id == retried.attempt_id
    assert [a.attempt_number for a in view.attempts] == [1, 2]
    first, second = view.attempts
    assert first.state is AttemptState.FAILED and second.state is AttemptState.QUEUED
    assert view.input_sha256 == repo.get_job(scope, accepted.job_id).input_sha256
    assert second.enqueued_at > first.enqueued_at


def test_retry_rules(repo, scope):
    own = make_ready(repo)
    accepted = submit(repo, scope)
    with pytest.raises(JobStateConflict):
        repo.retry(scope, accepted.job_id, "while-queued")
    claim = repo.claim_next(own)
    repo.publish(own, claim, echo_package(claim))
    with pytest.raises(JobStateConflict):
        repo.retry(scope, accepted.job_id, "after-success")
    with pytest.raises(JobNotFound):
        repo.retry(TrustedScope(uuid.uuid4(), "x"), accepted.job_id, "other-org")


def test_jobs_are_scoped_by_organization(repo, scope):
    make_ready(repo)
    accepted = submit(repo, scope)
    with pytest.raises(JobNotFound):
        repo.get_job(TrustedScope(uuid.uuid4(), "x"), accepted.job_id)
    with pytest.raises(JobNotFound):
        repo.cancel(TrustedScope(uuid.uuid4(), "x"), accepted.job_id, "c")


# --- publication -----------------------------------------------------------------------------


def test_publication_commits_result_manifest_and_releases_slot(repo, scope):
    own = make_ready(repo)
    accepted = submit(repo, scope, value=7)
    claim = repo.claim_next(own)
    manifest = repo.publish(own, claim, echo_package(claim, value=7))
    view = repo.get_job(scope, accepted.job_id)
    assert view.state is AttemptState.SUCCEEDED
    assert view.attempts[0].result_manifest == manifest
    assert view.attempts[0].cleanup_confirmed_at is not None
    assert repo.control().active_attempt_id is None
    with repo.engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT label, payload FROM wq_fixture_results")).all()
    assert rows[0][0] == FIXTURE_LABEL and rows[0][1]["outputs"][0]["value"] == 7
    events = [e["event_type"] for e in repo.audit_events(accepted.job_id)]
    assert events == ["COMMAND_ACCEPTED", "ATTEMPT_CLAIMED", "ATTEMPT_PUBLISHED"]


def test_publisher_failure_rolls_back_everything(repo, scope):  # WQ-T19
    own = make_ready(repo)
    accepted = repo.submit(scope, ECHO, {**echo(), "publish_fail": True}, "pf")
    claim = repo.claim_next(own)
    with pytest.raises(PublicationRejected):
        repo.publish(own, claim, echo_package(claim))
    assert repo.read_attempt(claim.attempt_id).state is AttemptState.RUNNING
    assert repo.control().active_attempt_id == claim.attempt_id
    with repo.engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM wq_fixture_results")) == 0
    state = repo.finalize(own, claim, failure_reason=ReasonCode.PUBLICATION_REJECTED)
    assert state is AttemptState.FAILED
    assert repo.get_job(scope, accepted.job_id).attempts[0].result_manifest is None


def test_publication_after_execution_deadline_is_fenced(engine, repo, scope):
    own = make_ready(repo)
    submit(repo, scope)
    claim = repo.claim_next(own)
    with engine.begin() as conn:
        conn.execute(sa.text("ALTER TABLE compute_attempts DISABLE TRIGGER USER"))
        conn.execute(
            sa.text(
                "UPDATE compute_attempts"
                " SET execution_deadline_at = started_at + interval '1 microsecond'"
            )
        )
        conn.execute(sa.text("ALTER TABLE compute_attempts ENABLE TRIGGER USER"))
    with pytest.raises(Fenced):
        repo.publish(own, claim, echo_package(claim))


class _CommitThenLose(QueueRepository):
    def _commit(self, transaction):
        transaction.commit()
        raise OperationalError("COMMIT", {}, Exception("connection lost after commit"))


class _LoseBeforeCommit(QueueRepository):
    def _commit(self, transaction):
        transaction.rollback()
        raise OperationalError("COMMIT", {}, Exception("connection lost before commit"))


@pytest.mark.parametrize(
    ("cls", "expected"), [(_CommitThenLose, "COMMITTED"), (_LoseBeforeCommit, "ABSENT")]
)
def test_commit_uncertainty_reconciles_by_identity(db, scope, cls, expected):  # WQ-T20
    repo = cls(db, registry=REGISTRY, profile=TEST_PROFILE)
    plain = QueueRepository(db, registry=REGISTRY, profile=TEST_PROFILE)
    own = make_ready(plain)
    accepted = submit(plain, scope)
    claim = plain.claim_next(own)
    with pytest.raises(CommitUncertain):
        repo.publish(own, claim, echo_package(claim))
    assert plain.reconcile_publication(own, claim) == expected
    with db.connect() as conn:
        results = conn.scalar(sa.text("SELECT count(*) FROM wq_fixture_results"))
    if expected == "COMMITTED":
        assert plain.get_job(scope, accepted.job_id).state is AttemptState.SUCCEEDED
        assert results == 1
    else:
        assert results == 0
        state = plain.finalize(own, claim, failure_reason=ReasonCode.PUBLICATION_COMMIT_LOST)
        assert state is AttemptState.FAILED
    events = [e["event_type"] for e in plain.audit_events(accepted.job_id)]
    assert "PUBLICATION_RECONCILED" in events
