"""Pure deterministic loading; independent from all CP-SAT construction."""

from datetime import timedelta

from app.schemas.or_outputs import RouteQuantity, TransferAssignment
from app.services.optimization.candidates import PreparedProblem


def pack(
    problem: PreparedProblem, quantities: tuple[RouteQuantity, ...]
) -> tuple[TransferAssignment, ...]:
    keys = {(q.route_id, q.product_id): q.units for q in quantities}
    if len(keys) != len(quantities):
        raise ValueError("DUPLICATE_ROUTE_QUANTITY")
    allowed = {(c.route_id, c.product_id) for c in problem.candidates}
    if set(keys) - allowed:
        raise ValueError("UNKNOWN_OR_FORBIDDEN_CANDIDATE")
    lots = {lot.id: lot for lot in problem.scenario.package.inventory}
    balances = {lot.id: lot.free_units for lot in lots.values()}
    assignments = []
    for c in problem.candidates:
        remaining = keys.get((c.route_id, c.product_id), 0)
        if remaining > c.upper:
            raise ValueError("CANDIDATE_BOUND_EXCEEDED")
        # OR-DEC-004 [PROVISIONAL]: shared residual chains enforce route-order hard FEFO.
        for lot_id in c.lot_ids:
            lot = lots[lot_id]
            loaded = min(remaining, balances[lot_id])
            balances[lot_id] -= loaded
            remaining -= loaded
            if loaded:
                assignments.append(
                    TransferAssignment(
                        original_lot_id=lot_id,
                        route_id=c.route_id,
                        source_id=c.source_id,
                        destination_id=c.destination_id,
                        product_id=c.product_id,
                        unit=lot.unit,
                        units=loaded,
                        departure=problem.scenario.package.first_planning_date,
                        arrival=problem.scenario.package.first_planning_date
                        + timedelta(days=c.eta_days),
                        expires_on=lot.expires_on,
                        source_revision=lot.source_revision,
                        cost_minor=c.cost_minor * loaded,
                    )
                )
        if remaining:
            raise ValueError("INSUFFICIENT_ORIGINAL_SOURCE_STOCK")
    return tuple(assignments)
