"""Native solver-status gate before vector access (BACKEND-SPEC.md section 13.5, BE-05).

Grants permission to inspect a candidate only. No status alone authorizes publication: a
readable candidate must still be independently validated, and a permitted candidate that
cannot be read or validated is a failure, not a zero-transfer plan. This helper never
substitutes one method for another. Timeout/cancellation are orchestration outcomes, not
native statuses; their precedence and publication rules remain OPEN-30/35.
"""

from dataclasses import dataclass
from enum import StrEnum


class NativeSolverStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"


@dataclass(frozen=True, slots=True)
class SolverStatusGate:
    native_status: NativeSolverStatus
    may_read_candidate: bool
    requires_independent_verification: bool


_READABLE = frozenset({NativeSolverStatus.OPTIMAL, NativeSolverStatus.FEASIBLE})


def classify_solver_status(status: str) -> SolverStatusGate:
    """Classify an exact native status string; no trimming, case folding or aliasing."""
    if not isinstance(status, str):
        raise TypeError(f"status must be a str, got {type(status).__name__}")
    raw = str.__str__(status)
    for member in NativeSolverStatus:
        if member.value == raw:
            readable = member in _READABLE
            return SolverStatusGate(
                native_status=member,
                may_read_candidate=readable,
                requires_independent_verification=readable,
            )
    raise ValueError(f"status must be one of {[m.value for m in NativeSolverStatus]}, got {raw!r}")
