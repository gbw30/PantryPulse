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

from app.schemas.v1_planning import NOT_AT_RISK_LABEL, CapacityV3, InboundV3, ReserveV3
from app.services.optimization import v3 as v3_module
from app.services.optimization.decompose import at_risk, floor_shares, protected_senders
from app.services.optimization.methods import run_method
from app.services.optimization.projection import project_v3
from app.services.optimization.v3 import STARVED_LABEL, candidates, pack
from app.services.optimization.verify import verify_plan
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
    result = run_method(scenario("retail-usd-flip"), "RETAIL_OPTIMIZED", "USD")
    p = next(x for x in result.products if x.product_id == "P")
    assert (p.native_status, p.label) == (None, STARVED_LABEL)
    assert quantities(result) == {"Q": 3}


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


def bench_scenario(locations, products, mode="retail"):
    """The scripts/or/bench_v1.py generator at a small size (same shape as 100 × 500)."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / "scripts" / "or" / "bench_v1.py"
    spec = importlib.util.spec_from_file_location("bench_v1", path)
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    return bench.generate(locations, products, mode)


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
