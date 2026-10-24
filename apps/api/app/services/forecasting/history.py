"""BE-06: align one historical target series to a daily calendar without imputation.

Contract: docs/pantrypulse/BACKEND-SPEC.md section 13.6 (basis BD-03, BD-06, BD-27).

Pure and deterministic. The caller supplies one already selected, revision-resolved
series whose days are already site-local calendar dates (timezone handling is
OPEN-06). This helper never imputes, never turns null into zero, never appends
forecast dates and does not decide whether the result is usable by a provider
(OPEN-13) or bound public import sizes (OPEN-29).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AlignedObservation:
    day: date
    quantity: Decimal | None
    source_present: bool


def _is_plain_date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def align_history(
    start_date: date,
    cutoff_date: date,
    observations: Sequence[tuple[date, Decimal | None]],
) -> tuple[AlignedObservation, ...]:
    """Return exactly one AlignedObservation per day from start_date to cutoff_date.

    A missing row gives quantity=None/source_present=False; an explicit null row gives
    quantity=None/source_present=True; supplied Decimals are kept unchanged.

    Raises TypeError for wrong Python types and ValueError for invalid values. All
    types are checked before any value, and the whole input is validated before the
    calendar is built.
    """
    if not _is_plain_date(start_date):
        raise TypeError("start_date must be a datetime.date, not a datetime or other type")
    if not _is_plain_date(cutoff_date):
        raise TypeError("cutoff_date must be a datetime.date, not a datetime or other type")
    if not isinstance(observations, Sequence) or isinstance(observations, str | bytes | bytearray):
        raise TypeError("observations must be a sequence of (date, Decimal | None) pairs")

    for pair in observations:
        if not isinstance(pair, tuple | list) or len(pair) != 2:
            raise TypeError("each observation must be a (date, Decimal | None) pair")
        day, quantity = pair
        if not _is_plain_date(day):
            raise TypeError("observation day must be a datetime.date, not a datetime")
        if quantity is not None and not isinstance(quantity, Decimal):
            raise TypeError("observation quantity must be a decimal.Decimal or None")

    if start_date > cutoff_date:
        raise ValueError("start_date must be on or before cutoff_date")

    by_day: dict[date, Decimal | None] = {}
    for day, quantity in observations:
        if quantity is not None:
            if not quantity.is_finite():
                raise ValueError(f"quantity for {day.isoformat()} must be finite")
            if quantity < 0:
                raise ValueError(f"quantity for {day.isoformat()} must be nonnegative")
        if day < start_date:
            raise ValueError(f"observation {day.isoformat()} is before start_date")
        if day > cutoff_date:
            raise ValueError(f"observation {day.isoformat()} is after cutoff_date")
        if day in by_day:
            raise ValueError(f"duplicate observation day {day.isoformat()}")
        by_day[day] = quantity

    calendar = (
        start_date + timedelta(days=offset) for offset in range((cutoff_date - start_date).days + 1)
    )
    return tuple(
        AlignedObservation(day=day, quantity=by_day.get(day), source_present=day in by_day)
        for day in calendar
    )
