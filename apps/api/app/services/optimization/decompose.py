"""Per-product decomposition (decisions/W0-optimizer-decomposition.md, W1-S05).

At-risk screen on the frozen no-transfer projection, and the advance split of every shared limit:
share_p = floor(cap × weight_p / Σ weight over the products that can use that limit), where
weight = need × handling_units_per_unit, times unit_value_usd in Retail USD mode
(CR-w1-solver-2). Products whose share can't move one unit are reported, never optimized. The
union of the per-product plans is re-checked by verify.verify_plan against the raw scenario.
"""

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from math import floor

from app.services.optimization.product_model import Shares
from app.services.optimization.v3 import Candidate, dates, window_days


def floor_shares(cap: int, weights) -> dict:
    """share_p = floor(cap × weight_p / Σ weight); never sums above cap (0 when Σ weight = 0)."""
    total = sum(weights.values())
    return {p: (floor(cap * w / total) if total else 0) for p, w in weights.items()}


def need(s, baseline) -> dict[str, int]:
    """Retail: lost sales + expired units over 7 days. Pantry: unmet inside the window."""
    window = set(dates(s)[: window_days(s)])
    out = defaultdict(int)
    for d in baseline:
        out[d.product_id] += (
            d.unmet + d.expired if s.mode == "RETAIL" else (d.unmet if d.day in window else 0)
        )
    return dict(out)


def at_risk(s, baseline) -> set[str]:
    return {p for p, units in need(s, baseline).items() if units > 0}


def protected_senders(s, baseline, product_id) -> set[str]:
    """Locations that serve their whole seven-day forecast and keep their reserve with no plan."""
    floors = {r.location_id: r.floor for r in s.reserves if r.product_id == product_id}
    ok = defaultdict(lambda: True)
    for d in baseline:
        if d.product_id == product_id:
            ok[d.location_id] &= not d.unmet and d.on_hand >= floors.get(d.location_id, 0)
    return {loc for loc, good in ok.items() if good}


@dataclass(frozen=True)
class Split:
    shares: dict[str, Shares]
    starved: frozenset[str]


def split(s, baseline, products, measure, cands: dict[str, tuple[Candidate, ...]]) -> Split:
    info = {p.id: p for p in s.products}
    needs = need(s, baseline)
    weight = {}
    for p in products:
        w = Fraction(needs.get(p, 0) * info[p].handling_units_per_unit)
        weight[p] = w * Fraction(info[p].unit_value_usd) if measure == "USD" else w
    users = defaultdict(set)  # limit key -> products that can use it
    for p in products:
        for c in cands[p]:
            frm, to = c.route.from_location_id, c.route.to_location_id
            users["route", frm, to].add(p)
            users["dispatch", frm].add(p)
            users["receiving", to, c.arrival].add(p)
            for day in dates(s):
                users["storage", to, day].add(p)

    def share(cap, p, key=None):
        if cap is None:
            return None
        group = users[key] if key else products
        return floor_shares(cap, {q: weight[q] for q in group})[p]

    caps = {c.location_id: c for c in s.capacities}
    routes = {(r.from_location_id, r.to_location_id): r for r in s.routes}
    handling = defaultdict(int)  # baseline stock in handling units, every product
    for d in baseline:
        handling[d.location_id, d.day] += d.on_hand * info[d.product_id].handling_units_per_unit
    shares, starved = {}, set()
    for p in sorted(products):
        h = info[p].handling_units_per_unit
        route, dispatch, receiving, storage = {}, {}, {}, {}
        for c in cands[p]:
            frm, to = c.route.from_location_id, c.route.to_location_id
            route[frm, to] = share(routes[frm, to].capacity_per_batch, p, ("route", frm, to))
            limit = caps[frm].dispatch if frm in caps else None
            dispatch[frm] = share(limit, p, ("dispatch", frm))
            limit = caps[to].receiving if to in caps else None
            receiving[to, c.arrival] = share(limit, p, ("receiving", to, c.arrival))
            for day in dates(s):
                limit = caps[to].storage if to in caps else None
                room = None if limit is None else max(0, limit - handling[to, day])
                storage[to, day] = share(room, p, ("storage", to, day))
        budget = share(s.cost_budget_minor, p)
        shares[p] = Shares(
            route,
            dispatch,
            receiving,
            storage,
            share(s.global_handling, p),
            None if budget is None else Fraction(budget),
        )
        senders = protected_senders(s, baseline, p)
        usable = [c for c in cands[p] if c.route.from_location_id in senders]

        def fits(c, sh=shares[p], h=h):
            frm, to = c.route.from_location_id, c.route.to_location_id
            cost = c.route.cost_per_handling_unit_usd
            unit_cost = Fraction(cost) * 100 * h if cost else Fraction(0)
            return all(
                v is None or v >= h
                for v in (
                    sh.route[frm, to],
                    sh.dispatch[frm],
                    sh.receiving[to, c.arrival],
                    sh.global_handling,
                )
            ) and (sh.cost_minor is None or sh.cost_minor >= unit_cost)

        if usable and not any(fits(c) for c in usable):
            starved.add(p)
    return Split(shares, frozenset(starved))
