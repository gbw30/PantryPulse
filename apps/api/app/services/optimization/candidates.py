"""Method-independent candidate preparation and conservative donor eligibility."""

from dataclasses import dataclass
from uuid import UUID

from app.schemas.or_inputs import ORScenarioPayload
from app.schemas.or_outputs import Exclusion, ProjectionReport
from app.services.optimization.projection import simulate
from app.services.optimization.scenario import usable, verify_scenario
from app.services.transfer_modes import check_mode_route


@dataclass(frozen=True)
class RouteCandidate:
    route_id: UUID
    product_id: UUID
    source_id: UUID
    destination_id: UUID
    eta_days: int
    upper: int
    lot_ids: tuple[UUID, ...]
    cost_minor: int


@dataclass(frozen=True)
class PreparedProblem:
    scenario: ORScenarioPayload
    baseline: ProjectionReport
    candidates: tuple[RouteCandidate, ...]
    exclusions: tuple[Exclusion, ...]


def prepare_problem(snapshot: ORScenarioPayload) -> PreparedProblem:
    verify_scenario(snapshot)
    package = snapshot.package
    baseline = simulate(snapshot)
    sites = {x.id: x for x in package.sites}
    products = {x.id: x for x in package.products}
    routes = {x.id: x for x in package.routes}
    reserves = {(x.site_id, x.product_id): x.floors for x in package.reserves}
    candidates, exclusions = [], []
    for route in package.routes:
        permitted = check_mode_route(
            snapshot.transfer_mode,
            route.source_id,
            sites[route.source_id].role,
            route.destination_id,
            sites[route.destination_id].role,
            route.enabled,
        )
        if not permitted.allowed:
            exclusions.append(Exclusion(resource_id=str(route.id), code=permitted.reason.value))
        elif route.eta_days >= snapshot.planning_days:
            exclusions.append(Exclusion(resource_id=str(route.id), code="ARRIVAL_OUTSIDE_WINDOW"))
    for key in snapshot.loading_order:
        route, product = routes[key.route_id], products[key.product_id]
        arrival = package.first_planning_date
        from datetime import timedelta

        arrival += timedelta(days=route.eta_days)
        lots = tuple(
            sorted(
                (
                    lot
                    for lot in package.inventory
                    if lot.site_id == route.source_id
                    and lot.product_id == product.id
                    and usable(lot)
                    and lot.dispatchable
                    and lot.expires_on > arrival
                ),
                key=lambda lot: (lot.expires_on, lot.available_on, str(lot.id)),
            )
        )
        source_days = [
            d for d in baseline.days if (d.site_id, d.product_id) == (route.source_id, product.id)
        ]
        # OR-DEC-003 [PROVISIONAL]: already-short sources cannot donate this product.
        protected = all(
            d.unmet == 0 and d.on_hand >= reserve
            for d, reserve in zip(source_days, reserves[route.source_id, product.id], strict=True)
        )
        need = sum(
            d.unmet
            for d in baseline.days
            if (d.site_id, d.product_id) == (route.destination_id, product.id)
            and d.day < package.first_planning_date + timedelta(days=snapshot.planning_days)
        )
        upper = min(
            sum(lot.free_units for lot in lots),
            need,
            route.capacity.residual // product.handling_coefficient,
        )
        if not protected:
            exclusions.append(
                Exclusion(resource_id=f"{route.id}:{product.id}", code="DONOR_BASELINE_PROTECTION")
            )
            upper = 0
        if not lots:
            exclusions.append(
                Exclusion(resource_id=f"{route.id}:{product.id}", code="NO_ELIGIBLE_SOURCE_LOTS")
            )
        candidates.append(
            RouteCandidate(
                route.id,
                product.id,
                route.source_id,
                route.destination_id,
                route.eta_days,
                upper,
                tuple(lot.id for lot in lots),
                next(c.cost_minor for c in route.costs if c.product_id == product.id),
            )
        )
    return PreparedProblem(snapshot, baseline, tuple(candidates), tuple(exclusions))
