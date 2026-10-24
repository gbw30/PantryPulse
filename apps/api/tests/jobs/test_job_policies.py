"""WQ-01 pure policies: transitions (WQ-T01), admission (T02), boundaries (T03), budgets (T04,
T15, T17)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.jobs.contracts import (
    PRODUCTION_PROFILE,
    AdmissionOutcome,
    AttemptState,
    HeartbeatStatus,
    OperationKind,
    ReasonCode,
    StepOutcome,
    StepRunIf,
    StepSpec,
    StepStatus,
    SupervisorState,
)
from app.services.jobs.policies import (
    InvalidTransition,
    admission_outcome,
    allocation_steps,
    can_retry,
    comparison_steps,
    final_state_for_stop_reason,
    forecast_steps,
    heartbeat_status,
    is_allowed_transition,
    is_queue_expired,
    operation_budget_s,
    plan_step_window,
    remaining_budget_s,
    require_transition,
    should_run_step,
)

S = AttemptState
ALLOWED = {
    (S.QUEUED, S.RUNNING),
    (S.QUEUED, S.CANCELLED),
    (S.QUEUED, S.EXPIRED),
    (S.QUEUED, S.FAILED),
    (S.RUNNING, S.SUCCEEDED),
    (S.RUNNING, S.FAILED),
    (S.RUNNING, S.STOPPING),
    (S.STOPPING, S.FAILED),
    (S.STOPPING, S.TIMED_OUT),
    (S.STOPPING, S.INTERRUPTED),
    (S.STOPPING, S.CANCELLED),
}


@pytest.mark.parametrize("source", list(S))
@pytest.mark.parametrize("target", list(S))
def test_every_transition_pair_matches_the_table(source, target):
    expected = (source, target) in ALLOWED
    assert is_allowed_transition(source, target) is expected
    if expected:
        require_transition(source, target)
    else:
        with pytest.raises(InvalidTransition):
            require_transition(source, target)


def test_terminal_attempts_never_transition():
    for terminal in (S.SUCCEEDED, S.FAILED, S.TIMED_OUT, S.INTERRUPTED, S.CANCELLED, S.EXPIRED):
        assert not any(is_allowed_transition(terminal, t) for t in S)


def test_retry_only_from_cleaned_up_non_success_terminal_states():
    assert {s for s in S if can_retry(s)} == {
        S.FAILED,
        S.TIMED_OUT,
        S.INTERRUPTED,
        S.EXPIRED,
        S.CANCELLED,
    }


# --- WQ-T03 boundaries -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (None, HeartbeatStatus.MISSING),
        (0.0, HeartbeatStatus.FRESH),
        (14.999, HeartbeatStatus.FRESH),
        (15.0, HeartbeatStatus.STALE),
        (15.001, HeartbeatStatus.STALE),
        (-0.001, HeartbeatStatus.FUTURE),
    ],
)
def test_heartbeat_freshness_boundary(age, expected):
    assert heartbeat_status(age, PRODUCTION_PROFILE) is expected


def test_queue_expiry_applies_at_equality():
    enqueued = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    deadline = enqueued + timedelta(seconds=900)
    assert not is_queue_expired(enqueued + timedelta(seconds=899.999), deadline)
    assert is_queue_expired(enqueued + timedelta(seconds=900), deadline)
    assert is_queue_expired(enqueued + timedelta(seconds=901), deadline)


def test_queue_expiry_rejects_naive_datetimes():
    with pytest.raises(ValueError):
        is_queue_expired(datetime(2026, 10, 24), datetime(2026, 10, 24, tzinfo=UTC))


# --- WQ-T02 admission --------------------------------------------------------------------


def _admit(**kw):
    base = dict(
        supervisor_state=SupervisorState.READY,
        heartbeat=HeartbeatStatus.FRESH,
        capable=True,
        recovery_required=False,
        contract_advertised=True,
        queued_count=0,
        profile=PRODUCTION_PROFILE,
    )
    base.update(kw)
    return admission_outcome(**base)


def test_healthy_busy_supervisor_admits_up_to_two_waiters_globally():
    assert _admit(queued_count=0) is AdmissionOutcome.ACCEPT
    assert _admit(queued_count=1) is AdmissionOutcome.ACCEPT
    assert _admit(queued_count=2) is AdmissionOutcome.COMPUTE_QUEUE_FULL
    assert _admit(queued_count=7) is AdmissionOutcome.COMPUTE_QUEUE_FULL


@pytest.mark.parametrize(
    "change",
    [
        {"supervisor_state": SupervisorState.OFFLINE},
        {"supervisor_state": SupervisorState.STARTING},
        {"supervisor_state": SupervisorState.DRAINING},
        {"supervisor_state": SupervisorState.RECOVERING},
        {"supervisor_state": SupervisorState.QUARANTINED},
        {"heartbeat": HeartbeatStatus.STALE},
        {"heartbeat": HeartbeatStatus.MISSING},
        {"heartbeat": HeartbeatStatus.FUTURE},
        {"capable": False},
        {"recovery_required": True},
        {"contract_advertised": False},
    ],
)
def test_unavailable_compute_is_distinct_from_full(change):
    assert _admit(**change) is AdmissionOutcome.COMPUTE_UNAVAILABLE
    # Unavailability wins over a full queue: the caller learns compute is down.
    assert _admit(queued_count=2, **change) is AdmissionOutcome.COMPUTE_UNAVAILABLE


# --- WQ-T04/T15/T17 budgets -----------------------------------------------------------------


def test_operation_budgets_are_the_accepted_ceilings():
    assert operation_budget_s(OperationKind.FORECAST, PRODUCTION_PROFILE) == 300
    assert operation_budget_s(OperationKind.ALLOCATION, PRODUCTION_PROFILE) == 25
    assert operation_budget_s(OperationKind.COMPARISON, PRODUCTION_PROFILE) == 60


def test_forecast_primary_is_signalled_by_268_and_force_stopped_by_270():
    primary, fallback = forecast_steps(PRODUCTION_PROFILE, fallback_allowed=True)
    window = plan_step_window(primary, elapsed_s=0, budget_s=300, profile=PRODUCTION_PROFILE)
    assert (window.soft_stop_s, window.hard_stop_s) == (268, 270)
    assert fallback.run_if is StepRunIf.AFTER_FALLBACK_ELIGIBLE_FAILURE


def test_fallback_shares_the_original_300_second_budget():
    _, fallback = forecast_steps(PRODUCTION_PROFILE, fallback_allowed=True)
    late = plan_step_window(fallback, elapsed_s=271, budget_s=300, profile=PRODUCTION_PROFILE)
    # Publication reserve (2 s) stays inside the 300 s; no fresh allowance.
    assert late.hard_stop_s == 298
    early = plan_step_window(fallback, elapsed_s=12, budget_s=300, profile=PRODUCTION_PROFILE)
    assert early.hard_stop_s == 298
    assert (
        plan_step_window(fallback, elapsed_s=297.5, budget_s=300, profile=PRODUCTION_PROFILE)
        is None
    )


def test_without_fallback_the_primary_may_use_the_whole_budget():
    (only,) = forecast_steps(PRODUCTION_PROFILE, fallback_allowed=False)
    window = plan_step_window(only, elapsed_s=0, budget_s=300, profile=PRODUCTION_PROFILE)
    assert window.hard_stop_s == 298


def test_comparison_methods_are_sequential_capped_and_may_be_not_run():
    first, second = comparison_steps(PRODUCTION_PROFILE)
    assert (first.name, second.name) == ("CLASSICAL_GP", "EGP_PI_INSPIRED")
    assert first.max_s == second.max_s == 25
    w1 = plan_step_window(first, elapsed_s=0.5, budget_s=60, profile=PRODUCTION_PROFILE)
    assert w1.hard_stop_s == 25.5
    w2 = plan_step_window(second, elapsed_s=26, budget_s=60, profile=PRODUCTION_PROFILE)
    assert w2.hard_stop_s == 51
    w_late = plan_step_window(second, elapsed_s=50, budget_s=60, profile=PRODUCTION_PROFILE)
    assert w_late.hard_stop_s == 58  # parent budget minus publication reserve
    assert plan_step_window(second, elapsed_s=57.5, budget_s=60, profile=PRODUCTION_PROFILE) is None


def test_allocation_has_a_single_method_step():
    (step,) = allocation_steps(PRODUCTION_PROFILE, "CLASSICAL_GP")
    assert step.name == "CLASSICAL_GP"
    w = plan_step_window(step, elapsed_s=0, budget_s=25, profile=PRODUCTION_PROFILE)
    assert w.hard_stop_s == 23


def test_step_windows_cannot_be_reset_by_elapsed_time_or_later_steps():
    step = StepSpec(name="x", min_s=1)
    a = plan_step_window(step, elapsed_s=0, budget_s=300, profile=PRODUCTION_PROFILE)
    b = plan_step_window(step, elapsed_s=200, budget_s=300, profile=PRODUCTION_PROFILE)
    assert a.hard_stop_s == b.hard_stop_s == 298
    with pytest.raises(ValueError):
        plan_step_window(step, elapsed_s=-1, budget_s=300, profile=PRODUCTION_PROFILE)


def test_remaining_budget_uses_the_smaller_clock_and_never_goes_negative():
    assert remaining_budget_s(db_remaining_s=10, monotonic_remaining_s=12) == 10
    assert remaining_budget_s(db_remaining_s=12, monotonic_remaining_s=10) == 10
    assert remaining_budget_s(db_remaining_s=-3, monotonic_remaining_s=10) == 0


def _outcome(status, eligible=False):
    return StepOutcome(name="primary", status=status, fallback_eligible=eligible)


def test_fallback_runs_only_after_timeout_or_classified_primary_failure():
    fallback = StepSpec(name="fallback", run_if=StepRunIf.AFTER_FALLBACK_ELIGIBLE_FAILURE, min_s=1)
    assert should_run_step(fallback, [_outcome(StepStatus.TIMED_OUT, eligible=True)])
    assert should_run_step(fallback, [_outcome(StepStatus.FAILED, eligible=True)])
    assert not should_run_step(fallback, [_outcome(StepStatus.FAILED, eligible=False)])
    assert not should_run_step(fallback, [_outcome(StepStatus.COMPLETED)])
    assert not should_run_step(fallback, [])
    always = StepSpec(name="EGP_PI_INSPIRED", min_s=1)
    assert should_run_step(always, [_outcome(StepStatus.FAILED)])


@pytest.mark.parametrize(
    ("reason", "state"),
    [
        (ReasonCode.CANCEL_REQUESTED, S.CANCELLED),
        (ReasonCode.EXECUTION_DEADLINE_EXCEEDED, S.TIMED_OUT),
        (ReasonCode.WORKER_LOST, S.INTERRUPTED),
        (ReasonCode.SHUTDOWN_IMMEDIATE, S.INTERRUPTED),
        (ReasonCode.OUTPUT_TOO_LARGE, S.FAILED),
        (ReasonCode.CLEANUP_UNCONFIRMED, S.FAILED),
    ],
)
def test_stop_reason_decides_the_terminal_state(reason, state):
    assert final_state_for_stop_reason(reason) is state


def test_advertisement_round_trip_and_malformed_documents_fail_closed():
    from app.services.jobs.policies import advertised_capability, supervisor_advertisement

    doc = supervisor_advertisement(
        PRODUCTION_PROFILE, handler_contracts=["b.v1", "a.v1", "a.v1"], process_containment=True
    )
    assert doc["capabilities"] == {
        "process_containment": True,
        "handler_contracts": ["a.v1", "b.v1"],
    }
    assert advertised_capability(doc, "a.v1") == (True, True)
    assert advertised_capability(doc, "c.v1") == (True, False)
    assert advertised_capability({}, "a.v1") == (False, False)
    assert advertised_capability(None, "a.v1") == (False, False)
    assert advertised_capability({"version": 2, "capabilities": {}}, "a.v1") == (False, False)
    off = supervisor_advertisement(PRODUCTION_PROFILE, handler_contracts=[], process_containment=0)
    assert advertised_capability(off, "a.v1") == (False, False)
