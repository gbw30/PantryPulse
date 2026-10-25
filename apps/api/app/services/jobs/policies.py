"""Pure transition, admission, freshness and deadline policies (WQ-01).

No clock, database or process access: callers pass database-time ages and elapsed seconds.
"""

from collections.abc import Sequence
from datetime import datetime

from app.services.jobs.contracts import (
    RETRYABLE_STATES,
    AdmissionOutcome,
    AttemptState,
    HeartbeatStatus,
    OperationKind,
    ReasonCode,
    RuntimeProfile,
    StepOutcome,
    StepRunIf,
    StepSpec,
    StepStatus,
    StepWindow,
    SupervisorState,
)

COMPARISON_METHODS = ("CLASSICAL_GP", "EGP_PI_INSPIRED")

_S = AttemptState
ALLOWED_TRANSITIONS: dict[AttemptState, frozenset[AttemptState]] = {
    _S.QUEUED: frozenset({_S.RUNNING, _S.CANCELLED, _S.EXPIRED, _S.FAILED}),
    _S.RUNNING: frozenset({_S.SUCCEEDED, _S.PARTIAL, _S.FAILED, _S.STOPPING}),
    _S.STOPPING: frozenset({_S.FAILED, _S.TIMED_OUT, _S.INTERRUPTED, _S.CANCELLED}),
}


class InvalidTransition(ValueError):
    pass


def is_allowed_transition(source: AttemptState, target: AttemptState) -> bool:
    return AttemptState(target) in ALLOWED_TRANSITIONS.get(AttemptState(source), frozenset())


def require_transition(source: AttemptState, target: AttemptState) -> None:
    if not is_allowed_transition(source, target):
        raise InvalidTransition(f"attempt transition {source} -> {target} is not allowed")


def can_retry(state: AttemptState) -> bool:
    return AttemptState(state) in RETRYABLE_STATES


_STOP_REASON_STATES = {
    ReasonCode.CANCEL_REQUESTED: _S.CANCELLED,
    ReasonCode.EXECUTION_DEADLINE_EXCEEDED: _S.TIMED_OUT,
    ReasonCode.WORKER_LOST: _S.INTERRUPTED,
    ReasonCode.SHUTDOWN_IMMEDIATE: _S.INTERRUPTED,
    ReasonCode.OWNERSHIP_LOST: _S.INTERRUPTED,
}


def final_state_for_stop_reason(reason: ReasonCode) -> AttemptState:
    """Terminal state after STOPPING, decided by the recorded stop reason."""
    return _STOP_REASON_STATES.get(ReasonCode(reason), _S.FAILED)


def heartbeat_status(age_s: float | None, profile: RuntimeProfile) -> HeartbeatStatus:
    """Fresh only when 0 <= age < stale bound; a future heartbeat fails closed."""
    if age_s is None:
        return HeartbeatStatus.MISSING
    if age_s < 0:
        return HeartbeatStatus.FUTURE
    if age_s < profile.heartbeat_stale_s:
        return HeartbeatStatus.FRESH
    return HeartbeatStatus.STALE


def is_queue_expired(now: datetime, queue_deadline: datetime) -> bool:
    if now.tzinfo is None or queue_deadline.tzinfo is None:
        raise ValueError("queue expiry requires timezone-aware datetimes")
    return now >= queue_deadline


def admission_outcome(
    *,
    supervisor_state: SupervisorState,
    heartbeat: HeartbeatStatus,
    capable: bool,
    recovery_required: bool,
    contract_advertised: bool,
    queued_count: int,
    profile: RuntimeProfile,
) -> AdmissionOutcome:
    """Healthy-busy admits within the global waiter bound; unavailability is checked first."""
    available = (
        SupervisorState(supervisor_state) is SupervisorState.READY
        and HeartbeatStatus(heartbeat) is HeartbeatStatus.FRESH
        and capable is True
        and recovery_required is False
        and contract_advertised is True
    )
    if not available:
        return AdmissionOutcome.COMPUTE_UNAVAILABLE
    if queued_count >= profile.max_queued:
        return AdmissionOutcome.COMPUTE_QUEUE_FULL
    return AdmissionOutcome.ACCEPT


def operation_budget_s(kind: OperationKind, profile: RuntimeProfile) -> float:
    return {
        OperationKind.FORECAST: profile.forecast_total_s,
        OperationKind.ALLOCATION: profile.allocation_total_s,
        OperationKind.COMPARISON: profile.comparison_total_s,
    }[OperationKind(kind)]


def forecast_steps(profile: RuntimeProfile, *, fallback_allowed: bool) -> tuple[StepSpec, ...]:
    if not fallback_allowed:
        return (StepSpec(name="primary", min_s=profile.method_min_s),)
    return (
        StepSpec(
            name="primary", min_s=profile.method_min_s, cutoff_s=profile.forecast_primary_cutoff_s
        ),
        StepSpec(
            name="fallback",
            min_s=profile.method_min_s,
            run_if=StepRunIf.AFTER_FALLBACK_ELIGIBLE_FAILURE,
        ),
    )


def allocation_steps(profile: RuntimeProfile, method: str) -> tuple[StepSpec, ...]:
    return (StepSpec(name=method, min_s=profile.method_min_s, max_s=profile.method_wall_s),)


def comparison_steps(
    profile: RuntimeProfile, methods: Sequence[str] = COMPARISON_METHODS
) -> tuple[StepSpec, ...]:
    """Sequential methods with equivalent per-method limits inside one parent budget."""
    return tuple(
        StepSpec(name=m, min_s=profile.method_min_s, max_s=profile.method_wall_s) for m in methods
    )


def should_run_step(step: StepSpec, previous: Sequence[StepOutcome]) -> bool:
    if step.run_if is StepRunIf.ALWAYS:
        return True
    if not previous:
        return False
    last = previous[-1]
    return last.status in (StepStatus.FAILED, StepStatus.TIMED_OUT) and last.fallback_eligible


def plan_step_window(
    step: StepSpec, *, elapsed_s: float, budget_s: float, profile: RuntimeProfile
) -> StepWindow | None:
    """Stop offsets for a step starting ``elapsed_s`` into the attempt, or None for NOT_RUN.

    The publication reserve and every cutoff stay inside the original budget; a step never
    receives a fresh allowance because it starts late.
    """
    if elapsed_s < 0:
        raise ValueError("elapsed_s must be nonnegative")
    hard = budget_s - profile.publication_reserve_s
    if step.cutoff_s is not None:
        hard = min(hard, step.cutoff_s)
    if step.max_s is not None:
        hard = min(hard, elapsed_s + step.max_s)
    if hard - elapsed_s < step.min_s:
        return None
    soft = max(elapsed_s, hard - profile.stop_grace_s)
    force = max(soft, hard - profile.kill_margin_s)
    return StepWindow(
        name=step.name, start_s=elapsed_s, soft_stop_s=soft, force_stop_s=force, hard_stop_s=hard
    )


def supervisor_advertisement(
    profile: RuntimeProfile, *, handler_contracts: Sequence[str], process_containment: bool
) -> dict:
    """Effective limits plus runtime capabilities a supervisor records for admission (A5)."""
    document = profile.effective_limits()
    document["capabilities"] = {
        "process_containment": process_containment is True,
        "handler_contracts": sorted(set(handler_contracts)),
    }
    return document


def advertised_capability(document: object, contract: str) -> tuple[bool, bool]:
    """(capable, contract_advertised) from a stored advertisement; malformed means neither."""
    if not isinstance(document, dict):
        return False, False
    capabilities = document.get("capabilities")
    if document.get("version") != 1 or not isinstance(capabilities, dict):
        return False, False
    contracts = capabilities.get("handler_contracts")
    advertised = isinstance(contracts, list) and contract in contracts
    return capabilities.get("process_containment") is True, advertised


def remaining_budget_s(*, db_remaining_s: float, monotonic_remaining_s: float) -> float:
    """When database wall time and local monotonic accounting disagree, use the smaller."""
    return max(0.0, min(db_remaining_s, monotonic_remaining_s))
