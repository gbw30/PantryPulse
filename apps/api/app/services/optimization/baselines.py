"""Deterministic baselines: EQUAL_SHARE, MOST_URGENT_FIRST, SOONEST_EXPIRY_FIRST (W1-S02).

Same frozen scenario and feasible region as the optimizers: the same at-risk screen and the same
per-product capacity shares (decompose.split), and every plan is re-verified as a union.

Declared tie-breaks (V1-SPEC §14 leaves them to the builder):
- Receivers: earliest first-deficit day (Pantry: inside the window; Retail: first lost sale),
  then location_id; products in product_id order.
- Sources for a receiver: EQUAL_SHARE and MOST_URGENT_FIRST take the shortest travel first, then
  sender location_id; SOONEST_EXPIRY_FIRST takes the sender whose earliest eligible batch expires
  first (non-expiring last), then travel days, then location_id.
- Each request takes, route by route, the largest quantity the per-product feasibility probe
  accepts (binary search; the probe enforces BD-49, BD-51, need and every share).
- EQUAL_SHARE: total protected sender surplus is split equally between the receivers with need
  (water-filling, each capped at its need); remainders go one unit each in receiver order. A
  receiver that can't be served its full target stays short; nothing is redistributed.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from app.services.optimization.decompose import at_risk, protected_senders, split
from app.services.optimization.kernel import KernelLot, project_kernel
from app.services.optimization.v3 import RECEIVER_ROLES, candidates, dates, window_days
from app.services.optimization.verify import only_product, product_violations


@dataclass(frozen=True)
class HeuristicPlan:
    quantities: dict
    risky: frozenset[str]
    starved: frozenset[str]


def heuristic(s, method, measure, baseline) -> HeuristicPlan:
    risky = at_risk(s, baseline)
    cands = {p: candidates(s, p) for p in risky}
    parts = split(s, baseline, risky, measure, cands)
    quantities = {}
    by_product = defaultdict(list)
    for d in baseline:
        by_product[d.product_id].append(d)
    for p in sorted(risky - parts.starved):
        sp = only_product(s, p)  # every probe below touches this product only
        rows = by_product[p]
        senders = protected_senders(s, rows, p)
        usable = [c for c in cands[p] if c.route.from_location_id in senders]
        plan: dict = {}
        requests = deficits(s, rows)
        if method == "EQUAL_SHARE":
            supply = sum(surplus(s, p, loc) for loc in {c.route.from_location_id for c in usable})
            requests = equal_targets(requests, supply)
        for loc, wanted in requests:
            for c in sources(method, [c for c in usable if c.route.to_location_id == loc]):
                got = sum(q for k, q in plan.items() if k[2] == loc)
                if got >= wanted:
                    break
                fill(sp, p, plan, c.key, wanted - got, parts.shares[p], rows)
        quantities.update({k: q for k, q in plan.items() if q})
    return HeuristicPlan(quantities, frozenset(risky), parts.starved)


def deficits(s, rows) -> list[tuple[str, int]]:
    """(receiver, need) in declared order: first-deficit day, then location_id."""
    roles = {loc.id: loc.role for loc in s.locations}
    window = set(dates(s)[: window_days(s)])
    first_day, need = {}, defaultdict(int)
    for d in sorted(rows, key=lambda d: d.day):
        if roles[d.location_id] in RECEIVER_ROLES and d.unmet and d.day in window:
            need[d.location_id] += d.unmet
            first_day.setdefault(d.location_id, d.day)
    return [(loc, need[loc]) for loc in sorted(need, key=lambda loc: (first_day[loc], loc))]


def equal_targets(requests, supply) -> list[tuple[str, int]]:
    target = {loc: 0 for loc, _ in requests}
    need = dict(requests)
    while supply:
        active = [loc for loc, _ in requests if target[loc] < need[loc]]
        if not active:
            break
        share = supply // len(active)
        for loc in active:
            give = min(share or 1, need[loc] - target[loc], supply)
            target[loc] += give
            supply -= give
            if not supply:
                break
    return [(loc, target[loc]) for loc, _ in requests if target[loc]]


def sources(method, routes):
    if method == "SOONEST_EXPIRY_FIRST":
        return sorted(
            routes,
            key=lambda c: (
                min((b.expiry_date or date.max for b in c.batches), default=date.max),
                c.route.travel_days,
                c.route.from_location_id,
            ),
        )
    return sorted(routes, key=lambda c: (c.route.travel_days, c.route.from_location_id))


def fill(s, product_id, plan, key, room, shares, rows) -> None:
    """Add the largest feasible quantity (0..room) on one route to the plan."""
    start = plan.get(key, 0)

    def ok(extra):
        trial = {**plan, key: start + extra}
        return not product_violations(s, product_id, trial, shares, rows, changed_sender=key[1])

    low, high = 0, room
    while low < high:
        mid = (low + high + 1) // 2
        if ok(mid):
            low = mid
        else:
            high = mid - 1
    if low:
        plan[key] = start + low


def surplus(s, product_id, loc) -> int:
    """Units a sender can ship FEFO and still serve its 7-day forecast and keep its reserve."""
    first = s.first_planning_date
    own = sorted(
        (b for b in s.batches if (b.location_id, b.product_id) == (loc, product_id)),
        key=lambda b: (b.expiry_date or date.max, b.id),
    )
    arrivals = [
        KernelLot(f"i:{i.id}", i.quantity, i.arrival_date, i.expiry_date, True)
        for i in s.inbound
        if (i.location_id, i.product_id) == (loc, product_id)
    ]
    targets = next(
        (d.targets for d in s.demand if (d.location_id, d.product_id) == (loc, product_id)),
        (0,) * 7,
    )
    floor = next(
        (r.floor for r in s.reserves if (r.location_id, r.product_id) == (loc, product_id)), 0
    )
    points = tuple((first + timedelta(days=i), units) for i, units in enumerate(targets))

    def ok(q):
        lots = []
        for b in own:
            take = min(b.quantity, q)
            q -= take
            lots.append(KernelLot(f"b:{b.id}", b.quantity - take, first, b.expiry_date, False))
        days, _ = project_kernel(points, (*lots, *arrivals))
        return all(not d.unmet and d.on_hand >= floor for d in days)

    low, high = 0, sum(b.quantity for b in own)
    while low < high:
        mid = (low + high + 1) // 2
        if ok(mid):
            low = mid
        else:
            high = mid - 1
    return low
