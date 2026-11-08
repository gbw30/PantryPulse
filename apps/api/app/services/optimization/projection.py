"""OR-local network replay; no changes to the inventory service."""

from dataclasses import dataclass
from datetime import date


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
    from app.services.optimization.kernel import KernelLot, project_kernel
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


# --- or-input-v3 (v1) -------------------------------------------------------------------------


@dataclass(frozen=True)
class DayV3:
    location_id: str
    product_id: str
    day: date
    demand: int
    served: int
    unmet: int
    expired: int  # units left unsold after expiring on this day (pre-expired stock: day 1)
    on_hand: int  # end of day, before that day's expiries are written off


@dataclass(frozen=True)
class SublotV3:
    transfer_id: str
    batch_id: str
    location_id: str
    units: int
    consumed: tuple[int, ...]  # per planning day at the receiver
    expired: int


@dataclass(frozen=True)
class ProjectionV3:
    days: tuple[DayV3, ...]
    sublots: tuple[SublotV3, ...]


def lot_ids_v3():
    """Kernel lot identities; the CP model uses the same ones so FEFO ties break identically."""
    return (
        lambda batch_id: f"b:{batch_id}",
        lambda inbound_id: f"i:{inbound_id}",
        lambda transfer_id, batch_id: f"s:{transfer_id}:{batch_id}",
    )


def project_v3(
    scenario, packed=(), *, include_inbound_transfers=True, locations=None
) -> ProjectionV3:
    """Dated FEFO replay of an or-input-v3 scenario with a packed plan (v3.pack).

    Seven planning days plus one sentinel day with no demand, so a batch expiring on day 7 is
    written off inside the horizon. include_inbound_transfers=False gives the sender-protection
    view (BD-49): outgoing debits stay, proposed arrivals are left out. locations limits the
    replay to those locations (each location × product series is independent once packed).
    """
    from datetime import timedelta

    from app.services.optimization.kernel import KernelLot, project_kernel
    from app.services.optimization.v3 import dates

    bid, iid, sid = lot_ids_v3()
    days = dates(scenario)
    points = (*days, days[-1] + timedelta(days=1))
    first = scenario.first_planning_date
    demand = {(d.location_id, d.product_id): d.targets for d in scenario.demand}
    debit: dict[str, int] = {}
    lots: dict[tuple[str, str], list] = {}
    sublot_meta = {}
    for p in packed:
        for batch_id, units in p.splits:
            debit[batch_id] = debit.get(batch_id, 0) + units
    batches = {b.id: b for b in scenario.batches}
    for b in scenario.batches:
        units = b.quantity - debit.get(b.id, 0)
        if units < 0:
            raise ValueError("SOURCE_OVERDRAWN")
        lots.setdefault((b.location_id, b.product_id), []).append(
            KernelLot(bid(b.id), units, first, b.expiry_date, False)
        )
    for i in scenario.inbound:
        lots.setdefault((i.location_id, i.product_id), []).append(
            KernelLot(iid(i.id), i.quantity, i.arrival_date, i.expiry_date, True)
        )
    if include_inbound_transfers:
        for p in packed:
            t = p.transfer
            for batch_id, units in p.splits:
                key = sid(t.id, batch_id)
                sublot_meta[key] = (t.id, batch_id, t.to_location_id)
                lots.setdefault((t.to_location_id, t.product_id), []).append(
                    KernelLot(key, units, t.arrival_date, batches[batch_id].expiry_date, True)
                )
    rows, sublots = [], []
    for key in sorted(set(demand) | set(lots)):
        if locations is not None and key[0] not in locations:
            continue
        targets = (*demand.get(key, (0,) * len(days)), 0)
        out, flows = project_kernel(
            tuple(zip(points, targets, strict=True)), tuple(lots.get(key, ()))
        )
        for i, d in enumerate(out[:-1]):
            expired = out[i + 1].expired + (out[0].expired if i == 0 else 0)
            rows.append(DayV3(*key, d.day, d.demand, d.served, d.unmet, expired, d.on_hand))
        for f in flows:
            if f.lot.id in sublot_meta:
                transfer, batch_id, location = sublot_meta[f.lot.id]
                sublots.append(
                    SublotV3(
                        transfer, batch_id, location, f.lot.units, f.consumed[:-1], sum(f.expired)
                    )
                )
    return ProjectionV3(tuple(rows), tuple(sublots))
