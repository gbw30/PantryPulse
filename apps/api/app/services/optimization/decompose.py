"""Per-product decomposition (decisions/W0-optimizer-decomposition.md, W1-S05).

At-risk screen on the frozen no-transfer projection, and the advance split of every shared limit,
weight = need × handling_units_per_unit, times unit_value_usd in Retail USD mode (CR-w1-solver-2):
- a receiver's limits (route into it, receiving, storage) go only to the products with positive
  need at that receiver, by allot (localized split, Gabriel 2026-11-07);
- sender dispatch, global handling and the cost budget: share_p = floor(cap × weight_p / Σ weight)
  over the products that can use them.
Products whose share still can't move one unit (including storage on the days the unit waits
at the receiver for its first short day) are reported, never optimized. The union of the
per-product plans is re-checked by verify.verify_plan against the raw scenario.
"""

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from math import floor, lcm

from app.services.optimization.product_model import Shares
from app.services.optimization.v3 import Candidate, dates, window_days


def floor_shares(cap: int, weights) -> dict:
    """share_p = floor(cap × weight_p / Σ weight); never sums above cap (0 when Σ weight = 0)."""
    total = sum(weights.values())
    return {p: (floor(cap * w / total) if total else 0) for p, w in weights.items()}


def allot(cap: int, weights: dict, handling: dict) -> dict:
    """Localized split of one limit (Gabriel, 2026-11-07), shares in handling units.

    Proportional floor shares, rounded down to whole units. A product whose share can't fit one
    unit gets exactly one unit's handling, largest weight then product id first, while capacity
    lasts (else 0: starved); the rest is split proportionally among the others. Never sums above
    cap; zero weight gets 0.
    """

    def proportional(room, products):
        total = sum(weights[p] for p in products)
        return {
            p: (room * weights[p] // total // handling[p] * handling[p] if total else 0)
            for p in products
        }

    positive = {p for p, w in weights.items() if w > 0}
    small: set = set()  # products held to one unit; grows until the others all fit
    while True:
        others = positive - small
        room = max(0, cap - sum(handling[p] for p in small))
        grown = {p for p, v in proportional(room, others).items() if v < handling[p]}
        if not grown:
            break
        small |= grown
    out = dict.fromkeys(weights, 0)
    left = cap
    for p in sorted(small, key=lambda p: (-weights[p], p)):
        if left >= handling[p]:
            out[p], left = handling[p], left - handling[p]
    out |= proportional(left, positive - small)
    return out


def need(s, baseline, *, by_location=False) -> dict:
    """Retail: lost sales + expired units over 7 days. Pantry: unmet inside the window.
    Keyed by product, or by (product, location)."""
    window = set(dates(s)[: window_days(s)])
    out = defaultdict(int)
    for d in baseline:
        key = (d.product_id, d.location_id) if by_location else d.product_id
        out[key] += (
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
    exact = {}
    for p in products:
        w = Fraction(needs.get(p, 0) * info[p].handling_units_per_unit)
        exact[p] = w * Fraction(info[p].unit_value_usd) if measure == "USD" else w
    # One common positive scale turns the rational weights into integers; floors are unchanged.
    scale = lcm(*(w.denominator for w in exact.values())) if exact else 1
    weight = {p: int(w * scale) for p, w in exact.items()}
    days = dates(s)
    local = need(s, baseline, by_location=True)
    users = defaultdict(set)  # limit key -> products that can use it
    for p in products:
        for c in cands[p]:
            frm, to = c.route.from_location_id, c.route.to_location_id
            users["dispatch", frm].add(p)
            if local.get((p, to), 0) > 0:  # a receiver's limits: products with need there
                users["route", frm, to].add(p)
                users["receiving", to, c.arrival].add(p)
                users["storage", to].add(p)

    totals: dict = {}
    allotted: dict = {}
    handling_of = {p: info[p].handling_units_per_unit for p in products}

    def share(cap, p, key=None):
        """This product's share of one limit (allot for a receiver's limits, else floor)."""
        if cap is None:
            return None
        if key and key[0] in ("route", "receiving", "storage"):
            if (key, cap) not in allotted:
                mine = users[key]
                allotted[key, cap] = allot(cap, {q: weight[q] for q in mine}, handling_of)
            return allotted[key, cap].get(p, 0)
        if key not in totals:
            totals[key] = sum(weight[q] for q in (users[key] if key else products))
        total = totals[key]
        return cap * weight[p] // total if total else 0

    caps = {c.location_id: c for c in s.capacities}
    routes = {(r.from_location_id, r.to_location_id): r for r in s.routes}
    handling = defaultdict(int)  # baseline stock in handling units, every product
    for d in baseline:
        handling[d.location_id, d.day] += d.on_hand * info[d.product_id].handling_units_per_unit
    by_product = defaultdict(list)
    for d in baseline:
        by_product[d.product_id].append(d)
    window = days[: window_days(s)]
    shares, starved = {}, set()
    for p in sorted(products):
        h = info[p].handling_units_per_unit
        route, dispatch, receiving, storage = {}, {}, {}, {}
        for c in cands[p]:
            frm, to = c.route.from_location_id, c.route.to_location_id
            route[frm, to] = share(routes[frm, to].capacity_per_batch, p, ("route", frm, to))
            if frm not in dispatch:
                limit = caps[frm].dispatch if frm in caps else None
                dispatch[frm] = share(limit, p, ("dispatch", frm))
            if (to, c.arrival) not in receiving:
                limit = caps[to].receiving if to in caps else None
                receiving[to, c.arrival] = share(limit, p, ("receiving", to, c.arrival))
            if (to, days[0]) not in storage:
                limit = caps[to].storage if to in caps else None
                for day in days:
                    room = None if limit is None else max(0, limit - handling[to, day])
                    storage[to, day] = share(room, p, ("storage", to))
        budget = share(s.cost_budget_minor, p)
        shares[p] = Shares(
            route,
            dispatch,
            receiving,
            storage,
            share(s.global_handling, p),
            None if budget is None else Fraction(budget),
        )
        senders = protected_senders(s, by_product[p], p)
        usable = [  # a protected sender to a receiver with need (the localized split's users)
            c
            for c in cands[p]
            if c.route.from_location_id in senders and local.get((p, c.route.to_location_id), 0) > 0
        ]
        short = {(d.location_id, d.day) for d in by_product[p] if d.unmet > 0}

        def fits(c, sh=shares[p], h=h, short=short):
            frm, to = c.route.from_location_id, c.route.to_location_id
            cost = c.route.cost_per_handling_unit_usd
            unit_cost = Fraction(cost) * 100 * h if cost else Fraction(0)
            # The unit sits in storage at the receiver until its first short day in the window.
            waiting = []
            for day in (d for d in window if d >= c.arrival):
                if (to, day) in short:
                    break
                waiting.append(sh.storage_room[to, day])
            return all(
                v is None or v >= h
                for v in (
                    sh.route[frm, to],
                    sh.dispatch[frm],
                    sh.receiving[to, c.arrival],
                    sh.global_handling,
                    *waiting,
                )
            ) and (sh.cost_minor is None or sh.cost_minor >= unit_cost)

        if usable and not any(fits(c) for c in usable):
            starved.add(p)
    return Split(shares, frozenset(starved))
