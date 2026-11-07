"""One product's CP-SAT physical model on an or-input-v3 scenario (v1 solves per product).

The model encodes the same dated FEFO recurrence as projection.project_v3 (same lot identities,
FEFO order and sentinel day), the frozen FEFO packing chain of v3.pack, BD-49 sender protection,
BD-51 (relaxed in Retail) and this product's pre-split share of every shared limit. It never
decides anything the independent verifier (verify.verify_plan) does not re-check.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from fractions import Fraction
from math import floor, lcm

from ortools.sat.python import cp_model

from app.services.optimization.projection import lot_ids_v3
from app.services.optimization.v3 import Candidate, RouteKey, dates, fefo_key, window_days


@dataclass
class ProductModel:
    model: cp_model.CpModel
    y: dict[RouteKey, cp_model.IntVar | int] = field(default_factory=dict)
    upper: dict[RouteKey, int] = field(default_factory=dict)
    unmet: dict[str, list] = field(default_factory=dict)  # per location, 7 planning days
    served: dict[str, list] = field(default_factory=dict)
    expired: dict[str, list] = field(default_factory=dict)  # per location, 8 points
    ends: dict[str, list] = field(default_factory=dict)


def _min(m, a, b, upper, name):
    if isinstance(a, int) and isinstance(b, int):
        return min(a, b)
    v = m.new_int_var(0, upper, name)
    m.add_min_equality(v, [a, b])
    return v


def _project(m, points, demand, lots, prefix):
    """FEFO kernel over (point, demand) with lots (ident, balance, bound, available, expiry).

    Returns served, unmet, expired-per-point, end-of-day stock and per-lot consumption, exactly as
    kernel.project_kernel computes them for the same inputs.
    """
    lots = sorted(lots, key=lambda r: fefo_key(r[4], r[3], r[0]))
    balance = {r[0]: r[1] for r in lots}
    consumed = defaultdict(list)
    served, unmet, expired, ends = [], [], [], []
    for i, (day, units) in enumerate(zip(points, demand, strict=True)):
        remaining, waste = units, []
        for ident, _, bound, available, expiry in lots:
            used = 0
            if available <= day:
                if expiry is not None and expiry < day:
                    waste.append(balance[ident])
                    balance[ident] = 0
                elif units:
                    used = _min(
                        m, balance[ident], remaining, min(bound, units), f"{prefix}u{i}{ident}"
                    )
                    balance[ident] = balance[ident] - used
                    remaining = remaining - used
            consumed[ident].append(used)
        served.append(units - remaining)
        unmet.append(remaining)
        expired.append(sum(waste))
        ends.append(sum(balance[r[0]] for r in lots if r[3] <= day))
    return served, unmet, expired, ends, consumed


def build_product_model(s, product_id, cands: tuple[Candidate, ...], shares, baseline, protected):
    """baseline: no-transfer projection rows of this product; protected: senders allowed to send."""
    bid, iid, sid = lot_ids_v3()
    m = cp_model.CpModel()
    pm = ProductModel(m)
    product = next(p for p in s.products if p.id == product_id)
    h = product.handling_units_per_unit
    days = dates(s)
    points = (*days, days[-1] + timedelta(days=1))
    window = window_days(s)
    first = s.first_planning_date
    demand = {d.location_id: d.targets for d in s.demand if d.product_id == product_id}
    base = defaultdict(dict)
    for d in baseline:
        base[d.location_id][d.day] = d
    need = {
        loc: sum(base[loc][day].unmet for day in days[:window] if day in base[loc]) for loc in base
    }
    routes = {(r.from_location_id, r.to_location_id): r for r in s.routes}

    def cap(limit, unit):
        return None if limit is None else (limit // unit if unit else None)

    for c in cands:
        frm, to = c.route.from_location_id, c.route.to_location_id
        cost = _unit_cost(routes[frm, to], h)
        bounds = [
            sum(b.quantity for b in c.batches),
            cap(shares.route.get((frm, to)), h),
            cap(shares.dispatch.get(frm), h),
            cap(shares.receiving.get((to, c.arrival)), h),
            cap(shares.global_handling, h),
            None if shares.cost_minor is None or not cost else floor(shares.cost_minor / cost),
            # a receiver can't consume more than its demand from arrival through the window
            sum(demand.get(to, (0,) * 7)[(c.arrival - first).days : window]),
            need.get(to, 0) if s.mode == "PANTRY" else None,
            None if frm in protected else 0,
        ]
        upper = min(b for b in bounds if b is not None)
        pm.upper[c.key] = upper
        pm.y[c.key] = m.new_int_var(0, upper, f"y:{frm}>{to}") if upper else 0

    # Frozen FEFO packing chain per sender (v3.pack): candidates are already in loading order.
    residual = {b.id: b.quantity for b in s.batches if b.product_id == product_id}
    sublots = defaultdict(list)
    for c in cands:
        request = pm.y[c.key]
        if isinstance(request, int):
            continue
        for b in c.batches:
            x = _min(
                m, residual[b.id], request, min(b.quantity, pm.upper[c.key]), f"x:{c.id}:{b.id}"
            )
            residual[b.id] = residual[b.id] - x
            request = request - x
            sublots[c.route.to_location_id].append(
                (sid(c.id, b.id), x, min(b.quantity, pm.upper[c.key]), c.arrival, b.expiry_date)
            )
        m.add(request == 0)

    own = defaultdict(list)
    for b in s.batches:
        if b.product_id == product_id:
            own[b.location_id].append((bid(b.id), residual[b.id], b.quantity, first, b.expiry_date))
    for i in s.inbound:
        if i.product_id == product_id:
            own[i.location_id].append(
                (iid(i.id), i.quantity, i.quantity, i.arrival_date, i.expiry_date)
            )

    outgoing, incoming = defaultdict(list), defaultdict(list)
    for c in cands:
        if not isinstance(pm.y[c.key], int):
            outgoing[c.route.from_location_id].append(pm.y[c.key])
            incoming[c.route.to_location_id].append(pm.y[c.key])
    floors = {r.location_id: r.floor for r in s.reserves if r.product_id == product_id}
    for loc in sorted(set(demand) | set(own) | set(sublots)):
        targets = (*demand.get(loc, (0,) * 7), 0)
        served, unmet, expired, ends, consumed = _project(
            m, points, targets, own[loc] + sublots[loc], f"{loc}:"
        )
        pm.served[loc], pm.unmet[loc], pm.expired[loc], pm.ends[loc] = (
            served[:7],
            unmet[:7],
            expired,
            ends[:7],
        )
        for ident, x, *_ in sublots[loc]:
            m.add(sum(consumed[ident][:window]) == x)  # BD-51 (relaxed in Retail)
        if s.mode == "PANTRY" and incoming[loc]:
            m.add(sum(incoming[loc]) <= need.get(loc, 0))
        if outgoing[loc]:  # BD-49: protection never counts proposed inbound
            if sublots[loc]:
                _, unmet_p, _, ends_p, _ = _project(m, points, targets, own[loc], f"{loc}:p:")
            else:
                unmet_p, ends_p = unmet, ends
            sending = m.new_bool_var(f"sending:{loc}")
            m.add(sum(outgoing[loc]) >= 1).only_enforce_if(sending)
            m.add(sum(outgoing[loc]) == 0).only_enforce_if(~sending)
            for k in range(7):
                _enforce(m, unmet_p[k], 0, 0, sending)
                _enforce(m, ends_p[k], floors.get(loc, 0), None, sending)
        for k, day in enumerate(days):
            room = shares.storage_room.get((loc, day))
            if room is not None and loc in sublots:
                start = base[loc][day].on_hand if day in base[loc] else 0
                m.add(h * pm.ends[loc][k] <= h * start + room)

    def limit(groups, shares_of):
        for key, ys in groups.items():
            share = shares_of(key)
            if share is not None and ys:
                m.add(h * sum(ys) <= share)

    by_route, by_receiver = defaultdict(list), defaultdict(list)
    for c in cands:
        if not isinstance(pm.y[c.key], int):
            by_route[c.route.from_location_id, c.route.to_location_id].append(pm.y[c.key])
            by_receiver[c.route.to_location_id, c.arrival].append(pm.y[c.key])
    limit(by_route, shares.route.get)
    limit(outgoing, shares.dispatch.get)
    limit(by_receiver, shares.receiving.get)
    every = [v for v in pm.y.values() if not isinstance(v, int)]
    if every:
        limit({"global": every}, lambda _: shares.global_handling)
    if shares.cost_minor is not None and every:
        costs = {
            c.key: _unit_cost(routes[c.route.from_location_id, c.route.to_location_id], h)
            for c in cands
        }
        scale = lcm(*(cost.denominator for cost in costs.values()), shares.cost_minor.denominator)
        m.add(
            sum(int(costs[k] * scale) * v for k, v in pm.y.items() if not isinstance(v, int))
            <= floor(shares.cost_minor * scale)
        )
    for v in every:
        m.add_hint(v, 0)  # the no-transfer plan is always feasible
    return pm


def _enforce(m, expr, low, high, literal):
    """low <= expr <= high when literal holds; a constant that fails forbids the literal."""
    if isinstance(expr, int):
        if expr < low or (high is not None and expr > high):
            m.add(literal == 0)
        return
    m.add(expr >= low).only_enforce_if(literal)
    if high is not None:
        m.add(expr <= high).only_enforce_if(literal)


def _unit_cost(route, handling) -> Fraction:
    """Cents to move one unit on this route."""
    if route.cost_per_handling_unit_usd is None:
        return Fraction(0)
    return Fraction(route.cost_per_handling_unit_usd) * 100 * handling
