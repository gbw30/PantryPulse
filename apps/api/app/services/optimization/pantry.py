"""CLASSICAL_GP and EGP_PI_INSPIRED for one product on or-input-v3 (W1-S03, Pantry).

A port of the v2 objective (objective.attach, metrics.evaluate) to the v1 per-product solve:
- goals: each pantry with a positive target inside the BD-50 window (target = window demand,
  fulfilled = units served inside the window); hubs are never goals;
- weight v = 1 + λ × Σ coefficient × rate (VulnerabilityV3 rates, exact rationals; EGP only);
- q = floor(S × v × unmet / target), S = 10 000; Z = max q; blend β × Σq + (1 − β) × Z, all / S;
- EGP adds the AP/RP flags (reified both ways, equality unflagged) and the per-product excess
  max(0, S × Σflags − cap × n), weighted γ / (100 × S × n); RP needs a group of at least two
  pantries (SPEC-V5 §11: reject singleton groups), otherwise EGP does not optimize the product;
- both add ε_cost × floor(S × cost / cost reference) and ε_waste × floor(S × expired / stock).
Per product there is one RP group, so v2's 1 / (number of product groups) factor is 1.
The rational coefficients compile exactly to integers (LCM, then GCD), and pantry_objectives
replays the same integer from the verifier's projection.
"""

from collections import defaultdict
from decimal import Decimal
from fractions import Fraction
from functools import reduce
from math import floor, gcd, lcm

from app.services.optimization.constraints import floor_variable
from app.services.optimization.product_model import _unit_cost, build_product_model
from app.services.optimization.retail import solve
from app.services.optimization.v3 import dates, route_allowed, window_days
from app.services.optimization.verify import cost_minor

S = 10_000
SINGLETON_LABEL = "relative-priority group has fewer than two pantries; EGP-PI not defined"


def research(method: str) -> bool:
    return method == "EGP_PI_INSPIRED"


def goals(s, product_id) -> list[tuple[str, int]]:
    """(pantry, window target) for every pantry with a positive target, in location order."""
    roles = {loc.id: loc.role for loc in s.locations}
    window = window_days(s)
    out = [
        (d.location_id, sum(d.targets[:window]))
        for d in s.demand
        if d.product_id == product_id and roles[d.location_id] == "pantry"
    ]
    return sorted((loc, t) for loc, t in out if t > 0)


def coverage_gap(s) -> list[str]:
    """Pantries with demand but no vulnerability row (EGP can't weight them)."""
    covered = {v.location_id for v in s.vulnerability}
    return sorted({loc for p in s.products for loc, _ in goals(s, p.id)} - covered)


def weights(s, method) -> dict[str, Fraction]:
    if not research(method):
        return defaultdict(lambda: Fraction(1))
    policy = s.policy
    lam = Fraction(policy.lambda_percent, 100)
    return {
        v.location_id: 1
        + lam
        * sum(
            Fraction(c.percent, 100) * Fraction(Decimal(getattr(v, c.attribute_id)))
            for c in policy.coefficients
        )
        for v in s.vulnerability
    }


def references(s, product_id) -> tuple[Fraction, int]:
    """(cost reference in cents, stock reference in units) for the normalized ε terms."""
    product = next(p for p in s.products if p.id == product_id)
    first, last = s.first_planning_date, dates(s)[-1]
    unit_costs = defaultdict(list)
    for r in s.routes:
        if route_allowed(s, r):
            unit_costs[r.from_location_id].append(_unit_cost(r, product.handling_units_per_unit))
    cost = sum(
        (
            b.quantity * max(unit_costs[b.location_id], default=Fraction(0))
            for b in s.batches
            if b.product_id == product_id and (b.expiry_date is None or b.expiry_date >= first)
        ),
        Fraction(0),
    )
    stock = sum(b.quantity for b in s.batches if b.product_id == product_id) + sum(
        i.quantity for i in s.inbound if i.product_id == product_id and i.arrival_date <= last
    )
    return cost, stock


def coefficients(policy, method, n, has_cost, has_waste) -> tuple[int, ...]:
    """Integer coefficients, in term order: q_1..q_n, Z, [AP, RP excess], [cost], [waste]."""
    beta = Fraction(policy.beta_percent, 100)
    terms = [beta / S] * n + [(1 - beta) / S]
    if research(method):
        terms += [
            Fraction(g, 100 * S * n) for g in (policy.gamma_ap_percent, policy.gamma_rp_percent)
        ]
    if has_cost:
        terms.append(Fraction(policy.epsilon_cost_bp, S * S))
    if has_waste:
        terms.append(Fraction(policy.epsilon_waste_bp, S * S))
    denominator = lcm(*(t.denominator for t in terms))
    integers = [int(t * denominator) for t in terms]
    common = reduce(gcd, integers, 0) or 1
    return tuple(i // common for i in integers)


def solve_pantry_product(
    s, product_id, cands, shares, baseline, protected, search_seconds, *, method
):
    pm = build_product_model(s, product_id, cands, shares, baseline, protected)
    m, policy, window = pm.model, s.policy, window_days(s)
    v = weights(s, method)
    product_goals = goals(s, product_id)
    n = len(product_goals)
    values = []
    for loc, target in product_goals:
        w = v[loc]
        fulfilled = sum(pm.served[loc][:window])
        values.append(
            floor_variable(
                m,
                S * w.numerator * (target - fulfilled),
                w.denominator * target,
                floor(S * w),
                f"q:{loc}",
            )
        )
    qs = list(values)
    z = m.new_int_var(0, max((floor(S * v[loc]) for loc, _ in product_goals), default=0), "Z")
    m.add_max_equality(z, qs or [0])
    values.append(z)
    if research(method):
        for kind, threshold_flag, cap in (
            ("ap", lambda q: (q, policy.ap_threshold), policy.ap_cap_bp),
            ("rp", lambda q: (n * q - sum(qs), n * policy.rp_threshold), policy.rp_cap_bp),
        ):
            flags = []
            for i, q in enumerate(qs):
                expr, threshold = threshold_flag(q)
                b = m.new_bool_var(f"{kind}:{i}")
                m.add(expr >= threshold + 1).only_enforce_if(b)
                m.add(expr <= threshold).only_enforce_if(~b)
                flags.append(b)
            excess = m.new_int_var(0, S * n, f"excess:{kind}")
            m.add_max_equality(excess, [0, S * sum(flags) - cap * n])
            values.append(excess)
    cost_ref, stock_ref = references(s, product_id)
    if cost_ref:
        routes = {(r.from_location_id, r.to_location_id): r for r in s.routes}
        h = next(p.handling_units_per_unit for p in s.products if p.id == product_id)
        unit = {
            c.key: _unit_cost(routes[c.route.from_location_id, c.route.to_location_id], h)
            for c in cands
        }
        scale = lcm(cost_ref.denominator, *(u.denominator for u in unit.values()))
        cost = sum(int(unit[k] * scale) * y for k, y in pm.y.items() if not isinstance(y, int))
        values.append(floor_variable(m, S * cost, int(cost_ref * scale), S, "q_cost"))
    if stock_ref:
        expired = sum(sum(points) for points in pm.expired.values())
        values.append(floor_variable(m, S * expired, stock_ref, S, "q_waste"))
    weights_ = coefficients(policy, method, n, bool(cost_ref), bool(stock_ref))
    primary = sum(c * x for c, x in zip(weights_, values, strict=True))
    # no fewer-units tie-break: K × these coefficients could pass the 2**60 audit at 100×500
    return solve(pm, primary, search_seconds, product_id, tie_break=False)


def pantry_objectives(s, report, method) -> dict[str, int]:
    """Each product's compiled objective, replayed from the verifier's projection and plan."""
    policy, window = s.policy, window_days(s)
    v = weights(s, method)
    in_window = set(dates(s)[:window])
    served, expired = defaultdict(int), defaultdict(int)
    for d in report.days:
        expired[d.product_id] += d.expired
        if d.day in in_window:
            served[d.location_id, d.product_id] += d.served
    routes = {(r.from_location_id, r.to_location_id): r for r in s.routes}
    handling = {p.id: p.handling_units_per_unit for p in s.products}
    cost = defaultdict(Fraction)
    for p in report.packed:
        t = p.transfer
        cost[t.product_id] += cost_minor(
            routes[t.from_location_id, t.to_location_id], t.quantity, handling[t.product_id]
        )
    out = {}
    for product in s.products:
        pid = product.id
        product_goals = goals(s, pid)
        n = len(product_goals)
        qs = [
            (S * v[loc].numerator * (target - served[loc, pid])) // (v[loc].denominator * target)
            for loc, target in product_goals
        ]
        values = [*qs, max(qs, default=0)]
        if research(method):
            for flags, cap in (
                ([q > policy.ap_threshold for q in qs], policy.ap_cap_bp),
                ([n * q - sum(qs) > n * policy.rp_threshold for q in qs], policy.rp_cap_bp),
            ):
                values.append(max(0, S * sum(flags) - cap * n))
        cost_ref, stock_ref = references(s, pid)
        if cost_ref:
            values.append(floor(S * cost[pid] / cost_ref))
        if stock_ref:
            values.append(S * expired[pid] // stock_ref)
        c = coefficients(policy, method, n, bool(cost_ref), bool(stock_ref))
        out[pid] = sum(a * b for a, b in zip(c, values, strict=True))
    return out
