"""Single physical feasible region. Neither method contributes any constraint here."""

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from ortools.sat.python import cp_model

from app.services.optimization.scenario import usable


@dataclass
class PhysicalModel:
    problem: object
    model: cp_model.CpModel
    y: dict = field(default_factory=dict)
    x: dict = field(default_factory=dict)
    served: dict = field(default_factory=dict)
    ends: dict = field(default_factory=dict)
    expired: dict = field(default_factory=dict)
    goals: dict = field(default_factory=dict)
    cost: object = None
    q_cost: object = None
    q_waste: dict = field(default_factory=dict)
    fingerprint: str = ""


def floor_variable(model, numerator, denominator, upper, name):
    if denominator <= 0:
        raise ValueError("Positive floor denominator required")
    q = model.new_int_var(0, upper, name)
    model.add(denominator * q <= numerator)
    model.add(numerator <= denominator * q + denominator - 1)
    return q


def build_physical_model(problem) -> PhysicalModel:
    # OR-DEC-019 [PROVISIONAL]: local pre-solver gate evidence is in RESEARCH-MAPPING.md.
    s = problem.scenario
    package = s.package
    m = cp_model.CpModel()
    physical = PhysicalModel(problem, m)
    products = {p.id: p for p in package.products}
    lots = {lot.id: lot for lot in package.inventory}
    dates = tuple(p.day for p in s.demand[0].days)
    residuals = {lot.id: lot.free_units for lot in package.inventory if usable(lot)}
    received = defaultdict(list)
    candidate_by_key = {(c.route_id, c.product_id): c for c in problem.candidates}
    # OR-DEC-004 [PROVISIONAL]: route order is frozen and restricts packing schedules.
    for key in s.loading_order:
        candidate = candidate_by_key[key.route_id, key.product_id]
        y = m.new_int_var(0, candidate.upper, f"y:{key.route_id}:{key.product_id}")
        physical.y[key.route_id, key.product_id] = y
        if candidate.upper == 0:
            # A fixed-zero route cannot debit a lot or create an inbound sublot.
            # Keep extraction identities without emitting zero-balance trajectories.
            for lot_id in candidate.lot_ids:
                physical.x[lot_id, key.route_id] = 0
            continue
        request = y
        for lot_id in candidate.lot_ids:
            lot = lots[lot_id]
            bound = min(lot.free_units, candidate.upper)
            x = m.new_int_var(0, bound, f"x:{lot_id}:{key.route_id}")
            m.add_min_equality(x, [residuals[lot_id], request])
            left = m.new_int_var(0, lot.free_units, f"left:{lot_id}:{key.route_id}")
            m.add(left == residuals[lot_id] - x)
            residuals[lot_id] = left
            next_request = m.new_int_var(0, candidate.upper, f"request:{lot_id}:{key.route_id}")
            m.add(next_request == request - x)
            request = next_request
            physical.x[lot_id, key.route_id] = x
            received[candidate.destination_id, candidate.product_id].append(
                (
                    f"{lot_id}:{key.route_id}",
                    x,
                    bound,
                    dates[0] + timedelta(days=candidate.eta_days),
                    lot.expires_on,
                    True,
                )
            )
        m.add(request == 0)

    # OR-DEC-001/005 [PROVISIONAL]: arrivals, expiry, day-one dispatch, dated FEFO service.
    def project(series, inbound, prefix):
        resources = []
        for lot in package.inventory:
            if (lot.site_id, lot.product_id) == (series.site_id, series.product_id) and usable(lot):
                resources.append(
                    (
                        str(lot.id),
                        residuals[lot.id],
                        lot.free_units,
                        lot.available_on,
                        lot.expires_on,
                        False,
                    )
                )
        for lot in package.confirmed_arrivals:
            if (lot.site_id, lot.product_id) == (series.site_id, series.product_id) and usable(lot):
                resources.append(
                    (str(lot.id), lot.units, lot.units, lot.available_on, lot.expires_on, False)
                )
        resources.extend(inbound)
        resources.sort(key=lambda r: (r[4], r[3], r[0]))
        balances = {r[0]: r[1] for r in resources}
        consumption = defaultdict(list)
        day_served, day_ends, day_waste = [], [], []
        for index, point in enumerate(series.days):
            request = point.units
            wastes = []
            for identity, _, bound, arrival, expiry, proposed in resources:
                if arrival > point.day:
                    continue
                if proposed and index >= s.planning_days:
                    # Every proposed sublot must be consumed by H (enforced below).
                    balances[identity] = 0
                    continue
                balance = balances[identity]
                if expiry <= point.day:
                    wastes.append(balance)
                    balances[identity] = 0
                    continue
                if point.units == 0 or (isinstance(balance, int) and balance == 0):
                    continue
                consumed = m.new_int_var(
                    0, min(bound, point.units), f"consume:{prefix}:{identity}:{index}"
                )
                m.add_min_equality(consumed, [balance, request])
                left = m.new_int_var(0, bound, f"stock:{prefix}:{identity}:{index}")
                m.add(left == balance - consumed)
                balances[identity] = left
                remaining = m.new_int_var(0, point.units, f"unmet:{prefix}:{identity}:{index}")
                m.add(remaining == request - consumed)
                request = remaining
                if index < s.planning_days:
                    consumption[identity].append(consumed)
            served = m.new_int_var(0, point.units, f"served:{prefix}:{index}")
            m.add(served == point.units - request)
            day_served.append(served)
            day_ends.append(sum(balances[r[0]] for r in resources if r[3] <= point.day))
            day_waste.append(sum(wastes))
        for identity, quantity, _, _, _, proposed in resources:
            if proposed:
                m.add(sum(consumption[identity]) == quantity)
        return day_served, day_ends, day_waste

    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for c in problem.candidates:
        y = physical.y[c.route_id, c.product_id]
        outgoing[c.source_id, c.product_id].append(y)
        incoming[c.destination_id, c.product_id].append(y)
    reserves = {(r.site_id, r.product_id): r.floors for r in package.reserves}
    for series in s.demand:
        key = series.site_id, series.product_id
        prefix = f"{series.site_id}:{series.product_id}"
        served, ends, waste = project(series, received[key], prefix)
        physical.served[key], physical.ends[key], physical.expired[key] = served, ends, waste
        if incoming[key]:
            need = sum(
                d.unmet
                for d in problem.baseline.days
                if (d.site_id, d.product_id) == key and d.day in dates[: s.planning_days]
            )
            m.add(sum(incoming[key]) <= need)
        # OR-DEC-003 [PROVISIONAL]: sending safety cannot depend on proposed inbound.
        if outgoing[key]:
            sending = m.new_bool_var(f"sending:{prefix}")
            m.add(sum(outgoing[key]) >= 1).only_enforce_if(sending)
            m.add(sum(outgoing[key]) == 0).only_enforce_if(~sending)
            if received[key]:
                protected_service, protected_ends, _ = project(series, [], f"protected:{prefix}")
            else:
                protected_service, protected_ends = served, ends
            for i, point in enumerate(series.days):
                m.add(protected_service[i] == point.units).only_enforce_if(sending)
                m.add(protected_ends[i] >= reserves[key][i]).only_enforce_if(sending)
        if next(site.role for site in package.sites if site.id == series.site_id) == "BENEFICIARY":
            target = sum(p.units for p in series.days[: s.planning_days])
            fulfilled = m.new_int_var(0, target, f"fulfilled:{prefix}")
            m.add(fulfilled == sum(served[: s.planning_days]))
            physical.goals[key] = target, fulfilled

    # OR-DEC-017 [PROVISIONAL]: shared product handling, residual capacities and budget.
    handling = {key: products[key[1]].handling_coefficient * y for key, y in physical.y.items()}
    routes = {r.id: r for r in package.routes}
    for rid, route in routes.items():
        m.add(sum(v for (r, _), v in handling.items() if r == rid) <= route.capacity.residual)
    for capacity in package.capacities.sites:
        m.add(
            sum(
                handling[c.route_id, c.product_id]
                for c in problem.candidates
                if c.source_id == capacity.site_id
            )
            <= capacity.source.residual
        )
        for i, _day in enumerate(dates):
            m.add(
                sum(
                    handling[c.route_id, c.product_id]
                    for c in problem.candidates
                    if c.destination_id == capacity.site_id and c.eta_days == i
                )
                <= capacity.receiving[i].residual
            )
            m.add(
                sum(
                    products[pid].handling_coefficient * ends[i]
                    for (sid, pid), ends in physical.ends.items()
                    if sid == capacity.site_id
                )
                <= capacity.storage[i].residual
            )
    m.add(sum(handling.values()) <= package.capacities.global_handling.residual)
    cost = m.new_int_var(0, s.cost_reference, "cost")
    m.add(
        cost == sum(c.cost_minor * physical.y[c.route_id, c.product_id] for c in problem.candidates)
    )
    if package.capacities.cost_budget_minor is not None:
        m.add(cost <= package.capacities.cost_budget_minor)
    physical.cost = cost
    physical.q_cost = (
        floor_variable(m, 10000 * cost, s.cost_reference, 10000, "q_cost")
        if s.cost_reference
        else m.new_constant(0)
    )
    for ref in s.waste_references:
        waste = sum(
            day
            for (sid, pid), days in physical.expired.items()
            if pid == ref.product_id
            for day in days
        )
        total = m.new_int_var(0, ref.units, f"waste:{ref.product_id}")
        m.add(total == waste)
        physical.q_waste[ref.product_id] = (
            floor_variable(m, 10000 * total, ref.units, 10000, f"q_waste:{ref.product_id}")
            if ref.units
            else m.new_constant(0)
        )
    physical.fingerprint = hashlib.sha256(str(m.proto).encode()).hexdigest()
    return physical
