"""Independent physical replay/checker. Never imports CP or objective attachments."""

from collections import defaultdict

from app.schemas.or_outputs import Candidate, VerificationReport
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.canonical import operational_hash
from app.services.optimization.metrics import evaluate
from app.services.optimization.packing import pack
from app.services.optimization.projection import simulate


def verify(problem, candidate: Candidate, method=None) -> VerificationReport:
    scenario = problem.scenario
    violations = []
    projection = metrics = None
    candidate_hash = None
    try:
        raw = (
            candidate.model_dump(warnings=False) if isinstance(candidate, Candidate) else candidate
        )
        candidate = Candidate.model_validate(raw)
        # OR-DEC-009 [PROVISIONAL]: invalid/unvalidated input has no candidate identity.
        candidate_hash = operational_hash(candidate)
        problem = prepare_problem(scenario)
        expected = pack(problem, candidate.route_quantities)
        if expected != candidate.assignments:
            violations.append("PACKING_FEFO_LINEAGE_MISMATCH")
        projection = simulate(scenario, candidate.assignments)
        package = scenario.package
        products = {p.id: p for p in package.products}
        routes = {r.id: r for r in package.routes}
        site_caps = {c.site_id: c for c in package.capacities.sites}
        route_load, source_load, receiving, incoming, outgoing = (
            defaultdict(int) for _ in range(5)
        )
        total_handling = 0
        for t in candidate.assignments:
            h = t.units * products[t.product_id].handling_coefficient
            route_load[t.route_id] += h
            source_load[t.source_id] += h
            receiving[t.destination_id, t.arrival] += h
            incoming[t.destination_id, t.product_id] += t.units
            outgoing[t.source_id, t.product_id] += t.units
            total_handling += h
        # OR-DEC-017 [PROVISIONAL]: product-coupled residual handling/storage limits.
        if total_handling > package.capacities.global_handling.residual:
            violations.append("GLOBAL_HANDLING_CAPACITY")
        for rid, load in route_load.items():
            if load > routes[rid].capacity.residual:
                violations.append("ROUTE_CAPACITY")
        for sid, load in source_load.items():
            if load > site_caps[sid].source.residual:
                violations.append("SOURCE_HANDLING_CAPACITY")
        dates = tuple(p.day for p in scenario.demand[0].days)
        for (sid, day), load in receiving.items():
            if day not in dates or load > site_caps[sid].receiving[dates.index(day)].residual:
                violations.append("RECEIVING_CAPACITY")
        for site in package.sites:
            for i, day in enumerate(dates):
                storage = sum(
                    p.on_hand * products[p.product_id].handling_coefficient
                    for p in projection.days
                    if p.site_id == site.id and p.day == day
                )
                if storage > site_caps[site.id].storage[i].residual:
                    violations.append("STORAGE_CAPACITY")
        budget = package.capacities.cost_budget_minor
        if budget is not None and sum(t.cost_minor for t in candidate.assignments) > budget:
            violations.append("TRANSPORT_COST_BUDGET")
        window = set(dates[: scenario.planning_days])
        for (site, product), units in incoming.items():
            baseline_need = sum(
                d.unmet
                for d in problem.baseline.days
                if (d.site_id, d.product_id) == (site, product) and d.day in window
            )
            if units > baseline_need:
                violations.append("BASELINE_NEED_OVERDELIVERY")
        for lot in projection.lots:
            if lot.proposed and (
                sum(lot.consumed[: scenario.planning_days]) != lot.initial_units
                or sum(lot.expired[: scenario.planning_days]) != 0
            ):
                violations.append("TRANSFER_NOT_CONSUMED_WITHIN_WINDOW")
            if sum(lot.consumed) + sum(lot.expired) + lot.end_balances[-1] != (
                lot.initial_units if lot.arrival <= dates[-1] else 0
            ):
                violations.append("LOT_CONSERVATION")
        protected = simulate(scenario, candidate.assignments, include_planned_inbound=False)
        reserves = {(r.site_id, r.product_id): r.floors for r in package.reserves}
        for key in outgoing:
            days = [d for d in protected.days if (d.site_id, d.product_id) == key]
            if any(
                d.unmet or d.on_hand < floor for d, floor in zip(days, reserves[key], strict=True)
            ):
                violations.append("DONOR_NO_INBOUND_PROTECTION")
        metrics = evaluate(scenario, projection, candidate.assignments)
        if candidate.claimed_metrics is not None and candidate.claimed_metrics != metrics:
            violations.append("CLAIMED_METRICS_MISMATCH")
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        violations.append(str(exc).split("\n")[0])
    return VerificationReport(
        passed=not violations,
        violations=tuple(dict.fromkeys(violations)),
        projection=projection,
        metrics=metrics,
        operational_hash=scenario.operational_hash,
        candidate_hash=candidate_hash,
    )
