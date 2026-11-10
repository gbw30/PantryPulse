# covers: V1-A17, V1-A15
"""Per-product decomposition: at-risk screen, advance split, starvation, union check, k-nearest.

Most cases reuse retail-usd-no-flip (data/demo/or-v3/README.md): DC D ships to store B on a
1-day route; lettuce P (4 units, expiring 11-04, need 4 expired + 14 lost = 18) and oil Q
(10 non-expiring bottles, need 14 lost). UNITS weights are therefore 18 : 14.
"""

import random
from datetime import date, timedelta
from itertools import product as grid

import pytest

from app.schemas.v1_planning import (
    NOT_AT_RISK_LABEL,
    CapacityV3,
    InboundV3,
    ORInputV3,
    ReserveV3,
)
from app.services.optimization import v3 as v3_module
from app.services.optimization.decompose import (
    allot,
    at_risk,
    floor_shares,
    need,
    protected_senders,
    split,
)
from app.services.optimization.methods import run_method
from app.services.optimization.product_model import _unit_cost
from app.services.optimization.projection import project_v3
from app.services.optimization.v3 import STARVED_LABEL, candidates, pack, quantities_of
from app.services.optimization.verify import cost_minor, verify_plan
from tests.optimization.test_retail_oracle import load

FIRST = date(2026, 11, 2)


def scenario(name="retail-usd-no-flip", **changes):
    s, _ = load(name)
    return s.model_copy(update=changes)


def priced_route(s, **changes):
    return s.model_copy(update={"routes": (s.routes[0].model_copy(update=changes),)})


def plan(s, p, q):
    return tuple(x.transfer for x in pack(s, {("P", "D", "B"): p, ("Q", "D", "B"): q}))


def quantities(result):
    return {t.product_id: t.quantity for t in result.transfers}


def test_at_risk_screen_uses_frozen_baseline():
    """Confirmed inbound and reserves come from the frozen scenario, not raw stock.

    14 bottles of oil arriving at B on day 1 cover all 14 sales, so oil leaves the screen.
    A reserve of 11 at the DC is above its 10 bottles, so the DC can't send oil at all.
    """
    s = scenario()
    assert at_risk(s, project_v3(s).days) == {"P", "Q"}
    arriving = InboundV3(
        id="in1",
        location_id="B",
        product_id="Q",
        quantity=14,
        arrival_date=FIRST,
        expiry_date=None,
        non_expiring=True,
    )
    covered = s.model_copy(update={"inbound": (arriving,), "inbound_file_provided": True})
    assert at_risk(covered, project_v3(covered).days) == {"P"}
    reserved = s.model_copy(
        update={"reserves": (ReserveV3(location_id="D", product_id="Q", floor=11),)}
    )
    assert protected_senders(reserved, project_v3(reserved).days, "Q") == set()  # B is short too
    result = run_method(reserved, "RETAIL_OPTIMIZED", "UNITS")
    assert quantities(result) == {"P": 4}


def test_not_at_risk_products_untouched_and_labeled():
    arriving = InboundV3(
        id="in1",
        location_id="B",
        product_id="Q",
        quantity=14,
        arrival_date=FIRST,
        expiry_date=None,
        non_expiring=True,
    )
    s = scenario(inbound=(arriving,), inbound_file_provided=True)
    for method in ("SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED"):
        result = run_method(s, method, "UNITS")
        q = next(p for p in result.products if p.product_id == "Q")
        assert (q.native_status, q.label) == (None, NOT_AT_RISK_LABEL)
        assert "Q" not in quantities(result)


def test_split_floors_by_handling_need_share_and_never_exceeds_capacity():
    rng = random.Random(20261107)
    for _ in range(2000):
        cap = rng.randint(0, 10_000)
        weights = {
            f"p{i}": rng.randint(0, 500) * rng.randint(1, 3) for i in range(rng.randint(1, 8))
        }
        shares = floor_shares(cap, weights)
        total = sum(weights.values())
        assert sum(shares.values()) <= cap
        for p, w in weights.items():
            assert shares[p] == (cap * w // total if total else 0)


@pytest.mark.parametrize("cost", [None, "0", "0.37", "12.5"])
def test_solver_unit_cost_agrees_with_the_verifier(cost):
    """One solver-side cost helper (split screen, product models, Pantry references); the
    independent verifier keeps its own formula, and the two must agree."""
    route = (
        scenario("retail-usd-flip")
        .routes[0]
        .model_copy(update={"cost_per_handling_unit_usd": cost})
    )
    for h, units in ((1, 1), (3, 7)):
        assert _unit_cost(route, h) * units == cost_minor(route, units, h)


def test_split_uses_handling_units():
    """Oil at 3 handling units per bottle weighs 14 × 3 = 42 against lettuce's 18 × 1."""
    s = scenario("retail-usd-flip")
    heavy = s.products[1].model_copy(update={"handling_units_per_unit": 3})
    s = priced_route(
        s.model_copy(update={"products": (s.products[0], heavy)}), capacity_per_batch=12
    )
    # shares: lettuce 12 × 18 // 60 = 3 handling; oil 12 × 42 // 60 = 8 handling = 2 bottles
    assert quantities(run_method(s, "RETAIL_OPTIMIZED", "UNITS")) == {"P": 3, "Q": 2}


def test_starved_product_reported_not_optimized():
    """Route capacity 1: proportional shares 18/32 and 14/32 of one unit are both 0. Lettuce
    (larger weight) gets the one unit's handling; nothing is left for oil, which is starved."""
    s = priced_route(scenario("retail-usd-flip"), capacity_per_batch=1)
    result = run_method(s, "RETAIL_OPTIMIZED", "UNITS")
    q = next(x for x in result.products if x.product_id == "Q")
    assert (q.native_status, q.label) == (None, STARVED_LABEL)
    assert quantities(result) == {"P": 1}
    assert verify_plan(s, result.transfers).passed


def test_starved_product_gets_one_unit_first():
    """USD on retail-usd-flip: lettuce's share 4 x 18 // 158 = 0 can't fit a unit, so it gets
    one unit's handling and oil splits the remaining 3 (README)."""
    result = run_method(scenario("retail-usd-flip"), "RETAIL_OPTIMIZED", "USD")
    assert quantities(result) == {"P": 1, "Q": 3}
    assert not any(x.label == STARVED_LABEL for x in result.products)


def test_allot_never_exceeds_cap_and_starves_no_one_when_units_fit():
    rng = random.Random(20261108)
    for _ in range(3000):
        n = rng.randint(1, 8)
        weights = {f"p{i}": rng.randint(0, 50) * rng.randint(0, 3) for i in range(n)}
        handling = {p: rng.randint(1, 4) for p in weights}
        cap = rng.randint(0, 60)
        shares = allot(cap, weights, handling)
        assert set(shares) == set(weights)
        assert sum(shares.values()) <= cap
        for p, share in shares.items():
            assert share % handling[p] == 0
            assert share == 0 or weights[p] > 0
        positive = [p for p, w in weights.items() if w > 0]
        if cap >= sum(handling[p] for p in positive):
            assert all(shares[p] >= handling[p] for p in positive)
        total = sum(weights.values())
        floors = {p: (cap * w // total // handling[p]) for p, w in weights.items()} if total else {}
        if total and all(floors[p] for p in positive):  # every share fits: plain floor split
            assert shares == {p: floors[p] * handling[p] for p in weights}


def test_allot_priority_largest_weight_then_product_id():
    # proportional shares of 3 are all below 2 handling units; c (weight 9) goes first
    assert allot(3, {"a": 5, "b": 5, "c": 9}, {"a": 2, "b": 2, "c": 2}) == {"a": 0, "b": 0, "c": 2}
    assert allot(2, {"b": 5, "a": 5}, {"a": 2, "b": 2}) == {"a": 2, "b": 0}  # tie: product id
    # 10 split 1 : 9 gives a 1 handling unit (< 2), so a takes 2 and b the remaining 8
    assert allot(10, {"a": 1, "b": 9}, {"a": 2, "b": 1}) == {"a": 2, "b": 8}


def test_localized_split_only_products_with_need_at_receiver():
    """Oil sells only at a new store C, so B's route capacity 4 goes to lettuce alone
    (network weights would have given it 4 x 18 // 32 = 2)."""
    s = scenario("retail-usd-flip")
    b = next(loc for loc in s.locations if loc.id == "B")
    c = b.model_copy(update={"id": "C", "name": "Store C"})
    demand = []
    for d in s.demand:
        if (d.location_id, d.product_id) == ("B", "Q"):
            demand.append(d.model_copy(update={"location_id": "C"}))
            demand.append(
                d.model_copy(update={"targets": (0,) * 7, "central_literals": ("0",) * 7})
            )
        else:
            demand.append(d)
    to_c = s.routes[0].model_copy(update={"to_location_id": "C", "capacity_per_batch": None})
    s = s.model_copy(
        update={
            "locations": (*s.locations, c),
            "demand": tuple(demand),
            "routes": (*s.routes, to_c),
        }
    )
    baseline = project_v3(s).days
    risky = at_risk(s, baseline)
    cands = {p: candidates(s, p) for p in risky}
    parts = split(s, baseline, risky, "UNITS", cands)
    assert parts.shares["P"].route["D", "B"] == 4
    assert parts.shares["Q"].route["D", "B"] == 0
    result = run_method(s, "RETAIL_OPTIMIZED", "UNITS")
    assert quantities(result)["P"] == 4 and verify_plan(s, result.transfers).passed


def test_cost_budget_split_union_within_budget():
    """$1.00 per handling unit, budget 600 cents: lettuce 600 × 18 // 32 = 337 (3 units),
    oil 600 × 14 // 32 = 262 (2 units). Each alone would spend the whole budget."""
    s = priced_route(scenario(cost_budget_minor=600), cost_per_handling_unit_usd="1.00")
    result = run_method(s, "RETAIL_OPTIMIZED", "UNITS")
    assert quantities(result) == {"P": 3, "Q": 2}
    assert verify_plan(s, result.transfers).passed


def test_storage_shared_across_products():
    """B holds 6 handling units. Both products arrive on day 2 and B sells 2 of each per day,
    so day 2 ends with (y_P - 2) + (y_Q - 2). Room 6 splits 3 : 2, so y_P <= 4 (its sell
    limit) and y_Q <= 4. Without the split oil alone could take y_Q = 8 and overflow."""
    s = scenario(
        capacities=(CapacityV3(location_id="B", receiving=None, dispatch=None, storage=6),)
    )
    result = run_method(s, "RETAIL_OPTIMIZED", "UNITS")
    assert quantities(result) == {"P": 4, "Q": 4}
    assert verify_plan(s, result.transfers).passed
    assert not verify_plan(s, plan(s, 4, 8)).passed


@pytest.mark.parametrize(
    ("kind", "at_bound", "violation"),
    [
        ("route", lambda s, n: priced_route(s, capacity_per_batch=n), "ROUTE_CAPACITY"),
        (
            "dispatch",
            lambda s, n: s.model_copy(
                update={
                    "capacities": (
                        CapacityV3(location_id="D", receiving=None, dispatch=n, storage=None),
                    )
                }
            ),
            "DISPATCH_CAPACITY",
        ),
        (
            "receiving",
            lambda s, n: s.model_copy(
                update={
                    "capacities": (
                        CapacityV3(location_id="B", receiving=n, dispatch=None, storage=None),
                    )
                }
            ),
            "RECEIVING_CAPACITY",
        ),
        (
            "global",
            lambda s, n: s.model_copy(update={"global_handling": n}),
            "GLOBAL_HANDLING_CAPACITY",
        ),
        (
            "cost",
            lambda s, n: priced_route(
                s.model_copy(update={"cost_budget_minor": 100 * n}),
                cost_per_handling_unit_usd="1.00",
            ),
            "TRANSPORT_COST_BUDGET",
        ),
    ],
)
def test_union_check_fails_on_planted_violation(kind, at_bound, violation):
    """Plan: 3 lettuce + 2 oil = 5 handling units on one route, from D, into B, on 11-03."""
    s = scenario()
    assert verify_plan(at_bound(s, 5), plan(s, 3, 2)).passed, kind
    report = verify_plan(at_bound(s, 4), plan(s, 3, 2))
    assert violation in report.violations, kind


def test_union_check_fails_on_planted_storage_violation():
    """Plan 4 + 4 ends day 2 at B with 2 + 2 = 4 handling units."""
    s = scenario()

    def storage(n):
        return s.model_copy(
            update={
                "capacities": (
                    CapacityV3(location_id="B", receiving=None, dispatch=None, storage=n),
                )
            }
        )

    assert verify_plan(storage(4), plan(s, 4, 4)).passed
    assert "STORAGE_CAPACITY" in verify_plan(storage(3), plan(s, 4, 4)).violations


def monolithic_optimum(s):
    """Enumerate every plan of the two-product network; the best verified sum of objectives."""
    best = None
    for p, q in grid(range(5), range(11)):
        try:
            transfers = plan(s, p, q)
        except ValueError:
            continue
        report = verify_plan(s, transfers)
        if report.passed:
            value = sum(d.expired + d.unmet for d in report.days)  # w_exp = w_lost = 1
            best = value if best is None else min(best, value)
    return best


def per_product_sum(s, result):
    return sum(e.expired_with_plan + e.unmet_with_plan for e in result.effects)


def test_decomposed_equals_monolithic_when_no_shared_capacity_binds():
    s = scenario()
    result = run_method(s, "RETAIL_OPTIMIZED", "UNITS")
    assert verify_plan(s, result.transfers).passed
    assert per_product_sum(s, result) == monolithic_optimum(s) == 14  # README: 10 + 4


def test_decomposed_feasible_for_monolithic_when_capacity_binds():
    s = scenario("retail-usd-flip")
    result = run_method(s, "RETAIL_OPTIMIZED", "UNITS")
    assert verify_plan(s, result.transfers).passed  # feasible for the single network model
    gap = per_product_sum(s, result) - monolithic_optimum(s)
    assert gap >= 0  # recorded, not asserted to be zero: README 27 vs 24 here
    assert (per_product_sum(s, result), monolithic_optimum(s)) == (27, 24)


def test_no_network_objective_total():
    result = run_method(scenario("retail-usd-flip"), "RETAIL_OPTIMIZED", "UNITS")
    assert result.objective is None  # lettuce cases and oil bottles are never added
    assert "solved per product: 2 OPTIMAL, 0 FEASIBLE" in result.labels
    assert "units objective is per product; not summed across products" in result.labels


def test_pantry_at_risk_uses_the_window_and_reports_no_total():
    """pantry-four-methods: need is window unmet only (README: targets 3, 6, 6 over 2 days;
    the demand of 1 a day on days 3-7 is outside). With a 1-day window P1 has no need."""
    s = scenario("pantry-four-methods")
    assert need(s, project_v3(s).days, by_location=True) == {
        ("F", "H"): 0,
        ("F", "P1"): 3,
        ("F", "P2"): 6,
        ("F", "P3"): 6,
    }
    one_day = s.model_copy(update={"planning_days": 1})
    local = need(one_day, project_v3(one_day).days, by_location=True)
    assert (local[("F", "P1")], local[("F", "P2")], local[("F", "P3")]) == (0, 3, 3)
    for method in ("CLASSICAL_GP", "EGP_PI_INSPIRED"):
        result = run_method(s, method, "UNITS")
        assert result.verified and result.objective is None  # no network objective total
        assert "solved per product: 1 OPTIMAL, 0 FEASIBLE" in result.labels


def test_storage_share_too_small_is_starved_not_optimized():
    """P2 storage 1, beans and rice needed 3, 0, 2 there (equal need): allot gives the one unit
    of room to beans (equal weight, then product id), none to rice. A unit shipped on Nov 2
    waits at P2 through Nov 3 (no demand), so rice can't move one unit under its share. Rice is
    reported starved, never optimized; with no storage limit both move."""
    from tests.optimization.test_pantry_methods import moved, with_rice

    demand = [("P2", p, (3, 0, 2, 0, 0, 0, 0)) for p in ("F", "G")]
    for storage, expected in ((1, {"F": 1}), (None, {"F": 2, "G": 2})):
        s = with_rice(
            demand, CapacityV3(location_id="P2", receiving=None, dispatch=None, storage=storage)
        )
        s = s.model_copy(update={"planning_days": 3})
        for method in ("CLASSICAL_GP", "EQUAL_SHARE"):
            result = run_method(s, method, "UNITS")
            assert moved(result) == expected, (storage, method)
            rice = next(p for p in result.products if p.product_id == "G")
            starved = (None, STARVED_LABEL) if storage else (rice.native_status, None)
            assert (rice.native_status, rice.label) == starved, (storage, method)


@pytest.mark.parametrize("method", ("RETAIL_OPTIMIZED", "SOONEST_EXPIRY_FIRST"))
def test_share_only_on_a_route_that_breaks_donor_protection_is_starved(method):
    """F2 residual: lost-vs-waste plus store C, which holds exactly its own seven-day forecast
    (7 non-expiring units, selling 1/day). C is protected with no plan, but sending one unit
    leaves it short on day 7. With A -> B at capacity 0, the only route with room for a unit is
    C -> B, which BD-49 forbids, so P is starved, never optimized. With room on A -> B, A moves
    units. With C -> B alone nothing can move whatever the capacity, so it is no capacity
    verdict: P is optimized (0 moves) as before."""
    s = scenario("retail-lost-vs-waste")
    store_c = s.locations[0].model_copy(update={"id": "C", "name": "Store C"})
    c1 = s.batches[0].model_copy(
        update={
            "id": "c1",
            "location_id": "C",
            "quantity": 7,
            "expiry_date": None,
            "non_expiring": True,
        }
    )
    from_c = s.routes[0].model_copy(update={"from_location_id": "C"})
    s = s.model_copy(
        update={
            "locations": (*s.locations, store_c),
            "batches": (*s.batches, c1),
            "demand": (*s.demand, s.demand[0].model_copy(update={"location_id": "C"})),
            "routes": (*s.routes, from_c),
        }
    )
    assert protected_senders(s, project_v3(s).days, "P") == {"A", "C"}
    no_room = s.routes[0].model_copy(update={"capacity_per_batch": 0})
    for routes, senders, label in (
        ((no_room, from_c), set(), STARVED_LABEL),
        ((s.routes[0], from_c), {"A"}, None),
        ((from_c,), set(), None),
    ):
        result = run_method(s.model_copy(update={"routes": routes}), method, "UNITS")
        assert result.verified, result.failure_reason
        assert {t.from_location_id for t in result.transfers} == senders
        (p,) = result.products
        assert p.label == label, (method, len(routes))
        if label:
            assert p.native_status is None


@pytest.mark.parametrize("mode", ("retail", "pantry"))
def test_one_unit_screen_agrees_with_the_verifier_on_donor_protection(mode):
    """The F2 screen runs the model's own BD-49 lots and FEFO kernel. For one unit on every
    candidate of a generated network it must agree with the independent verifier's probe."""
    from app.services.optimization.product_model import one_unit_protected
    from app.services.optimization.v3 import Shares
    from app.services.optimization.verify import product_violations

    s = bench_scenario(16, 6, mode)
    baseline = project_v3(s).days
    no_limits = Shares({}, {}, {}, {}, None, None)
    seen = set()
    for product in s.products:
        sends = one_unit_protected(s, product.id)
        rows = [d for d in baseline if d.product_id == product.id]
        for c in candidates(s, product.id):
            found = product_violations(s, product.id, {c.key: 1}, no_limits, rows)
            assert sends(c) == ("DONOR_PROTECTION" not in found), c.key
            seen.add(sends(c))
    assert seen == {True, False}


def test_k_nearest_routes_used(monkeypatch):
    """Three DCs hold oil for B at 1, 2 and 3 days; with k = 1 only the 1-day DC is a candidate."""
    s = scenario()
    dcs = tuple(
        s.locations[0].model_copy(update={"id": f"D{i}", "name": f"DC {i}"}) for i in (1, 2, 3)
    )
    s = s.model_copy(
        update={
            "locations": (*dcs, s.locations[1]),
            "products": (s.products[1],),
            "batches": tuple(
                s.batches[1].model_copy(update={"id": f"q{i}", "location_id": f"D{i}"})
                for i in (1, 2, 3)
            ),
            "demand": (s.demand[1],),
            "routes": tuple(
                s.routes[0].model_copy(update={"from_location_id": f"D{i}", "travel_days": i})
                for i in (3, 1, 2)
            ),
        }
    )
    assert [c.route.from_location_id for c in candidates(s, "Q", k=2)] == ["D1", "D2"]
    monkeypatch.setattr(v3_module, "K_NEAREST", 1)
    result = run_method(s, "RETAIL_OPTIMIZED", "UNITS")
    assert {t.from_location_id for t in result.transfers} == {"D1"}
    assert sum(t.quantity for t in result.transfers) == 10  # D1's 10 bottles sell days 2-6
    assert result.transfers[0].arrival_date == FIRST + timedelta(days=1)


def test_method_search_deadline_fails_honestly(monkeypatch):
    """Products the method budget can't reach are never reported as optimized."""
    from app.services.optimization import methods

    monkeypatch.setattr(methods, "METHOD_SEARCH_S", 0.0)
    result = run_method(scenario(), "RETAIL_OPTIMIZED", "UNITS")
    assert (result.verified, result.transfers, result.native_status) == (False, (), "UNKNOWN")
    assert result.failure_reason == "METHOD_TIME_LIMIT:P,Q"
    assert {p.native_status for p in result.products} == {"UNKNOWN"}


def test_method_deadline_counts_preparation(monkeypatch):
    """The budget starts when the method does: slow preparation leaves no search time, and the
    method reports METHOD_TIME_LIMIT instead of overrunning into a hard step timeout."""
    import time

    from app.services.optimization import methods

    def slow_split(*args, **kwargs):
        time.sleep(0.3)
        return split(*args, **kwargs)

    monkeypatch.setattr(methods, "split", slow_split)
    result = run_method(scenario(), "RETAIL_OPTIMIZED", "UNITS", method_seconds=0.2)
    assert (result.verified, result.transfers) == (False, ())
    assert result.failure_reason == "METHOD_TIME_LIMIT:P,Q"


@pytest.mark.parametrize(
    ("fixture", "method", "late"),
    [
        (None, "SOONEST_EXPIRY_FIRST", "P,Q"),
        ("pantry-four-methods", "EQUAL_SHARE", "F"),
        ("pantry-four-methods", "MOST_URGENT_FIRST", "F"),
    ],
)
def test_heuristics_stop_at_the_method_deadline(fixture, method, late):
    s = scenario() if fixture is None else load(fixture)[0]
    result = run_method(s, method, "UNITS", method_seconds=0)
    assert (result.verified, result.transfers, result.native_status) == (False, (), None)
    assert result.failure_reason == f"METHOD_TIME_LIMIT:{late}"


def bench_scenario(locations, products, mode="retail"):
    """The scripts/or/bench_v1.py generator at a small size (same shape as 100 × 500)."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / "scripts" / "or" / "bench_v1.py"
    spec = importlib.util.spec_from_file_location("bench_v1", path)
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    return bench.generate(locations, products, mode)


def test_bench_clean_tree_ignores_only_its_evidence_file(tmp_path):
    """The first porcelain line starts with a space (" M path"); the path must survive it."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / "scripts" / "or" / "bench_v1.py"
    spec = importlib.util.spec_from_file_location("bench_v1", path)
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    evidence = tmp_path / "docs/evidence.json"
    status = " M docs/evidence.json\n?? notes.txt\n"
    assert bench.changed_paths(status, tmp_path, evidence) == ["notes.txt"]
    assert bench.changed_paths(" M docs/evidence.json\n", tmp_path, evidence) == []


def test_restricted_probe_equals_full_probe():
    """The heuristic probe replays only the changed sender and its receivers. Starting from a
    plan that passes, that must give exactly the full probe's violations for any change."""
    from collections import defaultdict

    from app.services.optimization.baselines import heuristic
    from app.services.optimization.decompose import split
    from app.services.optimization.verify import product_violations

    s = bench_scenario(16, 6)
    baseline = project_v3(s).days
    plan = heuristic(s, "SOONEST_EXPIRY_FIRST", "UNITS", baseline)
    risky = sorted(plan.risky - plan.starved)
    cands = {p: candidates(s, p) for p in plan.risky}
    parts = split(s, baseline, plan.risky, "UNITS", cands)
    rows = defaultdict(list)
    for d in baseline:
        rows[d.product_id].append(d)
    outcomes = set()
    for p in risky:
        base = {k: q for k, q in plan.quantities.items() if k[0] == p}
        assert not product_violations(s, p, base, parts.shares[p], rows[p])
        for c, delta in grid(cands[p], (1, 5)):
            trial = {**base, c.key: base.get(c.key, 0) + delta}
            full = product_violations(s, p, trial, parts.shares[p], rows[p])
            fast = product_violations(
                s, p, trial, parts.shares[p], rows[p], changed_sender=c.key[1]
            )
            assert set(full) == set(fast), (p, c.key, delta)
            outcomes.add(bool(full))
    assert outcomes == {True, False}  # both accepted and rejected changes were compared


def test_verifier_never_loads_ortools():
    """Independent verification: the verifier, its residual rooms and the per-product probe run
    in a process where OR-Tools was never imported (verify.py: "Never imports CP")."""
    import subprocess
    import sys
    from pathlib import Path

    from tests.optimization.test_retail_oracle import DATA

    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from app.schemas.v1_planning import ORInputV3\n"
        "from app.services.optimization.projection import project_v3\n"
        "from app.services.optimization.verify import (\n"
        "    product_violations, residual_shares, verify_plan)\n"
        "s = ORInputV3.model_validate_json(Path(sys.argv[1]).read_text())\n"
        "days = project_v3(s).days\n"
        "assert verify_plan(s, ()).passed\n"
        "p = s.products[0].id\n"
        "rooms = residual_shares(s, (), days, days)(p)\n"
        "product_violations(s, p, {}, rooms, days)\n"
        "loaded = sorted(m for m in sys.modules if m.split('.')[0] == 'ortools')\n"
        "assert not loaded, loaded[:3]\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code, str(DATA / "retail-usd-no-flip.input.json")],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]


def relay_network():
    """Store X sends its short-dated lot x1 to Y (sells 5 a day) and receives Z's later lot z1,
    which would expire unsold at Z (the bench 20 × 12 P009/R009 pattern, by hand)."""
    s, _ = load("retail-expiry-transfer")
    row = s.demand[0]

    def demand(loc, per_day):
        return row.model_copy(
            update={
                "location_id": loc,
                "central_literals": (str(per_day),) * 7,
                "targets": (per_day,) * 7,
            }
        )

    lot = s.batches[0]
    batches = (
        lot.model_copy(update={"id": "x1", "location_id": "X", "quantity": 10}),  # expires Nov 4
        s.batches[1].model_copy(update={"id": "x2", "location_id": "X", "quantity": 5}),
        lot.model_copy(
            update={"id": "z1", "location_id": "Z", "quantity": 2, "expiry_date": date(2026, 11, 7)}
        ),
    )
    route = s.routes[0]
    return ORInputV3.model_validate(
        s.model_copy(
            update={
                "locations": tuple(
                    s.locations[0].model_copy(update={"id": loc, "name": f"Store {loc}"})
                    for loc in "XYZ"
                ),
                "batches": batches,
                "demand": (demand("X", 1), demand("Y", 5), demand("Z", 0)),
                "routes": tuple(
                    route.model_copy(update={"from_location_id": a, "to_location_id": b})
                    for a, b in (("X", "Y"), ("Z", "X"))
                ),
            }
        ).model_dump()
    )


def test_send_and_receive_moves_different_lots_and_never_relays():
    """INV-07: a location may send and receive the same product, but it ships only its own
    snapshot lots, every unit it receives is sold there, and an arrival never covers a send."""
    s = relay_network()

    def transfers(x_to_y, z_to_x=0):
        return tuple(
            p.transfer for p in pack(s, {("P", "X", "Y"): x_to_y, ("P", "Z", "X"): z_to_x})
        )

    def expired(plan):
        return sum(d.expired for d in project_v3(s, pack(s, quantities_of(plan))).days)

    sends = transfers(7, 2)
    report = verify_plan(s, sends)
    assert report.passed, report.violations
    splits = {
        (p.transfer.from_location_id, p.transfer.to_location_id): p.splits for p in report.packed
    }
    assert splits == {("X", "Y"): (("x1", 7),), ("Z", "X"): (("z1", 2),)}  # own lots only
    received = [(lot.units, sum(lot.consumed)) for lot in report.sublots]
    assert received == [(7, 7), (2, 2)] or received == [(2, 2), (7, 7)]  # sold where received
    assert expired(sends) < expired(transfers(7))  # the receive saves z1 from expiring at Z

    # X cannot ship the 2 units it receives: 16 > its own 15 on hand
    over = (sends[0].model_copy(update={"quantity": 16}), sends[1])
    assert verify_plan(s, over).violations == ("SOURCE_OVERDRAWN",)
    # X ships 9 and would sell out with Z's 2 units, but protection ignores arrivals
    shipped = transfers(9, 2)
    with_arrival = project_v3(s, pack(s, quantities_of(shipped))).days
    assert not any(d.unmet for d in with_arrival if d.location_id == "X")
    assert verify_plan(s, shipped).violations == ("DONOR_PROTECTION",)
