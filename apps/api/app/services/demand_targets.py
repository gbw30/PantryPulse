"""BE-03: round dated demand estimates to whole-unit targets before aggregation.

Contract: docs/pantrypulse/BACKEND-SPEC.md section 13.3 (basis BD-17).

Pure and deterministic. The caller passes final per-day scenario estimates for one
already selected site/product/window. This helper does not fill gaps, choose a
quantile or buffer, subtract inventory or validate storage/solver magnitude limits
(OPEN-24).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

__all__ = ["RoundedDailyTarget", "RoundedDemandTargets", "round_daily_targets"]


@dataclass(frozen=True, slots=True)
class RoundedDailyTarget:
    day: date
    target: int


@dataclass(frozen=True, slots=True)
class RoundedDemandTargets:
    points: tuple[RoundedDailyTarget, ...]
    total_target: int


def _exact_ceiling(value: Decimal) -> int:
    """Mathematical ceiling of a finite nonnegative Decimal, independent of the context.

    int(Decimal) truncates toward zero exactly, and Decimal == int comparison is
    exact, so no operation here is subject to context precision or traps.
    """
    truncated = int(value)
    if value == truncated:
        return truncated
    return truncated + 1


def round_daily_targets(
    points: Sequence[tuple[date, Decimal]],
) -> RoundedDemandTargets:
    """Return per-day ceil(estimate) targets and their sum, rounding before summing.

    Raises TypeError for wrong Python types and ValueError for invalid values.
    Every input is type-checked, then value-checked, before any result is built.
    """
    if not isinstance(points, Sequence) or isinstance(points, str | bytes | bytearray):
        raise TypeError("points must be a sequence of (date, Decimal) pairs")

    for pair in points:
        if not isinstance(pair, tuple | list) or len(pair) != 2:
            raise TypeError("each point must be a (date, Decimal) pair")
        day, estimate = pair
        if isinstance(day, datetime) or not isinstance(day, date):
            raise TypeError("point day must be a datetime.date, not a datetime or other type")
        if not isinstance(estimate, Decimal):
            raise TypeError("point estimate must be a decimal.Decimal")

    if len(points) == 0:
        raise ValueError("points must not be empty")

    previous: date | None = None
    for day, estimate in points:
        if not estimate.is_finite():
            raise ValueError(f"estimate for {day.isoformat()} must be finite")
        if estimate < 0:
            raise ValueError(f"estimate for {day.isoformat()} must be nonnegative")
        if previous is not None:
            if day == previous:
                raise ValueError(f"duplicate day {day.isoformat()}")
            if day < previous:
                raise ValueError("days must be strictly increasing")
        previous = day

    rounded = tuple(
        RoundedDailyTarget(day=day, target=_exact_ceiling(estimate)) for day, estimate in points
    )
    return RoundedDemandTargets(
        points=rounded,
        total_target=sum(p.target for p in rounded),
    )
