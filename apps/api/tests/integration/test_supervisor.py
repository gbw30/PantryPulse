"""WQ-03/05 supervisor against real PostgreSQL with a deterministic fake boundary.

Covers ownership/heartbeat (WQ-T08, T11), deadlines and phases (T15–T18), cancellation
(T21), worker loss/quarantine (T13, T14 policy side), shutdown (T22) and spawn/overflow
failures (T23). Real process containment is covered by the Linux-only tests.
"""

import dataclasses
import time
import uuid

import pytest
import sqlalchemy as sa
from fake_driver import FakeDriver

from app.repositories.jobs import (
    OwnershipLost,
    QueueRepository,
    QueueStorageUnavailable,
    TrustedScope,
)
from app.services.jobs.contracts import (
    AttemptState,
    OperationKind,
    RuntimeProfile,
    SupervisorState,
)
from app.services.jobs.registry import PublicationRejected, Registration, Registry
from app.workers.supervisor import Supervisor, SupervisorConfig
from app.workers.testing import REGISTRY, EchoHandler, FixturePublisher

pytestmark = pytest.mark.integration

PROFILE = RuntimeProfile(
    queue_wait_s=30,
    heartbeat_interval_s=0.2,
    heartbeat_stale_s=1.5,
    forecast_total_s=3,
    forecast_primary_cutoff_s=1.5,
    allocation_total_s=2,
    method_wall_s=2,
    method_search_s=1,
    comparison_total_s=4.5,
    stop_grace_s=0.2,
    publication_reserve_s=0.3,
    kill_margin_s=0.1,
    method_min_s=0.3,
)


@pytest.fixture
def q(db):
    return QueueRepository(db, registry=REGISTRY, profile=PROFILE)


@pytest.fixture
def org():
    return TrustedScope(organization_id=uuid.uuid4(), actor_ref="presenter")


_created = []


@pytest.fixture(autouse=True)
def _close_supervisors():
    yield
    while _created:
        _created.pop().close()


def make_sup(q, driver=None, profile=PROFILE, **cfg):
    driver = driver or FakeDriver(registry=REGISTRY)
    config = SupervisorConfig(registry_name="test", profile=profile, tick_s=0.02, **cfg)
    sup = Supervisor(q, REGISTRY, driver, config)
    _created.append(sup)
    return sup, driver


def started(q, driver=None, **kw):
    sup, driver = make_sup(q, driver, **kw)
    assert sup.start()
    return sup, driver


def run_until(sup, predicate, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        sup.tick()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached")


def job_state(q, org, job_id):
    return q.get_job(org, job_id).state


def settled(q, org, job_id):
    return lambda: (
        job_state(q, org, job_id)
        not in (
            AttemptState.QUEUED,
            AttemptState.RUNNING,
            AttemptState.STOPPING,
        )
    )


def submit(q, org, contract="test.echo.v1", payload=None):
    payload = payload if payload is not None else {"value": 3, "behavior": {}}
    return q.submit(org, contract, payload, str(uuid.uuid4()))


# --- lifecycle --------------------------------------------------------------------------


def test_incapable_host_never_reports_ready(q):
    sup, _ = make_sup(q, FakeDriver(registry=REGISTRY, capable=False))
    assert not sup.start()
    assert q.control().state is SupervisorState.OFFLINE


def test_start_advertises_limits_contracts_and_containment(q):
    sup, _ = started(q)
    ctl = q.control()
    assert ctl.state is SupervisorState.READY
    caps = ctl.effective_limits["capabilities"]
    assert caps["process_containment"] is True
    assert caps["handler_contracts"] == list(REGISTRY.contracts())
    assert ctl.effective_limits["limits"]["comparison_total_s"] == 4.5
    sup.shutdown_drain()


def test_second_supervisor_exits_without_changing_ownership(q):  # WQ-T08
    first, _ = started(q)
    generation = q.control().generation
    second, _ = make_sup(q)
    assert not second.start()
    assert q.control().generation == generation
    first.shutdown_drain()


def test_success_publishes_and_records_the_boundary(q, org):
    sup, driver = started(q)
    accepted = submit(q, org)
    run_until(sup, settled(q, org, accepted.job_id))
    view = q.get_job(org, accepted.job_id)
    assert view.state is AttemptState.SUCCEEDED
    assert view.attempts[0].result_manifest["label"] == "TEST_INFRASTRUCTURE_ARTIFACT"
    assert view.attempts[0].execution_boundary["kind"] == "linux_process_group"
    assert len(driver.started) == 1
    assert q.control().active_attempt_id is None
    sup.shutdown_drain()


def test_heartbeat_advances_while_a_child_is_busy(q, org):  # WQ-T11
    sup, _ = started(q)
    accepted = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 1.2}})
    run_until(sup, lambda: job_state(q, org, accepted.job_id) is AttemptState.RUNNING)
    first = q.control().heartbeat_at
    time.sleep(0.6)
    sup.tick()
    assert q.control().heartbeat_at > first
    # A saved read stays available while busy.
    assert q.get_job(org, accepted.job_id).state is AttemptState.RUNNING
    run_until(sup, settled(q, org, accepted.job_id))
    sup.shutdown_drain()


# --- deadlines and phases -----------------------------------------------------------------


def test_method_cap_times_out_the_attempt(q, org):  # WQ-T04/T17
    sup, driver = started(q)
    accepted = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 30}})
    t0 = time.monotonic()
    run_until(sup, settled(q, org, accepted.job_id))
    assert time.monotonic() - t0 < PROFILE.allocation_total_s + 1.0
    attempt = q.get_job(org, accepted.job_id).attempts[0]
    assert attempt.state is AttemptState.TIMED_OUT
    assert driver.started[0].term_sent and attempt.result_manifest is None
    sup.shutdown_drain()


def test_sigterm_ignoring_child_is_force_stopped(q, org):
    sup, driver = started(q)
    accepted = submit(
        q, org, payload={"value": 1, "behavior": {"sleep_s": 30, "ignore_sigterm": True}}
    )
    run_until(sup, settled(q, org, accepted.job_id))
    assert driver.started[0].killed
    assert job_state(q, org, accepted.job_id) is AttemptState.TIMED_OUT
    sup.shutdown_drain()


def test_primary_is_stopped_by_cutoff_and_fallback_shares_budget(q, org):  # WQ-T15
    sup, driver = started(q)
    accepted = submit(
        q,
        org,
        "test.forecast.v1",
        {"fallback_allowed": True, "primary": {"sleep_s": 30}, "fallback": {"sleep_s": 0.2}},
    )
    t0 = time.monotonic()
    run_until(sup, settled(q, org, accepted.job_id))
    total = time.monotonic() - t0
    view = q.get_job(org, accepted.job_id)
    assert view.state is AttemptState.SUCCEEDED
    manifest_steps = _fixture_payload(q, view.attempts[0].attempt_id)["steps"]
    assert [s["status"] for s in manifest_steps] == ["TIMED_OUT", "COMPLETED"]
    assert manifest_steps[0]["elapsed_s"] <= PROFILE.forecast_primary_cutoff_s
    assert _fixture_payload(q, view.attempts[0].attempt_id)["outputs"][0]["provider"] == (
        "test-fallback"
    )
    assert total < PROFILE.forecast_total_s
    assert [h.step for h in driver.started] == ["primary", "fallback"]
    sup.shutdown_drain()


def test_classified_primary_failure_falls_back_early(q, org):  # WQ-T16
    sup, _ = started(q)
    accepted = submit(
        q,
        org,
        "test.forecast.v1",
        {"fallback_allowed": True, "primary": {"fail": "classified"}, "fallback": {}},
    )
    t0 = time.monotonic()
    run_until(sup, settled(q, org, accepted.job_id))
    assert time.monotonic() - t0 < 1.0
    steps = _fixture_payload(q, q.get_job(org, accepted.job_id).attempts[0].attempt_id)["steps"]
    assert steps[0]["error_code"] == "TEST_PROVIDER_FAILURE"
    sup.shutdown_drain()


def test_programming_error_is_not_hidden_by_fallback(q, org):  # WQ-T16
    sup, driver = started(q)
    accepted = submit(
        q,
        org,
        "test.forecast.v1",
        {"fallback_allowed": True, "primary": {"fail": "error"}, "fallback": {}},
    )
    run_until(sup, settled(q, org, accepted.job_id))
    attempt = q.get_job(org, accepted.job_id).attempts[0]
    assert attempt.state is AttemptState.FAILED
    assert attempt.reason_code == "HANDLER_FAILED"
    assert [h.step for h in driver.started] == ["primary"]
    sup.shutdown_drain()


def test_no_fallback_allowed_means_primary_timeout_times_out(q, org):
    sup, _ = started(q)
    accepted = submit(
        q, org, "test.forecast.v1", {"fallback_allowed": False, "primary": {"sleep_s": 30}}
    )
    run_until(sup, settled(q, org, accepted.job_id))
    assert job_state(q, org, accepted.job_id) is AttemptState.TIMED_OUT
    sup.shutdown_drain()


def test_comparison_runs_methods_sequentially_with_equal_settings(q, org):  # WQ-T17
    sup, driver = started(q)
    accepted = submit(
        q,
        org,
        "test.comparison.v1",
        {"methods": {"CLASSICAL_GP": {"sleep_s": 0.2}, "EGP_PI_INSPIRED": {"sleep_s": 0.2}}},
    )
    run_until(sup, settled(q, org, accepted.job_id))
    view = q.get_job(org, accepted.job_id)
    assert view.state is AttemptState.SUCCEEDED
    assert [h.step for h in driver.started] == ["CLASSICAL_GP", "EGP_PI_INSPIRED"]
    first, second = driver.started
    assert second.finish_at >= first.finish_at  # second started only after the first ended
    methods = _fixture_payload(q, view.attempts[0].attempt_id)["methods"]
    assert [m["native_status"] for m in methods] == ["OPTIMAL", "OPTIMAL"]
    sup.shutdown_drain()


def test_comparison_records_not_run_when_parent_budget_is_spent(q, org):  # WQ-T17
    tight = dataclasses.replace(PROFILE, comparison_total_s=2.4)
    qq = QueueRepository(q.engine, registry=REGISTRY, profile=tight)
    sup, driver = started(qq, profile=tight)
    accepted = submit(
        qq,
        org,
        "test.comparison.v1",
        {"methods": {"CLASSICAL_GP": {"sleep_s": 30}, "EGP_PI_INSPIRED": {}}},
    )
    run_until(sup, settled(qq, org, accepted.job_id))
    assert [h.step for h in driver.started] == ["CLASSICAL_GP"]
    assert job_state(qq, org, accepted.job_id) is AttemptState.TIMED_OUT
    sup.shutdown_drain()


def test_invalid_native_status_cannot_publish_and_infeasible_is_not_a_plan(q, org):  # WQ-T18
    sup, _ = started(q)
    bad = submit(
        q,
        org,
        "test.comparison.v1",
        {"methods": {"CLASSICAL_GP": {"native_status": "optimal"}, "EGP_PI_INSPIRED": {}}},
    )
    run_until(sup, settled(q, org, bad.job_id))
    attempt = q.get_job(org, bad.job_id).attempts[0]
    assert attempt.state is AttemptState.FAILED and attempt.reason_code == "OUTPUT_INVALID"
    ok = submit(
        q,
        org,
        "test.comparison.v1",
        {"methods": {"CLASSICAL_GP": {"native_status": "INFEASIBLE"}, "EGP_PI_INSPIRED": {}}},
    )
    run_until(sup, settled(q, org, ok.job_id))
    view = q.get_job(org, ok.job_id)
    assert view.state is AttemptState.SUCCEEDED
    methods = _fixture_payload(q, view.attempts[0].attempt_id)["methods"]
    assert methods[0] == {
        "method": "CLASSICAL_GP",
        "step_status": "COMPLETED",
        "native_status": "INFEASIBLE",
        "candidate_readable": False,
    }
    sup.shutdown_drain()


# --- failures ------------------------------------------------------------------------------


def test_child_crash_fails_with_a_classified_reason(q, org):
    sup, _ = started(q)
    accepted = submit(q, org, payload={"value": 1, "behavior": {"fail": "crash"}})
    run_until(sup, settled(q, org, accepted.job_id))
    attempt = q.get_job(org, accepted.job_id).attempts[0]
    assert attempt.state is AttemptState.FAILED
    assert attempt.reason_code == "CHILD_EXITED_ABNORMALLY"


def test_oversized_output_fails_without_truncated_success(q, org):  # WQ-T23
    sup, _ = started(q)
    accepted = submit(q, org, payload={"value": 1, "behavior": {"output_bytes": 200_000}})
    run_until(sup, settled(q, org, accepted.job_id))
    attempt = q.get_job(org, accepted.job_id).attempts[0]
    assert attempt.state is AttemptState.FAILED and attempt.reason_code == "OUTPUT_TOO_LARGE"
    sup.shutdown_drain()


def test_spawn_failure_records_a_failed_attempt_and_frees_the_slot(q, org):
    sup, driver = started(q)
    driver.fail_spawn = True
    accepted = submit(q, org)
    run_until(sup, settled(q, org, accepted.job_id))
    attempt = q.get_job(org, accepted.job_id).attempts[0]
    assert attempt.state is AttemptState.FAILED and attempt.reason_code == "SPAWN_FAILED"
    assert q.control().active_attempt_id is None
    sup.shutdown_drain()


def test_cancel_running_stops_the_child_and_ends_cancelled(q, org):  # WQ-T21
    sup, driver = started(q)
    accepted = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 30}})
    run_until(sup, lambda: len(driver.started) == 1)
    assert not q.cancel(org, accepted.job_id, "cancel-1").completed
    run_until(sup, settled(q, org, accepted.job_id))
    assert job_state(q, org, accepted.job_id) is AttemptState.CANCELLED
    assert driver.started[0].term_sent
    sup.shutdown_drain()


def test_unconfirmed_cleanup_quarantines_and_keeps_the_slot(q, org):  # WQ-T12 policy
    sup, driver = started(q, stop_confirm_timeout_s=0.5)
    driver.stuck_steps.add("TEST_METHOD")  # leader exits but a group member lingers
    accepted = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 0.1}})
    run_until(sup, lambda: q.control().state is SupervisorState.QUARANTINED, timeout=15)
    ctl = q.control()
    assert ctl.active_attempt_id == q.get_job(org, accepted.job_id).current_attempt_id
    with pytest.raises(Exception) as err:
        submit(q, org)
    assert getattr(err.value, "code", "") == "COMPUTE_UNAVAILABLE"
    driver.stuck_steps.clear()  # the boundary finally empties
    run_until(sup, lambda: q.control().state is SupervisorState.READY, timeout=15)
    attempt = q.get_job(org, accepted.job_id).attempts[0]
    assert attempt.state is AttemptState.FAILED and attempt.reason_code == "CLEANUP_UNCONFIRMED"
    sup.shutdown_drain()


# --- worker loss, recovery, shutdown --------------------------------------------------------


def _age_heartbeat(q, seconds):
    with q.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE compute_control SET heartbeat_at = clock_timestamp()"
                " - make_interval(secs => :s)"
            ),
            {"s": seconds},
        )


def test_worker_loss_interrupts_without_recomputation(q, org):  # WQ-T13
    lost, lost_driver = started(q)
    running = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 30}})
    waiting = submit(q, org)
    run_until(lost, lambda: len(lost_driver.started) == 1)
    lost.simulate_crash()  # no shutdown code runs; heartbeat stops
    _age_heartbeat(q, 5)
    successor, driver = started(q)
    assert driver.foreign_checked  # recovery inspected the recorded boundary
    assert job_state(q, org, running.job_id) is AttemptState.INTERRUPTED
    assert q.get_job(org, running.job_id).attempts[0].diagnostics["recovery_evidence"] == {
        "method": "FAKE_GROUP_SCAN"
    }
    run_until(successor, settled(q, org, waiting.job_id))
    assert job_state(q, org, waiting.job_id) is AttemptState.SUCCEEDED
    assert [h.step for h in driver.started] == ["TEST_METHOD"]  # only the waiter ran
    assert len(q.get_job(org, running.job_id).attempts) == 1  # no automatic retry
    retried = q.retry(org, running.job_id, "manual")
    assert retried.attempt_id != running.attempt_id
    successor.shutdown_drain()


def test_stale_owner_detects_fencing_and_stops_its_child(q, org):  # WQ-T08
    old, old_driver = started(q)
    submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 30}})
    run_until(old, lambda: len(old_driver.started) == 1)
    old.pause_heartbeat()
    _age_heartbeat(q, 5)
    successor, _ = started(q)
    run_until(old, lambda: old.ownership_lost, timeout=5)
    assert old_driver.started[0].killed
    assert q.control().supervisor_id == successor.supervisor_id
    successor.shutdown_drain()


def test_unverifiable_boundary_quarantines_until_operator_attests(q, org):  # WQ-T14
    lost, lost_driver = started(q)
    running = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 30}})
    run_until(lost, lambda: len(lost_driver.started) == 1)
    lost.simulate_crash()
    _age_heartbeat(q, 5)
    successor, driver = make_sup(q, FakeDriver(registry=REGISTRY, foreign_evidence=None))
    assert successor.start()
    assert q.control().state is SupervisorState.QUARANTINED
    assert job_state(q, org, running.job_id) is AttemptState.STOPPING
    q.operator_attest_cleanup(running.attempt_id, "operator-1", "container recreated")
    run_until(successor, lambda: q.control().state is SupervisorState.READY, timeout=10)
    assert job_state(q, org, running.job_id) is AttemptState.INTERRUPTED
    successor.shutdown_drain()


def test_drain_finishes_active_work_and_keeps_queued_records(q, org):  # WQ-T22
    sup, _ = started(q)
    active = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 0.4}})
    run_until(sup, lambda: job_state(q, org, active.job_id) is AttemptState.RUNNING)
    queued = submit(q, org)
    sup.shutdown_drain(timeout_s=10)
    assert job_state(q, org, active.job_id) is AttemptState.SUCCEEDED
    assert job_state(q, org, queued.job_id) is AttemptState.QUEUED
    assert q.control().state is SupervisorState.OFFLINE


def test_immediate_stop_interrupts_active_work_and_never_auto_retries(q, org):  # WQ-T22
    sup, _ = started(q)
    active = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 30}})
    run_until(sup, lambda: job_state(q, org, active.job_id) is AttemptState.RUNNING)
    queued = submit(q, org)
    sup.shutdown_immediate(timeout_s=10)
    assert job_state(q, org, active.job_id) is AttemptState.INTERRUPTED
    assert job_state(q, org, queued.job_id) is AttemptState.QUEUED
    restarted, driver = started(q)
    run_until(restarted, settled(q, org, queued.job_id))
    assert job_state(q, org, active.job_id) is AttemptState.INTERRUPTED
    assert len(driver.started) == 1
    restarted.shutdown_drain()


def _fixture_payload(q, attempt_id):
    with q.engine.connect() as conn:
        return conn.scalar(
            sa.text("SELECT payload FROM wq_fixture_results WHERE attempt_id = :a"),
            {"a": attempt_id},
        )


def test_last_method_cap_does_not_discard_a_completed_method(q, org):  # review F6, WQ-T17
    # Production shape: publication reserve equals stop grace, so the second method's hard
    # stop coincides with budget - grace. Only that method may time out, not the attempt.
    equal = dataclasses.replace(
        PROFILE, stop_grace_s=0.3, publication_reserve_s=0.3, comparison_total_s=2.5
    )
    qq = QueueRepository(q.engine, registry=REGISTRY, profile=equal)
    sup, driver = started(qq, profile=equal)
    accepted = submit(
        qq,
        org,
        "test.comparison.v1",
        {
            "methods": {
                "CLASSICAL_GP": {"sleep_s": 0.6},
                "EGP_PI_INSPIRED": {"sleep_s": 30, "ignore_sigterm": True},
            }
        },
    )
    run_until(sup, settled(qq, org, accepted.job_id))
    view = qq.get_job(org, accepted.job_id)
    assert view.state is AttemptState.SUCCEEDED
    methods = _fixture_payload(qq, view.attempts[0].attempt_id)["methods"]
    assert [m["step_status"] for m in methods] == ["COMPLETED", "TIMED_OUT"]
    assert [h.step for h in driver.started] == ["CLASSICAL_GP", "EGP_PI_INSPIRED"]
    sup.shutdown_drain()


def test_attestation_during_local_cleanup_does_not_crash_the_loop(q, org):  # review F7
    sup, driver = started(q, stop_confirm_timeout_s=0.3)
    driver.stuck_steps.add("TEST_METHOD")
    accepted = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 0.1}})
    run_until(sup, lambda: q.control().state is SupervisorState.QUARANTINED, timeout=10)
    attempt_id = q.get_job(org, accepted.job_id).current_attempt_id
    q.operator_attest_cleanup(attempt_id, "operator-1", "checked")
    # Local evidence still shows members: the lane stays unavailable meanwhile.
    for _ in range(20):
        sup.tick()
    assert q.control().state is SupervisorState.QUARANTINED
    driver.stuck_steps.clear()
    run_until(sup, lambda: q.control().state is SupervisorState.READY, timeout=10)
    assert sup.active is None and not sup.closed
    sup.shutdown_drain()


def test_logs_and_audit_omit_tokens_and_payloads(q, org, caplog):  # WQ-T26
    import logging

    caplog.set_level(logging.INFO, logger="pantrypulse.worker")
    sup, _ = started(q)
    secret_value = 424242
    accepted = submit(q, org, payload={"value": secret_value, "behavior": {}})
    run_until(sup, settled(q, org, accepted.job_id))
    with q.engine.connect() as conn:
        token = conn.scalar(
            sa.text("SELECT execution_token FROM compute_attempts WHERE attempt_id = :a"),
            {"a": accepted.attempt_id},
        )
        audit = conn.execute(sa.text("SELECT details::text FROM compute_audit_events")).scalars()
        audit_text = " ".join(audit)
    logs = caplog.text
    assert logs and "ATTEMPT_PUBLISHED" in logs
    for text in (logs, audit_text):
        assert str(token) not in text
        assert str(secret_value) not in text
        assert "nonce" not in text
        assert "postgresql" not in text.lower()
    view = q.get_job(org, accepted.job_id)
    assert not hasattr(view.attempts[0], "execution_token")
    sup.shutdown_drain()


def test_sigterm_ignoring_primary_is_force_stopped_before_the_cutoff(q, org):  # verifier F1
    sup, driver = started(q)
    accepted = submit(
        q,
        org,
        "test.forecast.v1",
        {
            "fallback_allowed": True,
            "primary": {"sleep_s": 30, "ignore_sigterm": True},
            "fallback": {},
        },
    )
    run_until(sup, settled(q, org, accepted.job_id))
    view = q.get_job(org, accepted.job_id)
    assert view.state is AttemptState.SUCCEEDED
    steps = _fixture_payload(q, view.attempts[0].attempt_id)["steps"]
    assert steps[0]["status"] == "TIMED_OUT"
    assert steps[0]["elapsed_s"] <= PROFILE.forecast_primary_cutoff_s
    assert "cutoff_breach_s" not in steps[0]
    assert driver.started[0].killed
    sup.shutdown_drain()


def test_storage_blips_during_an_attempt_do_not_kill_the_loop(q, org, monkeypatch):  # F3
    from app.repositories.jobs import QueueStorageUnavailable

    sup, _ = started(q)
    accepted = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 1.0}})
    run_until(sup, lambda: job_state(q, org, accepted.job_id) is AttemptState.RUNNING)
    real_read, real_control = q.read_attempt, q.control
    failures = {"n": 0}

    def flaky(real):
        def call(*args, **kwargs):
            if failures["n"] < 3:
                failures["n"] += 1
                raise QueueStorageUnavailable("blip")
            return real(*args, **kwargs)

        return call

    monkeypatch.setattr(q, "read_attempt", flaky(real_read))
    monkeypatch.setattr(q, "control", flaky(real_control))
    run_until(sup, settled(q, org, accepted.job_id))
    assert failures["n"] == 3
    assert real_read(accepted.attempt_id).state is AttemptState.SUCCEEDED
    assert not sup.closed
    sup.shutdown_drain()


def test_child_that_survives_sigkill_quarantines_the_lane(q, org):  # verifier low finding
    sup, driver = started(q, stop_confirm_timeout_s=0.4)
    driver.unkillable_steps.add("TEST_METHOD")
    accepted = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 30}})
    run_until(sup, lambda: q.control().state is SupervisorState.QUARANTINED, timeout=10)
    assert q.control().active_attempt_id == accepted.attempt_id
    assert job_state(q, org, accepted.job_id) is AttemptState.STOPPING
    driver.unkillable_steps.clear()
    run_until(sup, lambda: q.control().state is SupervisorState.READY, timeout=10)
    assert job_state(q, org, accepted.job_id) in (AttemptState.TIMED_OUT, AttemptState.FAILED)
    sup.shutdown_drain()


class _CommitThenLose(QueueRepository):
    def _commit(self, transaction):
        from sqlalchemy.exc import OperationalError

        transaction.commit()
        raise OperationalError("COMMIT", {}, Exception("ack lost"))


class _LoseBeforeCommit(QueueRepository):
    def _commit(self, transaction):
        from sqlalchemy.exc import OperationalError

        transaction.rollback()
        raise OperationalError("COMMIT", {}, Exception("ack lost"))


@pytest.mark.parametrize(
    ("cls", "expected"),
    [(_CommitThenLose, AttemptState.SUCCEEDED), (_LoseBeforeCommit, AttemptState.FAILED)],
)
def test_supervisor_reconciles_an_uncertain_commit(db, org, cls, expected):  # WQ-T20
    repo = cls(db, registry=REGISTRY, profile=PROFILE)
    sup, driver = started(repo)
    accepted = submit(repo, org)
    done = settled(repo, org, accepted.job_id)
    run_until(sup, lambda: done() and sup.active is None)
    attempt = repo.get_job(org, accepted.job_id).attempts[0]
    assert attempt.state is expected
    if expected is AttemptState.FAILED:
        assert attempt.reason_code == "PUBLICATION_COMMIT_LOST"
    events = [e["event_type"] for e in repo.audit_events(accepted.job_id)]
    assert "PUBLICATION_RECONCILED" in events
    assert len(driver.started) == 1  # never recomputed
    assert repo.control().active_attempt_id is None
    sup.shutdown_drain()


def test_deadlines_survive_a_blocked_database_call(q, org, monkeypatch):
    sup, driver = started(q)
    accepted = submit(
        q, org, payload={"value": 1, "behavior": {"sleep_s": 30, "ignore_sigterm": True}}
    )
    sup.tick()
    run = sup.active.current
    assert run is not None

    def blocked_control():
        # A stalled DB socket holds the main loop beyond the child cutoff.
        while time.monotonic() < run.hard_at + 0.1:
            time.sleep(0.01)
        assert driver.started[0].killed, "DB I/O must not delay SIGKILL"
        return original_control()

    original_control = q.control
    monkeypatch.setattr(q, "control", blocked_control)
    sup._last_ownership_check = 0
    sup.tick()
    monkeypatch.setattr(q, "control", original_control)
    run_until(sup, settled(q, org, accepted.job_id))
    assert q.control().active_attempt_id is None
    sup.shutdown_drain()


def test_crash_before_recording_second_boundary_cannot_reuse_first(q, org, monkeypatch):
    from app.repositories.jobs import QueueStorageUnavailable

    sup, driver = started(q)
    accepted = submit(
        q,
        org,
        "test.forecast.v1",
        {
            "fallback_allowed": True,
            "primary": {"fail": "classified"},
            "fallback": {"sleep_s": 30},
        },
    )
    original_record = q.record_boundary

    def lose_second_boundary(own, claim, boundary, phase):
        if phase == "fallback":
            raise QueueStorageUnavailable("lost before recording new child")
        return original_record(own, claim, boundary, phase)

    monkeypatch.setattr(q, "record_boundary", lose_second_boundary)
    run_until(sup, lambda: len(driver.started) == 2)
    assert q.read_attempt(accepted.attempt_id).execution_boundary is None
    sup.simulate_crash()
    with q.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE compute_control SET heartbeat_at = "
                "clock_timestamp() - interval '10 seconds'"
            )
        )
    successor, successor_driver = started(q)
    assert q.control().state is SupervisorState.QUARANTINED
    assert q.control().active_attempt_id == accepted.attempt_id
    assert not successor_driver.foreign_checked


def test_cancel_during_uncertain_commit_reconciliation_releases_slot(db, org):
    repo = _LoseBeforeCommit(db, registry=REGISTRY, profile=PROFILE)
    sup, driver = started(repo)
    accepted = submit(repo, org)
    run_until(sup, lambda: sup.active is not None and sup.active.uncertain)
    repo.cancel(org, accepted.job_id, "cancel-uncertain")
    sup.tick()
    assert repo.read_attempt(accepted.attempt_id).state is AttemptState.CANCELLED
    assert repo.control().active_attempt_id is None
    assert len(driver.started) == 1
    sup.shutdown_drain()


def test_failed_spawn_is_not_retried_when_finalization_storage_recovers(q, org, monkeypatch):
    from app.repositories.jobs import QueueStorageUnavailable

    sup, driver = started(q)
    driver.fail_spawn = True
    accepted = submit(q, org)
    original_finalize = q.finalize

    def unavailable(*args, **kwargs):
        raise QueueStorageUnavailable("finalization offline")

    monkeypatch.setattr(q, "finalize", unavailable)
    sup.tick()
    driver.fail_spawn = False
    monkeypatch.setattr(q, "finalize", original_finalize)
    run_until(sup, settled(q, org, accepted.job_id))
    attempt = q.read_attempt(accepted.attempt_id)
    assert attempt.state is AttemptState.FAILED
    assert attempt.reason_code == "SPAWN_FAILED"
    assert not driver.started  # only an explicit retry may run this attempt's input again
    sup.shutdown_drain()


# --- publication preparation hook (CR-w1-data-2) ---------------------------------------------


class _PreparingPublisher(FixturePublisher):
    """Echo publisher with the optional prepare/discard hooks; records every call."""

    def __init__(self):
        super().__init__("echo")
        self.prepared, self.discarded = [], []
        self.on_prepare = None
        self.discard_error = False

    def prepare(self, engine, identity, package, *, remaining_s):
        with engine.connect() as conn:  # the queue control row must not be locked here
            conn.execute(sa.text("SET LOCAL lock_timeout = '200ms'"))
            conn.execute(sa.text("SELECT 1 FROM compute_control FOR UPDATE NOWAIT"))
            conn.rollback()
        self.prepared.append((identity, remaining_s))
        if self.on_prepare:
            self.on_prepare(identity)
        return {**package, "prepared_by": str(identity.attempt_id)}

    def discard(self, engine, identity):
        self.discarded.append(identity)
        if self.discard_error:
            raise RuntimeError("cleanup failed")


@pytest.fixture
def prep():
    publisher = _PreparingPublisher()
    registry = Registry(
        [
            Registration(
                contract="test.prepared.v1",
                operation_kind=OperationKind.ALLOCATION,
                input_schema_version="1",
                max_input_bytes=16_384,
                max_output_bytes=65_536,
                handler=EchoHandler(),
                publisher=publisher,
            )
        ]
    )
    return publisher, registry


def _prep_started(repo, registry):
    config = SupervisorConfig(registry_name="test", profile=PROFILE, tick_s=0.02)
    sup = Supervisor(repo, registry, FakeDriver(registry=registry), config)
    _created.append(sup)
    assert sup.start()
    return sup


def _prep_run(db, org, prep, payload=None, cls=QueueRepository):
    publisher, registry = prep
    repo = cls(db, registry=registry, profile=PROFILE)
    sup = _prep_started(repo, registry)
    accepted = submit(repo, org, contract="test.prepared.v1", payload=payload)
    done = settled(repo, org, accepted.job_id)
    run_until(sup, lambda: done() and sup.active is None)
    attempt = repo.get_job(org, accepted.job_id).attempts[0]
    assert repo.control().active_attempt_id is None
    sup.shutdown_drain()
    return repo, attempt


def test_prepared_package_is_published_without_discard(db, org, prep):
    publisher, _ = prep
    repo, attempt = _prep_run(db, org, prep)
    assert attempt.state is AttemptState.SUCCEEDED
    assert _fixture_payload(repo, attempt.attempt_id)["prepared_by"] == str(attempt.attempt_id)
    [(identity, remaining_s)] = publisher.prepared
    assert identity.attempt_id == attempt.attempt_id
    assert identity.organization_id == org.organization_id
    assert 0 < remaining_s < PROFILE.allocation_total_s
    assert publisher.discarded == []


def test_rejected_publication_discards_the_prepared_data(db, org, prep):
    publisher, _ = prep
    payload = {"value": 3, "behavior": {}, "publish_fail": True}
    _, attempt = _prep_run(db, org, prep, payload)
    assert attempt.state is AttemptState.FAILED
    assert [i.attempt_id for i in publisher.discarded] == [attempt.attempt_id]


@pytest.mark.parametrize("error", [PublicationRejected("IMPORT_REJECTED"), RuntimeError("load")])
def test_prepare_failure_fails_the_attempt_and_discards(db, org, prep, error):
    publisher, _ = prep

    def reject(identity):
        raise error

    publisher.on_prepare = reject
    _, attempt = _prep_run(db, org, prep)
    assert attempt.state is AttemptState.FAILED
    assert attempt.reason_code == "PUBLICATION_REJECTED"
    assert len(publisher.discarded) == 1


def test_prepare_past_the_deadline_times_out_and_discards(db, org, prep):
    publisher, _ = prep
    publisher.on_prepare = lambda identity: time.sleep(PROFILE.allocation_total_s)
    _, attempt = _prep_run(db, org, prep)
    assert attempt.state is AttemptState.TIMED_OUT
    assert len(publisher.discarded) == 1


def test_cancel_during_prepare_discards(db, org, prep):
    publisher, registry = prep
    repo = QueueRepository(db, registry=registry, profile=PROFILE)
    publisher.on_prepare = lambda identity: repo.cancel(org, identity.job_id, "cancel-prep")
    sup = _prep_started(repo, registry)
    accepted = submit(repo, org, contract="test.prepared.v1")
    done = settled(repo, org, accepted.job_id)
    run_until(sup, lambda: done() and sup.active is None)
    assert job_state(repo, org, accepted.job_id) is AttemptState.CANCELLED
    assert len(publisher.discarded) == 1
    sup.shutdown_drain()


def test_storage_retry_publishes_without_preparing_twice(db, org, prep, monkeypatch):
    publisher, _ = prep
    real, calls = QueueRepository.publish, []

    def flaky(self, *args):
        calls.append(1)
        if len(calls) == 1:
            raise QueueStorageUnavailable("blip")
        return real(self, *args)

    monkeypatch.setattr(QueueRepository, "publish", flaky)
    _, attempt = _prep_run(db, org, prep)
    assert attempt.state is AttemptState.SUCCEEDED
    assert len(calls) == 2 and len(publisher.prepared) == 1
    assert publisher.discarded == []


@pytest.mark.parametrize(
    ("cls", "expected", "discards"),
    [(_CommitThenLose, AttemptState.SUCCEEDED, 0), (_LoseBeforeCommit, AttemptState.FAILED, 1)],
)
def test_reconciled_publication_discards_only_when_lost(db, org, prep, cls, expected, discards):
    publisher, _ = prep
    _, attempt = _prep_run(db, org, prep, cls=cls)
    assert attempt.state is expected
    assert len(publisher.discarded) == discards


def test_failed_discard_does_not_block_finalization(db, org, prep):
    publisher, _ = prep
    publisher.discard_error = True
    _, attempt = _prep_run(db, org, prep, {"value": 3, "behavior": {}, "publish_fail": True})
    assert attempt.state is AttemptState.FAILED
    assert len(publisher.discarded) == 1


def _store_nul(connection):  # psycopg refuses NUL in text: a real DataError
    connection.execute(sa.text("SELECT CAST(:v AS text)"), {"v": "user-data\x00"})


def _quote_user_data(connection):  # like a constraint error that names the row's values
    raise ValueError("Key (external_id)=(user-data) already exists")


@pytest.mark.parametrize(("fail", "error_type"),
                         [(_store_nul, "DataError"), (_quote_user_data, "ValueError")])
def test_unexpected_publication_error_fails_the_attempt_and_the_loop_runs_on(
    db, org, prep, caplog, fail, error_type
):  # W2-06: a DataError in publish once ended the worker process
    import logging

    caplog.set_level(logging.INFO, logger="pantrypulse.worker")
    publisher, registry = prep
    real_publish = publisher.publish

    def publish(connection, identity, package):
        if not publisher.discarded:  # the first publication hits an error nobody expects
            fail(connection)
        return real_publish(connection, identity, package)

    publisher.publish = publish
    repo = QueueRepository(db, registry=registry, profile=PROFILE)
    sup = _prep_started(repo, registry)
    first = submit(repo, org, contract="test.prepared.v1")
    second = submit(repo, org, contract="test.prepared.v1")
    run_until(sup, lambda: settled(repo, org, second.job_id)() and sup.active is None)
    failed = repo.get_job(org, first.job_id).attempts[0]
    assert (failed.state, failed.reason_code) == (
        AttemptState.FAILED, "PUBLICATION_STORAGE_FAILED")
    assert [i.attempt_id for i in publisher.discarded] == [failed.attempt_id]
    assert repo.get_job(org, second.job_id).attempts[0].state is AttemptState.SUCCEEDED
    assert not sup.closed and repo.control().active_attempt_id is None
    assert f'"error_type":"{error_type}"' in caplog.text  # the type, never the message
    assert "user-data" not in caplog.text
    sup.shutdown_drain()


def test_ownership_lost_during_publication_hands_the_lane_over(db, org, prep, monkeypatch):
    publisher, registry = prep
    repo = QueueRepository(db, registry=registry, profile=PROFILE)

    def lost(*args, **kwargs):
        raise OwnershipLost("lane ownership changed")

    monkeypatch.setattr(repo, "publish", lost)
    sup = _prep_started(repo, registry)
    accepted = submit(repo, org, contract="test.prepared.v1")
    run_until(sup, lambda: sup.ownership_lost)
    assert sup.closed and len(publisher.discarded) == 1
    assert repo.get_job(org, accepted.job_id).attempts[0].state is AttemptState.RUNNING


class _CommitThenError(QueueRepository):
    def _commit(self, transaction):
        transaction.commit()  # the publication really commits
        raise RuntimeError("not a database error")


def test_any_error_from_commit_is_reconciled_never_discarded(db, org, prep):  # W2-06 F2
    publisher, registry = prep
    repo = _CommitThenError(db, registry=registry, profile=PROFILE)
    sup = _prep_started(repo, registry)
    accepted = submit(repo, org, contract="test.prepared.v1")
    run_until(sup, lambda: settled(repo, org, accepted.job_id)() and sup.active is None)
    assert repo.get_job(org, accepted.job_id).attempts[0].state is AttemptState.SUCCEEDED
    assert publisher.discarded == []  # registry contract: never after a committed publication
    events = [e["event_type"] for e in repo.audit_events(accepted.job_id)]
    assert "PUBLICATION_RECONCILED" in events and not sup.closed
    sup.shutdown_drain()


# --- named secrets in the child environment (W1-D08 Google key, Gabriel 2026-11-07) --------


def _secret_registry(child_secrets):
    return Registry(
        [
            Registration(
                contract="test.secret.v1",
                operation_kind=OperationKind.ALLOCATION,
                input_schema_version="1",
                max_input_bytes=16_384,
                max_output_bytes=65_536,
                handler=EchoHandler(),
                publisher=FixturePublisher("echo"),
                child_secrets=child_secrets,
            )
        ]
    )


@pytest.fixture
def google_key(db):
    with db.begin() as conn:
        conn.execute(sa.text("DELETE FROM local_secrets"))
    yield
    with db.begin() as conn:
        conn.execute(sa.text("DELETE FROM local_secrets"))


def _secret_run(db, org, registry):
    repo = QueueRepository(db, registry=registry, profile=PROFILE)
    driver = FakeDriver(registry=registry)
    config = SupervisorConfig(registry_name="test", profile=PROFILE, tick_s=0.02)
    sup = Supervisor(repo, registry, driver, config)
    _created.append(sup)
    assert sup.start()
    accepted = submit(repo, org, contract="test.secret.v1")
    done = settled(repo, org, accepted.job_id)
    run_until(sup, lambda: done() and sup.active is None)
    sup.shutdown_drain()
    return repo, driver, accepted


def test_declared_secret_reaches_only_the_child_env(db, org, google_key, caplog):
    with db.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO local_secrets (name, value) VALUES ('google_maps_api_key', :v)"),
            {"v": "k-secret-xyz"},
        )
    caplog.set_level("DEBUG")
    repo, driver, accepted = _secret_run(db, org, _secret_registry(("google_maps_api_key",)))
    assert job_state(repo, org, accepted.job_id) is AttemptState.SUCCEEDED
    assert driver.child_envs == [{"PP_SECRET_GOOGLE_MAPS_API_KEY": "k-secret-xyz"}]
    view = repo.get_job(org, accepted.job_id)
    stored = repr(view) + repr(repo.audit_events(accepted.job_id)) + caplog.text
    with db.connect() as conn:
        stored += repr(conn.execute(sa.text("SELECT * FROM compute_jobs")).all())
        stored += repr(conn.execute(sa.text("SELECT * FROM compute_attempts")).all())
    assert "k-secret-xyz" not in stored


def test_undeclared_registration_gets_no_secret(db, org, google_key):
    with db.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO local_secrets (name, value) VALUES ('google_maps_api_key', 'k')")
        )
    _, driver, _ = _secret_run(db, org, _secret_registry(()))
    assert driver.child_envs == [{}]


def test_missing_secret_fails_before_spawn(db, org, google_key):
    repo, driver, accepted = _secret_run(db, org, _secret_registry(("google_maps_api_key",)))
    attempt = repo.get_job(org, accepted.job_id).attempts[0]
    assert attempt.state is AttemptState.FAILED
    assert attempt.reason_code == "SPAWN_FAILED"
    assert attempt.error == {"code": "SECRET_UNAVAILABLE"}
    assert driver.started == [] and driver.child_envs == []


def test_secret_names_are_checked():
    with pytest.raises(ValueError):
        dataclasses.replace(REGISTRY.get("test.echo.v1"), child_secrets=("Bad-Name",))


# verifier findings on PR #103 (F1–F3)


def test_timed_out_prepare_is_not_rerun_after_a_storage_blip(db, org, prep, monkeypatch):  # F1
    publisher, registry = prep

    def slow(identity):
        raise PublicationRejected("SLOW_LOAD", timed_out=True)

    publisher.on_prepare = slow
    real, calls = QueueRepository.request_stop, []

    def flaky(self, *args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise QueueStorageUnavailable("blip")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(QueueRepository, "request_stop", flaky)
    _, attempt = _prep_run(db, org, prep)
    assert attempt.state is AttemptState.TIMED_OUT
    assert len(publisher.prepared) == 1 and len(publisher.discarded) == 1


def test_ownership_lost_after_prepare_discards(db, org, prep):  # F2
    publisher, registry = prep

    def takeover(identity):
        with db.begin() as conn:
            conn.execute(sa.text("UPDATE compute_control SET generation = generation + 1"))

    publisher.on_prepare = takeover
    repo = QueueRepository(db, registry=registry, profile=PROFILE)
    sup = _prep_started(repo, registry)
    submit(repo, org, contract="test.prepared.v1")
    run_until(sup, lambda: sup.ownership_lost)
    assert len(publisher.prepared) == 1 and len(publisher.discarded) == 1


@pytest.mark.parametrize(("outcome", "discards"), [("OTHER_CANCELLED", 1), ("OTHER_SUCCEEDED", 0)])
def test_reconciled_other_outcome_discards_unless_succeeded(
    db, org, prep, monkeypatch, outcome, discards
):  # F3
    publisher, registry = prep
    monkeypatch.setattr(_LoseBeforeCommit, "reconcile_publication", lambda *_: outcome)
    repo = _LoseBeforeCommit(db, registry=registry, profile=PROFILE)
    sup = _prep_started(repo, registry)
    submit(repo, org, contract="test.prepared.v1")
    run_until(sup, lambda: len(publisher.prepared) == 1 and sup.active is None)
    assert len(publisher.discarded) == discards
    sup.shutdown_drain()


class _CommitThenFence(QueueRepository):
    def _commit(self, transaction):
        from sqlalchemy.exc import OperationalError

        transaction.commit()  # the publication really commits
        with self.engine.begin() as conn:  # another owner takes the lane before the ack
            conn.execute(sa.text("UPDATE compute_control SET generation = generation + 1"))
        raise OperationalError("COMMIT", {}, Exception("ack lost"))


def test_fenced_during_uncertain_commit_never_discards(db, org, prep):  # verifier N1 on PR #103
    publisher, registry = prep
    repo = _CommitThenFence(db, registry=registry, profile=PROFILE)
    sup = _prep_started(repo, registry)
    accepted = submit(repo, org, contract="test.prepared.v1")
    run_until(sup, lambda: sup.ownership_lost)
    assert repo.get_job(org, accepted.job_id).attempts[0].state is AttemptState.SUCCEEDED
    assert publisher.discarded == []


# --- follow-up jobs admitted with the publication (CR-w1-data-5) ------------------------


class _FollowingPublisher(FixturePublisher):
    """Echo publisher whose committed result queues the jobs in `self.follow`."""

    def __init__(self, follow):
        super().__init__("echo")
        self.follow = follow
        self.hook_error = False
        self.publish_delay_s = 0.0

    def publish(self, connection, identity, package):
        time.sleep(self.publish_delay_s)
        return super().publish(connection, identity, package)

    def follow_ups(self, connection, identity, manifest):
        from app.services.jobs.registry import FollowUp

        if self.hook_error:
            connection.execute(sa.text("SELECT 1/0"))  # aborts the hook's own reads
        # Same transaction: this attempt's publication is visible, not yet committed.
        assert connection.scalar(sa.text("SELECT count(*) FROM wq_fixture_results"
                                         " WHERE attempt_id = :a"), {"a": identity.attempt_id})
        return [FollowUp(contract, payload) for contract, payload in self.follow]


def _follow_registry(follow):
    from app.workers.v1_stub import NotBuiltHandler

    def reg(contract, publisher, handler=None):
        return Registration(
            contract=contract,
            operation_kind=OperationKind.ALLOCATION,
            input_schema_version="1",
            max_input_bytes=16_384,
            max_output_bytes=65_536,
            handler=handler or EchoHandler(),
            publisher=publisher,
        )

    return Registry(
        [reg("test.parent.v1", _FollowingPublisher(follow)),
         reg("test.child.v1", FixturePublisher("echo")),
         reg("test.stub.v1", FixturePublisher("echo"), NotBuiltHandler("W9-X01"))]
    )


def _follow_run(
    db, org, follow, cls=QueueRepository, admission=None, monkeypatch=None, setup=None,
    patch=None,
):
    registry = _follow_registry(follow)
    if setup is not None:
        setup(registry.get("test.parent.v1").publisher)
    repo = cls(db, registry=registry, profile=PROFILE)
    if patch is not None:
        patch(repo)
    if admission is not None:
        real = repo._admission

        def patched(conn, ctl, now, contract, validated=None):
            if contract == "test.child.v1":
                return admission
            return real(conn, ctl, now, contract, validated)

        monkeypatch.setattr(repo, "_admission", patched)
    config = SupervisorConfig(registry_name="test", profile=PROFILE, tick_s=0.02)
    sup = Supervisor(repo, registry, FakeDriver(registry=registry), config)
    _created.append(sup)
    assert sup.start()
    accepted = submit(repo, org, contract="test.parent.v1")
    if setup is not None and getattr(setup, "squat", False):
        # A client in the same organization guesses keys derived from the parent job.
        key = f"follow-up:{accepted.job_id}:0"
        repo.submit(org, "test.child.v1", {"value": 99, "behavior": {}}, key)
    done = settled(repo, org, accepted.job_id)
    run_until(sup, lambda: done() and sup.active is None)
    sup.shutdown_drain()
    with db.connect() as conn:
        children = conn.execute(
            sa.text(
                "SELECT organization_id, requested_by_ref FROM compute_jobs"
                " WHERE handler_contract = 'test.child.v1' AND organization_id = :o"
            ),
            {"o": org.organization_id},
        ).all()
    return repo, accepted, children


CHILD = ("test.child.v1", {"value": 5, "behavior": {}})


def test_follow_up_is_admitted_with_the_publication(db, org):
    repo, accepted, children = _follow_run(db, org, [CHILD])
    assert job_state(repo, org, accepted.job_id) is AttemptState.SUCCEEDED
    assert children == [(org.organization_id, org.actor_ref)]


def test_follow_up_is_rolled_back_with_a_lost_publication(db, org):
    repo, accepted, children = _follow_run(db, org, [CHILD], cls=_LoseBeforeCommit)
    assert job_state(repo, org, accepted.job_id) is AttemptState.FAILED
    assert children == []


@pytest.mark.parametrize(
    ("follow", "admission", "code"),
    [
        ([("test.nope.v1", {"value": 1})], None, "UNKNOWN_CONTRACT"),
        ([("test.child.v1", {"value": "x"})], None, "INVALID_INPUT"),
        ([CHILD], "COMPUTE_QUEUE_FULL", "COMPUTE_QUEUE_FULL"),
    ],
)
def test_rejected_follow_up_never_fails_the_publication(
    db, org, monkeypatch, follow, admission, code
):
    from app.services.jobs.contracts import AdmissionOutcome

    outcome = AdmissionOutcome(admission) if admission else None
    repo, accepted, children = _follow_run(
        db, org, follow, admission=outcome, monkeypatch=monkeypatch
    )
    assert job_state(repo, org, accepted.job_id) is AttemptState.SUCCEEDED
    assert children == []
    rejected = [
        e for e in repo.audit_events(accepted.job_id) if e["event_type"] == "FOLLOW_UP_REJECTED"
    ]
    assert [(e["reason_code"], e["details"]["contract"]) for e in rejected] == [
        (code, follow[0][0])
    ]


def _rejections(repo, job_id):
    return [
        (e["reason_code"], e["details"].get("contract"))
        for e in repo.audit_events(job_id)
        if e["event_type"] == "FOLLOW_UP_REJECTED"
    ]


def test_unbuilt_follow_up_contract_never_fails_the_publication(db, org):  # verifier F1
    repo, accepted, children = _follow_run(db, org, [("test.stub.v1", {"value": 1})])
    assert job_state(repo, org, accepted.job_id) is AttemptState.SUCCEEDED
    assert _rejections(repo, accepted.job_id) == [("NOT_IMPLEMENTED", "test.stub.v1")]


def test_a_client_key_cannot_claim_the_follow_up(db, org):  # verifier F2
    def squat(publisher):
        pass

    squat.squat = True
    repo, accepted, children = _follow_run(db, org, [CHILD], setup=squat)
    assert job_state(repo, org, accepted.job_id) is AttemptState.SUCCEEDED
    assert _rejections(repo, accepted.job_id) == []
    assert len(children) == 2  # the client's job plus the follow-up


def test_failing_hook_never_fails_the_publication(db, org):  # verifier delta note
    def broken(publisher):
        publisher.hook_error = True

    repo, accepted, children = _follow_run(db, org, [CHILD], setup=broken)
    assert job_state(repo, org, accepted.job_id) is AttemptState.SUCCEEDED
    assert children == []
    assert _rejections(repo, accepted.job_id) == [("FOLLOW_UP_HOOK_FAILED", None)]


def test_follow_up_queue_window_starts_after_the_publisher_ran(db, org):  # verifier note 4
    def slow(publisher):
        publisher.publish_delay_s = 0.4

    repo, accepted, _ = _follow_run(db, org, [CHILD], setup=slow)
    parent = repo.get_job(org, accepted.job_id).attempts[0]
    with db.connect() as conn:
        enqueued = conn.scalar(
            sa.text(
                "SELECT a.enqueued_at FROM compute_attempts a JOIN compute_jobs j"
                " ON j.job_id = a.job_id WHERE j.handler_contract = 'test.child.v1'"
                " AND j.organization_id = :o"
            ),
            {"o": org.organization_id},
        )
    assert (parent.completed_at - enqueued).total_seconds() < 0.2


def _child_admission_raises(monkeypatch, errors):
    """The follow-up's admission raises each of `errors` once, then runs for real."""

    def patch(repo):
        real = repo._admission

        def admission(conn, ctl, now, contract, validated=None):
            if contract == "test.child.v1" and errors:
                raise errors.pop(0)
            return real(conn, ctl, now, contract, validated)

        monkeypatch.setattr(repo, "_admission", admission)

    return patch


def test_storage_error_in_a_follow_up_retries_the_whole_publication(db, org, monkeypatch):
    from sqlalchemy.exc import OperationalError

    timeout = OperationalError("SELECT", {}, Exception("canceling statement due to timeout"))
    patch = _child_admission_raises(monkeypatch, [timeout])
    repo, accepted, children = _follow_run(db, org, [CHILD], patch=patch)
    assert job_state(repo, org, accepted.job_id) is AttemptState.SUCCEEDED
    assert len(children) == 1
    assert _rejections(repo, accepted.job_id) == []


def test_database_error_codes_never_reach_the_audit_reason(db, org, monkeypatch):  # re-verify F1
    from sqlalchemy.exc import IntegrityError

    error = IntegrityError("INSERT", {}, Exception("violates check"))  # .code == "gkpj"
    patch = _child_admission_raises(monkeypatch, [error])
    repo, accepted, children = _follow_run(db, org, [CHILD], patch=patch)
    assert job_state(repo, org, accepted.job_id) is AttemptState.SUCCEEDED
    assert children == []
    assert _rejections(repo, accepted.job_id) == [("FOLLOW_UP_FAILED", "test.child.v1")]


def test_slow_publish_does_not_make_the_live_supervisor_look_stale(db, org):  # re-verify F2
    def slow(publisher):
        publisher.publish_delay_s = PROFILE.heartbeat_stale_s + 0.1

    repo, accepted, children = _follow_run(db, org, [CHILD], setup=slow)
    assert job_state(repo, org, accepted.job_id) is AttemptState.SUCCEEDED
    assert _rejections(repo, accepted.job_id) == []
    assert len(children) == 1
