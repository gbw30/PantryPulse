"""Native extraction is guarded before the first value read."""

from datetime import timedelta

from app.schemas.or_outputs import Candidate, RouteQuantity, TransferAssignment
from app.services.solver_outcomes import classify_solver_status


def read_candidate(status, solver, physical):
    # BE-05 grants inspection only; publication still requires independent replay.
    if not classify_solver_status(status).may_read_candidate:
        return None
    scenario = physical.problem.scenario
    lots = {lot.id: lot for lot in scenario.package.inventory}
    quantities, assignments = [], []
    for c in physical.problem.candidates:
        units = solver.value(physical.y[c.route_id, c.product_id])
        quantities.append(RouteQuantity(route_id=c.route_id, product_id=c.product_id, units=units))
        for lid in c.lot_ids:
            amount = solver.value(physical.x[lid, c.route_id])
            if amount:
                lot = lots[lid]
                departure = scenario.package.first_planning_date
                assignments.append(
                    TransferAssignment(
                        original_lot_id=lid,
                        route_id=c.route_id,
                        source_id=c.source_id,
                        destination_id=c.destination_id,
                        product_id=c.product_id,
                        unit=lot.unit,
                        units=amount,
                        departure=departure,
                        arrival=departure + timedelta(days=c.eta_days),
                        expires_on=lot.expires_on,
                        source_revision=lot.source_revision,
                        cost_minor=amount * c.cost_minor,
                    )
                )
    return Candidate(route_quantities=tuple(quantities), assignments=tuple(assignments))
