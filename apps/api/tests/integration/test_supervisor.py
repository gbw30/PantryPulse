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

from app.repositories.jobs import QueueRepository, TrustedScope
from app.services.jobs.contracts import AttemptState, RuntimeProfile, SupervisorState
from app.workers.supervisor import Supervisor, SupervisorConfig
from app.workers.testing import REGISTRY

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


def test_storage_failure_stops_local_child_and_requires_owned_recovery(q, org, monkeypatch):
    # OR-DEC-011 [PROVISIONAL]: lost publication authority cannot keep computing.
    from app.repositories.jobs import QueueStorageUnavailable

    sup, driver = started(q)
    accepted = submit(q, org, payload={"value": 1, "behavior": {"sleep_s": 30.0}})
    run_until(sup, lambda: job_state(q, org, accepted.job_id) is AttemptState.RUNNING)
    real_read = q.read_attempt

    def unavailable(*args, **kwargs):
        raise QueueStorageUnavailable("lost database")

    monkeypatch.setattr(q, "read_attempt", unavailable)
    run_until(sup, lambda: sup.ownership_lost)
    assert driver.started[0].killed
    assert sup.closed
    monkeypatch.setattr(q, "read_attempt", real_read)
    assert real_read(accepted.attempt_id).state is AttemptState.RUNNING
    # The failed owner writes nothing after losing storage; a fresh fenced owner
    # confirms cleanup, retains history and records interruption without retry.
    with q.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE compute_control SET heartbeat_at=clock_timestamp()-interval '5 seconds'"
            )
        )
    replacement, _ = started(q)
    assert real_read(accepted.attempt_id).state is AttemptState.INTERRUPTED
    assert len(q.get_job(org, accepted.job_id).attempts) == 1
    replacement.shutdown_drain()


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
