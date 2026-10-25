"""OR-local network replay; no changes to the inventory service."""


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
