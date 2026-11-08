"""Independent physical replay/checker. Never imports CP or objective attachments."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction

from app.schemas.or_outputs import Candidate, VerificationReport
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.canonical import operational_hash
from app.services.optimization.metrics import evaluate
from app.services.optimization.packing import pack
from app.services.optimization.projection import DayV3, SublotV3, project_v3, simulate
from app.services.optimization.v3 import Packed, Shares, quantities_of, window_days
from app.services.optimization.v3 import pack as pack_v3


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


# --- or-input-v3 (v1): independent plan check and union check ----------------------------------


@dataclass(frozen=True)
class PlanReport:
    passed: bool
    violations: tuple[str, ...]
    days: tuple[DayV3, ...]  # projection with the plan (empty when the plan could not be packed)
    sublots: tuple[SublotV3, ...]
    packed: tuple[Packed, ...]
    above_storage_at_baseline: tuple[tuple[str, date], ...]  # reported, never made infeasible


def cost_minor(route, units: int, handling: int) -> Fraction:
    """Exact transport cost in cents; a route without a cost column costs nothing."""
    if route.cost_per_handling_unit_usd is None:
        return Fraction(0)
    return Fraction(route.cost_per_handling_unit_usd) * 100 * units * handling


def verify_plan(scenario, transfers) -> PlanReport:
    """Replay a v1 plan from the raw frozen scenario only; never reads solver state.

    Recomputes FEFO packing, the dated projection, BD-49/BD-51 and every shared limit of the
    union plan (route per-batch, dispatch, receiving, storage, global handling, cost budget).
    """
    s = scenario
    violations: list[str] = []
    products = {p.id: p for p in s.products}
    routes = {(r.from_location_id, r.to_location_id): r for r in s.routes}
    caps = {c.location_id: c for c in s.capacities}
    for t in transfers:
        route = routes.get((t.from_location_id, t.to_location_id))
        if t.product_id not in products or route is None:
            violations.append("UNKNOWN_ROUTE_OR_PRODUCT")
            continue
        if t.quantity < 1:
            violations.append("EMPTY_TRANSFER")
        if t.ship_date != s.first_planning_date:
            violations.append("SINGLE_DISPATCH_ON_FIRST_PLANNING_DAY")
        if t.arrival_date != s.first_planning_date + timedelta(days=route.travel_days):
            violations.append("ARRIVAL_DATE_MISMATCH")
    if violations:
        return PlanReport(False, tuple(dict.fromkeys(violations)), (), (), (), ())
    try:
        packed = pack_v3(s, quantities_of(transfers))
    except ValueError as exc:
        return PlanReport(False, (str(exc),), (), (), (), ())
    by_key = {
        (p.transfer.product_id, p.transfer.from_location_id, p.transfer.to_location_id): p
        for p in packed
    }
    for t in transfers:
        expected = by_key[t.product_id, t.from_location_id, t.to_location_id].transfer
        if tuple(t.batch_ids) != expected.batch_ids:
            violations.append("PACKING_FEFO_MISMATCH")
    plan = project_v3(s, packed)
    base = project_v3(s)
    window = window_days(s)
    for lot in plan.sublots:
        if sum(lot.consumed[:window]) != lot.units:
            violations.append("TRANSFER_NOT_CONSUMED_IN_WINDOW")  # BD-51 (relaxed in Retail)
    if s.mode == "PANTRY":
        horizon = {d for d in (s.first_planning_date + timedelta(days=i) for i in range(window))}
        need = defaultdict(int)
        for d in base.days:
            if d.day in horizon:
                need[d.location_id, d.product_id] += d.unmet
        incoming = defaultdict(int)
        for p in packed:
            incoming[p.transfer.to_location_id, p.transfer.product_id] += p.transfer.quantity
        if any(units > need[key] for key, units in incoming.items()):
            violations.append("BASELINE_NEED_OVERDELIVERY")
    senders = {(p.transfer.from_location_id, p.transfer.product_id) for p in packed}
    floors = {(r.location_id, r.product_id): r.floor for r in s.reserves}
    for d in project_v3(s, packed, include_inbound_transfers=False).days:
        key = (d.location_id, d.product_id)
        if key in senders and (d.unmet or d.on_hand < floors.get(key, 0)):
            violations.append("DONOR_PROTECTION")  # BD-49
    route_load, dispatch, receiving = defaultdict(int), defaultdict(int), defaultdict(int)
    handling_total, cost = 0, Fraction(0)
    for p in packed:
        t = p.transfer
        h = t.quantity * products[t.product_id].handling_units_per_unit
        route_load[t.from_location_id, t.to_location_id] += h
        dispatch[t.from_location_id] += h
        receiving[t.to_location_id, t.arrival_date] += h
        handling_total += h
        route = routes[t.from_location_id, t.to_location_id]
        cost += cost_minor(route, t.quantity, products[t.product_id].handling_units_per_unit)
    for key, load in route_load.items():
        limit = routes[key].capacity_per_batch
        if limit is not None and load > limit:
            violations.append("ROUTE_CAPACITY")
    for loc, load in dispatch.items():
        limit = caps[loc].dispatch if loc in caps else None
        if limit is not None and load > limit:
            violations.append("DISPATCH_CAPACITY")
    for (loc, _), load in receiving.items():
        limit = caps[loc].receiving if loc in caps else None
        if limit is not None and load > limit:
            violations.append("RECEIVING_CAPACITY")
    if s.global_handling is not None and handling_total > s.global_handling:
        violations.append("GLOBAL_HANDLING_CAPACITY")
    if s.cost_budget_minor is not None and cost > s.cost_budget_minor:
        violations.append("TRANSPORT_COST_BUDGET")
    stock, base_stock = defaultdict(int), defaultdict(int)
    for rows, into in ((plan.days, stock), (base.days, base_stock)):
        for d in rows:
            into[d.location_id, d.day] += d.on_hand * products[d.product_id].handling_units_per_unit
    above = []
    for (loc, day), load in sorted(stock.items()):
        limit = caps[loc].storage if loc in caps else None
        if limit is None:
            continue
        if base_stock[loc, day] > limit:
            above.append((loc, day))
        if load > max(limit, base_stock[loc, day]):
            violations.append("STORAGE_CAPACITY")
    unique = tuple(dict.fromkeys(violations))
    return PlanReport(not unique, unique, plan.days, plan.sublots, packed, tuple(above))


def _ends(route) -> tuple[str, str]:
    return route.from_location_id, route.to_location_id


def only_product(s, product_id, locations=None):
    """The scenario restricted to one product (and optionally to some locations)."""

    def mine(rows):
        return tuple(
            r
            for r in rows
            if r.product_id == product_id and (locations is None or r.location_id in locations)
        )

    return s.model_copy(
        update={
            "products": tuple(p for p in s.products if p.id == product_id),
            "batches": mine(s.batches),
            "demand": mine(s.demand),
            "inbound": mine(s.inbound),
            "reserves": mine(s.reserves),
        }
    )


def residual_shares(s, packed, plan_days, base_days):
    """Each product's room in every raw shared limit, given the rest of a verified plan.

    Shared limits are sums over products, so with every other product's load fixed,
    product_violations of one product's change against these rooms (changed_sender set) is exactly
    verify_plan's verdict on the whole changed plan. Returns product id -> Shares.
    """
    h = {p.id: p.handling_units_per_unit for p in s.products}
    routes = {(r.from_location_id, r.to_location_id): r for r in s.routes}
    caps = {c.location_id: c for c in s.capacities}
    load, own = defaultdict(int), defaultdict(lambda: defaultdict(int))
    cost, own_cost = Fraction(0), defaultdict(Fraction)
    for x in packed:
        t = x.transfer
        units = t.quantity * h[t.product_id]
        for key in (
            ("route", t.from_location_id, t.to_location_id),
            ("dispatch", t.from_location_id),
            ("receiving", t.to_location_id, t.arrival_date),
            ("handling",),
        ):
            load[key] += units
            own[t.product_id][key] += units
        spent = cost_minor(
            routes[t.from_location_id, t.to_location_id], t.quantity, h[t.product_id]
        )
        cost += spent
        own_cost[t.product_id] += spent
    stock, base = defaultdict(int), defaultdict(int)
    own_stock, own_base = defaultdict(lambda: defaultdict(int)), defaultdict(dict)
    for d in plan_days:
        stock[d.location_id, d.day] += d.on_hand * h[d.product_id]
        own_stock[d.product_id][d.location_id, d.day] += d.on_hand * h[d.product_id]
    for d in base_days:
        base[d.location_id, d.day] += d.on_hand * h[d.product_id]
        own_base[d.product_id][d.location_id, d.day] = d.on_hand * h[d.product_id]
    days = sorted({day for _, day in stock} | {k[2] for k in load if k[0] == "receiving"})

    def rooms(product_id) -> Shares:
        mine = own[product_id]

        def room(limit, key):
            return None if limit is None else limit - (load[key] - mine[key])

        def cap(loc, field):
            return getattr(caps[loc], field) if loc in caps else None

        storage = {}
        for loc, day in stock:
            limit = cap(loc, "storage")
            if limit is not None:
                other = stock[loc, day] - own_stock[product_id][loc, day]
                start = own_base[product_id].get((loc, day), 0)
                storage[loc, day] = max(limit, base[loc, day]) - other - start
        return Shares(
            route={k: room(r.capacity_per_batch, ("route", *k)) for k, r in routes.items()},
            dispatch={
                loc.id: room(cap(loc.id, "dispatch"), ("dispatch", loc.id)) for loc in s.locations
            },
            receiving={
                (loc.id, day): room(cap(loc.id, "receiving"), ("receiving", loc.id, day))
                for loc in s.locations
                for day in days
            },
            storage_room=storage,
            global_handling=room(s.global_handling, ("handling",)),
            cost_minor=None
            if s.cost_budget_minor is None
            else s.cost_budget_minor - (cost - own_cost[product_id]),
        )

    return rooms


def product_violations(
    s, product_id, quantities, shares, baseline, *, changed_sender=None
) -> tuple[str, ...]:
    """One product's plan against its pre-split shares (heuristic feasibility probe).

    Projects only the locations the plan touches (projection is per location × product), so a
    heuristic can probe many quantities cheaply. With changed_sender (the rest of the plan already
    passed), only that sender and its receivers are replayed: packing is FEFO per sender, so no
    other location's lots change. Shared limits are always summed over the whole plan. Not a
    substitute for verify_plan, which checks the union plan against the raw scenario before
    anything is published.
    """
    touched = {loc for key in quantities for loc in key[1:]}
    if not touched:
        return ()
    sub = only_product(s, product_id, touched)
    # pack only needs the routes the plan uses; a route outside the full candidate set
    # never reaches here because heuristics probe full candidates only
    sub = sub.model_copy(
        update={"routes": tuple(r for r in s.routes if (product_id, *_ends(r)) in quantities)}
    )
    product = sub.products[0]
    try:
        packed = pack_v3(sub, quantities)
    except ValueError as exc:
        return (str(exc),)
    violations = []
    window = window_days(s)
    replay = None
    if changed_sender is not None:
        replay = {changed_sender} | {k[2] for k in quantities if k[1] == changed_sender}
    plan = project_v3(sub, packed, locations=replay)
    for lot in plan.sublots:
        if sum(lot.consumed[:window]) != lot.units:
            violations.append("TRANSFER_NOT_CONSUMED_IN_WINDOW")
    base = {(d.location_id, d.day): d for d in baseline if d.product_id == product_id}
    first = s.first_planning_date
    if s.mode == "PANTRY":
        incoming = defaultdict(int)
        for p in packed:
            incoming[p.transfer.to_location_id] += p.transfer.quantity
        for loc, units in incoming.items():
            need = sum(
                base[loc, first + timedelta(days=i)].unmet
                for i in range(window)
                if (loc, first + timedelta(days=i)) in base
            )
            if units > need:
                violations.append("BASELINE_NEED_OVERDELIVERY")
    senders = {p.transfer.from_location_id for p in packed}
    if replay is not None:
        senders &= replay
    floors = {r.location_id: r.floor for r in sub.reserves}
    for d in project_v3(sub, packed, include_inbound_transfers=False, locations=senders).days:
        if d.location_id in senders and (d.unmet or d.on_hand < floors.get(d.location_id, 0)):
            violations.append("DONOR_PROTECTION")
    h = product.handling_units_per_unit
    routes = {(r.from_location_id, r.to_location_id): r for r in s.routes}
    dispatch, receiving = defaultdict(int), defaultdict(int)
    total, cost = 0, Fraction(0)
    for p in packed:
        t = p.transfer
        load = t.quantity * h
        share = shares.route.get((t.from_location_id, t.to_location_id))
        if share is not None and load > share:
            violations.append("ROUTE_CAPACITY")
        dispatch[t.from_location_id] += load
        receiving[t.to_location_id, t.arrival_date] += load
        total += load
        cost += cost_minor(routes[t.from_location_id, t.to_location_id], t.quantity, h)

    def over(loads, limits):
        return any(limits.get(k) is not None and load > limits[k] for k, load in loads.items())

    if over(dispatch, shares.dispatch):
        violations.append("DISPATCH_CAPACITY")
    if over(receiving, shares.receiving):
        violations.append("RECEIVING_CAPACITY")
    if shares.global_handling is not None and total > shares.global_handling:
        violations.append("GLOBAL_HANDLING_CAPACITY")
    if shares.cost_minor is not None and cost > shares.cost_minor:
        violations.append("TRANSPORT_COST_BUDGET")
    for d in plan.days:
        room = shares.storage_room.get((d.location_id, d.day))
        start = base[d.location_id, d.day].on_hand if (d.location_id, d.day) in base else 0
        if room is not None and h * d.on_hand > h * start + room:
            violations.append("STORAGE_CAPACITY")
    return tuple(dict.fromkeys(violations))
