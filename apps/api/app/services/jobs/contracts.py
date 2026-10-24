"""Internal job vocabulary, runtime profile and canonical input identity (WQ-01).

These enums are WQ PROPOSAL internal contracts accepted for the foundation in ADR 0004, not
public V5 enums. A job lifecycle state is never a native solver status, and a completed
operation is never by itself a feasible plan.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from enum import StrEnum
from typing import Any


class OperationKind(StrEnum):
    FORECAST = "FORECAST"
    ALLOCATION = "ALLOCATION"
    COMPARISON = "COMPARISON"


class AttemptState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    INTERRUPTED = "INTERRUPTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


TERMINAL_STATES = frozenset(
    {
        AttemptState.SUCCEEDED,
        AttemptState.FAILED,
        AttemptState.TIMED_OUT,
        AttemptState.INTERRUPTED,
        AttemptState.CANCELLED,
        AttemptState.EXPIRED,
    }
)
NONTERMINAL_STATES = frozenset({AttemptState.QUEUED, AttemptState.RUNNING, AttemptState.STOPPING})
LANE_OCCUPYING_STATES = frozenset({AttemptState.RUNNING, AttemptState.STOPPING})
RETRYABLE_STATES = TERMINAL_STATES - {AttemptState.SUCCEEDED}


class SupervisorState(StrEnum):
    OFFLINE = "OFFLINE"
    STARTING = "STARTING"
    READY = "READY"
    DRAINING = "DRAINING"
    RECOVERING = "RECOVERING"
    QUARANTINED = "QUARANTINED"


class CommandAction(StrEnum):
    SUBMIT = "SUBMIT"
    RETRY = "RETRY"
    CANCEL = "CANCEL"


class AdmissionOutcome(StrEnum):
    ACCEPT = "ACCEPT"
    COMPUTE_UNAVAILABLE = "COMPUTE_UNAVAILABLE"
    COMPUTE_QUEUE_FULL = "COMPUTE_QUEUE_FULL"


class HeartbeatStatus(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    MISSING = "MISSING"
    FUTURE = "FUTURE"


class StepStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    NOT_RUN = "NOT_RUN"


class StepRunIf(StrEnum):
    ALWAYS = "ALWAYS"
    AFTER_FALLBACK_ELIGIBLE_FAILURE = "AFTER_FALLBACK_ELIGIBLE_FAILURE"


class ReasonCode(StrEnum):
    """Safe, stable reason codes recorded on attempts and audit events."""

    QUEUE_DEADLINE_REACHED = "QUEUE_DEADLINE_REACHED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    EXECUTION_DEADLINE_EXCEEDED = "EXECUTION_DEADLINE_EXCEEDED"
    WORKER_LOST = "WORKER_LOST"
    SHUTDOWN_IMMEDIATE = "SHUTDOWN_IMMEDIATE"
    OWNERSHIP_LOST = "OWNERSHIP_LOST"
    SPAWN_FAILED = "SPAWN_FAILED"
    INPUT_INTEGRITY = "INPUT_INTEGRITY"
    UNREGISTERED_CONTRACT = "UNREGISTERED_CONTRACT"
    HANDLER_FAILED = "HANDLER_FAILED"
    CHILD_EXITED_ABNORMALLY = "CHILD_EXITED_ABNORMALLY"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    OUTPUT_TOO_LARGE = "OUTPUT_TOO_LARGE"
    PUBLICATION_REJECTED = "PUBLICATION_REJECTED"
    PUBLICATION_COMMIT_LOST = "PUBLICATION_COMMIT_LOST"
    PARENT_BUDGET_EXHAUSTED = "PARENT_BUDGET_EXHAUSTED"
    STEP_DEADLINE_EXCEEDED = "STEP_DEADLINE_EXCEEDED"
    CLEANUP_UNCONFIRMED = "CLEANUP_UNCONFIRMED"
    PUBLICATION_STORAGE_FAILED = "PUBLICATION_STORAGE_FAILED"


def _positive_finite(name: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite, got {value!r}")


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    """Configured ceilings. Defaults are the accepted V5 values (BD-34–38); a shorter profile
    must be passed explicitly (tests), never silently exceed these ceilings in production."""

    max_queued: int = 2
    queue_wait_s: float = 900
    heartbeat_interval_s: float = 5
    heartbeat_stale_s: float = 15
    forecast_total_s: float = 300
    forecast_primary_cutoff_s: float = 270
    allocation_total_s: float = 25
    method_wall_s: float = 25
    method_search_s: float = 15
    comparison_total_s: float = 60
    stop_grace_s: float = 2
    publication_reserve_s: float = 2
    method_min_s: float = 1
    worker_cpu: float = 6
    worker_memory_gib: float = 8

    def __post_init__(self) -> None:
        if isinstance(self.max_queued, bool) or not isinstance(self.max_queued, int):
            raise ValueError("max_queued must be an int")
        if self.max_queued < 0:
            raise ValueError("max_queued must be nonnegative")
        for f in fields(self):
            if f.name != "max_queued":
                _positive_finite(f.name, getattr(self, f.name))
        if self.heartbeat_interval_s >= self.heartbeat_stale_s:
            raise ValueError("heartbeat interval must be shorter than the staleness bound")
        if self.method_search_s > self.method_wall_s:
            raise ValueError("native search time cannot exceed whole-method wall time")
        if self.method_wall_s > self.comparison_total_s:
            raise ValueError("a method cannot exceed the whole comparison budget")
        if self.forecast_primary_cutoff_s >= self.forecast_total_s:
            raise ValueError("forecast primary cutoff must precede the whole-operation deadline")
        budgets = (self.forecast_total_s, self.allocation_total_s, self.comparison_total_s)
        if self.publication_reserve_s >= min(budgets):
            raise ValueError("publication reserve must fit inside every operation budget")
        if self.stop_grace_s >= min(self.method_wall_s, self.forecast_primary_cutoff_s):
            raise ValueError("stop grace must fit inside the step it stops")

    def within(self, ceiling: "RuntimeProfile") -> bool:
        """True when no time/resource limit exceeds ``ceiling`` (shorter is allowed)."""
        return all(getattr(self, f.name) <= getattr(ceiling, f.name) for f in fields(self))

    def effective_limits(self) -> dict[str, Any]:
        return {
            "version": 1,
            "limits": {f.name: getattr(self, f.name) for f in fields(self)},
        }


PRODUCTION_PROFILE = RuntimeProfile()


@dataclass(frozen=True, slots=True)
class StepSpec:
    """One sequential execution step, run in its own child boundary.

    ``cutoff_s`` is an absolute offset from attempt start by which the step must be stopped
    (forecast primary 270 s). ``max_s`` caps the step's own wall time (25 s per method).
    ``min_s`` is the least remaining allowance worth starting; less means NOT_RUN.
    """

    name: str
    min_s: float
    run_if: StepRunIf = StepRunIf.ALWAYS
    cutoff_s: float | None = None
    max_s: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("step name must be a nonempty string")
        _positive_finite("min_s", self.min_s)
        if self.cutoff_s is not None:
            _positive_finite("cutoff_s", self.cutoff_s)
        if self.max_s is not None:
            _positive_finite("max_s", self.max_s)
        StepRunIf(self.run_if)


@dataclass(frozen=True, slots=True)
class StepWindow:
    """Offsets in seconds from attempt start."""

    name: str
    start_s: float
    soft_stop_s: float
    hard_stop_s: float


@dataclass(frozen=True, slots=True)
class StepOutcome:
    name: str
    status: StepStatus
    output: Mapping[str, Any] | None = None
    error_code: str | None = None
    fallback_eligible: bool = False
    elapsed_s: float | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        """Bounded, payload-free view passed to later steps and stored as diagnostics."""
        return {
            "name": self.name,
            "status": self.status.value,
            "error_code": self.error_code,
            "fallback_eligible": self.fallback_eligible,
            "elapsed_s": self.elapsed_s,
        }


def _reject_non_json(value: Any) -> Any:
    raise TypeError(f"value of type {type(value).__name__} is not JSON-serializable")


def _check_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            _check_keys(item)
    elif isinstance(value, list | tuple):
        for item in value:
            _check_keys(item)


def canonical_json(value: Any) -> str:
    """Deterministic compact JSON; rejects NaN/Infinity, non-string keys and non-JSON types."""
    _check_keys(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_reject_non_json,
    )


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
