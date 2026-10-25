"""Pure dated lost-sales projection over explicitly eligible lots/confirmed arrivals.

VP event ordering: arrivals, expiry after its stated day, then FEFO service.
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
    # Experimental wrapper retains its explicit null-expiry allowance; OR filters separately.
    from app.services.inventory.or_kernel import KernelLot, project_kernel

    modeled = tuple(
        KernelLot(
            str(lot.lot_id),
            lot.units,
            lot.available_on,
            lot.expires_on,
            lot.supply_kind == "CONFIRMED",
        )
        for lot in lots
        if lot.eligibility == "ELIGIBLE"
    )
    projected, _ = project_kernel(tuple((p.day, p.units) for p in demand.days), modeled)
    return tuple(
        ProjectionDay(
            day=p.day,
            demand=p.demand,
            received=p.received,
            expired=p.expired,
            served=p.served,
            unmet=p.unmet,
            on_hand=p.on_hand,
        )
        for p in projected
    )


def simulate(scenario, assignments=(), *, include_planned_inbound=True):
    """Operational adapter to the shared FEFO recurrence, with frozen lot lineage."""
    from app.schemas.or_outputs import (
        Exclusion,
        LotTrajectory,
        ProjectionReport,
        TransitDay,
    )
    from app.schemas.or_outputs import (
        ProjectionDay as ORProjectionDay,
    )
    from app.services.inventory.or_kernel import KernelLot, project_kernel
    from app.services.optimization.scenario import usable

    package = scenario.package
    outgoing = {}
    for transfer in assignments:
        outgoing[transfer.original_lot_id] = (
            outgoing.get(transfer.original_lot_id, 0) + transfer.units
        )
    rows, trajectories, exclusions = [], [], []
    for series in scenario.demand:
        lots, origins, proposed = [], {}, set()
        for lot in package.inventory:
            if (lot.site_id, lot.product_id) != (series.site_id, series.product_id):
                continue
            if not usable(lot):
                exclusions.append(
                    Exclusion(resource_id=str(lot.id), code="UNUSABLE_OR_UNKNOWN_EXPIRY")
                )
                continue
            units = lot.free_units - outgoing.get(lot.id, 0)
            if units < 0:
                raise ValueError("SOURCE_LOT_OVERDRAWN")
            key = str(lot.id)
            lots.append(KernelLot(key, units, lot.available_on, lot.expires_on, False))
            origins[key] = lot.id
        for lot in package.confirmed_arrivals:
            if (lot.site_id, lot.product_id) != (series.site_id, series.product_id):
                continue
            if not usable(lot):
                exclusions.append(
                    Exclusion(resource_id=str(lot.id), code="UNUSABLE_OR_UNKNOWN_EXPIRY")
                )
                continue
            if lot.expires_on is not None and lot.expires_on < lot.available_on:
                exclusions.append(
                    Exclusion(resource_id=str(lot.id), code="ARRIVAL_EXPIRED_ON_RECEIPT")
                )
            key = str(lot.id)
            lots.append(KernelLot(key, lot.units, lot.available_on, lot.expires_on, True))
            origins[key] = lot.id
        if include_planned_inbound:
            for transfer in assignments:
                if (transfer.destination_id, transfer.product_id) != (
                    series.site_id,
                    series.product_id,
                ):
                    continue
                key = f"{transfer.original_lot_id}:{transfer.route_id}"
                lots.append(
                    KernelLot(key, transfer.units, transfer.arrival, transfer.expires_on, True)
                )
                origins[key] = transfer.original_lot_id
                proposed.add(key)
        days, flows = project_kernel(tuple((p.day, p.units) for p in series.days), tuple(lots))
        rows.extend(
            ORProjectionDay(
                site_id=series.site_id,
                product_id=series.product_id,
                day=p.day,
                demand=p.demand,
                received=p.received,
                expired=p.expired,
                served=p.served,
                unmet=p.unmet,
                on_hand=p.on_hand,
            )
            for p in days
        )
        trajectories.extend(
            LotTrajectory(
                id=t.lot.id,
                original_lot_id=origins[t.lot.id],
                site_id=series.site_id,
                product_id=series.product_id,
                arrival=t.lot.available_on,
                expires_on=t.lot.expires_on,
                initial_units=t.lot.units,
                consumed=t.consumed,
                expired=t.expired,
                end_balances=t.end_balances,
                proposed=t.lot.id in proposed,
            )
            for t in flows
        )
    dates = tuple(p.day for p in scenario.demand[0].days)
    transit = tuple(
        TransitDay(
            day=day,
            product_id=p.id,
            units=sum(
                t.units
                for t in assignments
                if t.product_id == p.id and t.departure <= day < t.arrival
            ),
        )
        for day in dates
        for p in package.products
    )
    blocked = tuple(
        (
            p.id,
            sum(
                lot.physical_units - lot.free_units
                for lot in package.inventory
                if lot.product_id == p.id
            ),
        )
        for p in package.products
    )
    return ProjectionReport(
        days=tuple(rows),
        lots=tuple(trajectories),
        transit=transit,
        exclusions=tuple(exclusions),
        blocked_units=blocked,
    )
