"""Pure dated lost-sales projection over explicitly eligible lots/confirmed arrivals.

Historical forecasting API retained during main/VP integration. Experimental event
ordering: arrivals, expiry (D unusable on D), then FEFO service. The operational
project_inventory entry point uses the later accepted inclusive-expiry contract.
No inventory writes, allocation, inferred donation eligibility, or same-batch relay.
"""

from datetime import date, timedelta
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.services.forecasting.handoff import PlanningSeries
from app.services.forecasting.schemas import Contract, SeriesKey


class ProjectionLot(Contract):
    lot_id: UUID
    key: SeriesKey
    source_version: str = Field(min_length=1)
    unit: str
    units: int = Field(ge=0, strict=True)
    available_on: date
    expires_on: date | None
    eligibility: Literal["ELIGIBLE", "HELD", "UNKNOWN"]
    supply_kind: Literal["ON_HAND", "CONFIRMED"]


class ProjectionDay(Contract):
    day: date
    demand: int
    received: int
    expired: int
    served: int
    unmet: int
    on_hand: int


def project_daily(
    demand: PlanningSeries, *, lots: tuple[ProjectionLot, ...]
) -> tuple[ProjectionDay, ...]:
    demand = PlanningSeries.model_validate(demand.model_dump())
    lots = tuple(ProjectionLot.model_validate(lot.model_dump()) for lot in lots)
    if demand.scope.key.target_type != "DEMAND":
        raise ValueError("Projection requires a demand target")
    if len({lot.lot_id for lot in lots}) != len(lots):
        raise ValueError("A lot/arrival cannot be counted twice")
    if any(lot.key != demand.scope.key or lot.unit != demand.scope.unit for lot in lots):
        raise ValueError("Projection lot ownership, series or unit mismatch")
    days = [point.day for point in demand.days]
    if len(days) != 7 or any(
        b - a != timedelta(days=1) for a, b in zip(days, days[1:], strict=False)
    ):
        raise ValueError("Projection requires seven ordered demand dates")
    if any(lot.supply_kind == "ON_HAND" and lot.available_on > days[0] for lot in lots):
        raise ValueError("Future stock must be explicitly confirmed supply")
    eligible = sorted(
        (lot for lot in lots if lot.eligibility == "ELIGIBLE"),
        key=lambda lot: (lot.expires_on or date.max, lot.available_on, str(lot.lot_id)),
    )
    balances = {lot.lot_id: lot.units for lot in eligible}
    result = []
    for point in demand.days:
        received = sum(
            lot.units
            for lot in eligible
            if lot.available_on == point.day and lot.supply_kind == "CONFIRMED"
        )
        expired = 0
        remaining = point.units
        for lot in eligible:
            if lot.available_on > point.day:
                continue
            balance = balances[lot.lot_id]
            if lot.expires_on is not None and lot.expires_on <= point.day:
                expired += balance
                balances[lot.lot_id] = 0
                continue
            served = min(balance, remaining)
            balances[lot.lot_id] -= served
            remaining -= served
        result.append(
            ProjectionDay(
                day=point.day,
                demand=point.units,
                received=received,
                expired=expired,
                served=point.units - remaining,
                unmet=remaining,
                on_hand=sum(
                    balances[lot.lot_id] for lot in eligible if lot.available_on <= point.day
                ),
            )
        )
    return tuple(result)
