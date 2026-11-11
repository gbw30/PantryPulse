# covers: V1-A14
"""Pantry methods on or-input-v3: hand values, an enumeration oracle independent of CP-SAT, the
EGP group/coverage rules, hubs never receiving, BD-51 and both transfer modes (W1-S02..S04).

Hand values come from data/demo/or-v3/README.md (pantry-four-methods).
"""

import itertools
from decimal import Decimal
from fractions import Fraction
from uuid import UUID

import ortools
import pytest
from ortools.sat.python import cp_model

from app.schemas.v1_planning import (
    DEFAULT_PANTRY_POLICY,
    METHODS_BY_MODE,
    BatchV3,
    CapacityV3,
    ORInputV3,
    ProductV3,
    SolverRun,
)
from app.services.optimization.compare import compare_methods, publishable
from app.services.optimization.methods import PER_PRODUCT_LABEL, run_method
from app.services.optimization.pantry import (
    SINGLETON_LABEL,
    coefficients,
    goals,
    pantry_objectives,
    solve_pantry_product,
)
from app.services.optimization.projection import project_v3
from app.services.optimization.v3 import Shares
from app.services.optimization.verify import verify_plan
from tests.optimization.test_retail_oracle import load

PANTRY = METHODS_BY_MODE["PANTRY"]
S = 10_000


def plan_of(result):
    assert result.verified, result.failure_reason
    out = {}
    for t in result.transfers:
        out[t.to_location_id] = out.get(t.to_location_id, 0) + t.quantity
    return out


@pytest.mark.parametrize("method", PANTRY)
def test_pantry_four_methods_hand_values(method):
    s, expected = load("pantry-four-methods")
    assert plan_of(run_method(s, method, "UNITS")) == expected["plans"][method]


def test_methods_disagree_on_the_fixture():
    """Equal-share, most-urgent, GP and EGP each give a different plan (README)."""
    _, expected = load("pantry-four-methods")
    plans = [tuple(sorted(expected["plans"][m].items())) for m in PANTRY[1:]]
    assert len(set(plans)) == 4


@pytest.mark.parametrize("method", ("CLASSICAL_GP", "EGP_PI_INSPIRED"))
def test_compiled_objective_replays_hand_value(method):
    s, expected = load("pantry-four-methods")
    want = expected["objectives"][method]
    result = run_method(s, method, "UNITS")
    report = verify_plan(s, result.transfers)
    assert pantry_objectives(s, report, method)["F"] == want["compiled"]
    assert coefficients(s.policy, method, 3, False, True) == tuple(want["coefficients"])
    assert result.native_status == "OPTIMAL"
    assert result.products[0].native_status == "OPTIMAL"
    assert PER_PRODUCT_LABEL in result.labels


def test_gp_plan_scores_worse_under_egp():
    """README: the GP plan replays to 6 199 850 under the EGP objective (5 799 800 optimal)."""
    s, _ = load("pantry-four-methods")
    gp = run_method(s, "CLASSICAL_GP", "UNITS")
    assert pantry_objectives(s, verify_plan(s, gp.transfers), "EGP_PI_INSPIRED")["F"] == 6_199_850


def oracle(s, research):
    """Enumerate every hub plan; a case arriving on day 2 serves day-2 demand only."""
    w, policy = s.planning_days, s.policy
    pantries = sorted(d.location_id for d in s.demand)
    demand = {d.location_id: d.targets for d in s.demand}
    rates = {v.location_id: v for v in s.vulnerability}
    stock = sum(b.quantity for b in s.batches)

    def weight(p):
        if not research:
            return Fraction(1)
        mix = sum(
            Fraction(c.percent, 100) * Fraction(Decimal(getattr(rates[p], c.attribute_id)))
            for c in policy.coefficients
        )
        return 1 + Fraction(policy.lambda_percent, 100) * mix

    scores = {}
    for plan in itertools.product(*(range(sum(demand[p][1:w]) + 1) for p in pantries)):
        if sum(plan) > stock:
            continue
        qs = []
        for p, x in zip(pantries, plan, strict=True):
            target = sum(demand[p][:w])
            qs.append(int(S * weight(p) * (target - x) / target))  # exact floor, positive
        beta, n = Fraction(policy.beta_percent, 100), len(qs)
        value = beta * sum(qs) / S + (1 - beta) * max(qs) / S
        if research:
            for flags, cap, gamma in (
                ([q > policy.ap_threshold for q in qs], policy.ap_cap_bp, policy.gamma_ap_percent),
                (
                    [n * q - sum(qs) > n * policy.rp_threshold for q in qs],
                    policy.rp_cap_bp,
                    policy.gamma_rp_percent,
                ),
            ):
                value += Fraction(gamma, 100 * S * n) * max(0, S * sum(flags) - cap * n)
        scores[plan] = value
    best = min(scores.values())
    winners = [dict(zip(pantries, p, strict=True)) for p, v in scores.items() if v == best]
    return [{k: v for k, v in plan.items() if v} for plan in winners]


@pytest.mark.parametrize("method", ("CLASSICAL_GP", "EGP_PI_INSPIRED"))
def test_pantry_oracle(method):
    s, expected = load("pantry-four-methods")
    winners = oracle(s, method == "EGP_PI_INSPIRED")
    assert winners == [expected["plans"][method]]  # unique optimum
    assert plan_of(run_method(s, method, "UNITS")) == winners[0]


def test_goals_use_the_window_only():
    """Days 3-7 carry demand 1 each, outside the 2-day window."""
    s, _ = load("pantry-four-methods")
    assert goals(s, "F") == [("P1", 3), ("P2", 6), ("P3", 6)]


def test_ap_flag_unset_at_equality():
    """With no stock to move, the model's objective is the baseline's. P2 sells its 1 case and
    misses 3 of 4, so q = 7500, exactly the AP threshold: unflagged.
    q = (P1 14000, P2 7500, P3 12000): AP flags P1, P3 -> excess 20000 - 7500 = 12500;
    RP: 3 x 14000 - 33500 = 8500 > 7500 flags P1 only -> excess 2500.
    Compiled: 150 x (33500 + 14000) + 100 x (12500 + 2500) + 3 x 0 = 8 625 000."""
    s, _ = load("pantry-four-methods")
    p2 = s.demand[1].model_copy(update={"targets": (2, 2, 0, 0, 0, 0, 0)})
    own = s.batches[0].model_copy(update={"id": "p2b", "location_id": "P2", "quantity": 1})
    s = s.model_copy(update={"batches": (own,), "demand": (s.demand[0], p2, s.demand[2])})
    baseline = project_v3(s).days
    none = Shares({}, {}, {}, {}, None, None)
    outcome = solve_pantry_product(s, "F", (), none, baseline, set(), 5.0, method="EGP_PI_INSPIRED")
    report = verify_plan(s, ())
    assert outcome.primary == pantry_objectives(s, report, "EGP_PI_INSPIRED")["F"] == 8_625_000


def test_rp_flag_unset_at_equality():
    """No hub stock; each pantry serves from its own cases. q = floor(S x v x unmet / target):
    P1 (v 1.4) misses 5 of 28 -> 2500; P2 (v 1) misses 5 of 8 -> 6250; P3 (v 1.2) 5 of 24 -> 2500.
    W = 11250, Z = 6250. RP for P2: 3 x 6250 - 11250 = 7500 = 3 x 2500, exactly the threshold:
    unflagged, so RP excess is 0 (flagged it would be 2500, +250 000). No q is above 7500 (AP).
    Compiled: 150 x (11250 + 6250) = 2 625 000."""
    s, _ = load("pantry-four-methods")
    targets = {"P1": (14, 14), "P2": (4, 4), "P3": (12, 12)}
    stock = {"P1": 23, "P2": 3, "P3": 19}
    demand = tuple(
        d.model_copy(update={"targets": (*targets[d.location_id], 0, 0, 0, 0, 0)}) for d in s.demand
    )
    own = tuple(
        s.batches[0].model_copy(update={"id": f"{loc}b", "location_id": loc, "quantity": qty})
        for loc, qty in stock.items()
    )
    s = s.model_copy(update={"batches": own, "demand": demand})
    baseline = project_v3(s).days
    none = Shares({}, {}, {}, {}, None, None)
    outcome = solve_pantry_product(s, "F", (), none, baseline, set(), 5.0, method="EGP_PI_INSPIRED")
    report = verify_plan(s, ())
    assert outcome.primary == pantry_objectives(s, report, "EGP_PI_INSPIRED")["F"] == 2_625_000


@pytest.mark.parametrize(
    ("gammas", "plan"),
    [
        ({}, {"P1": 2, "P2": 2}),
        ({"gamma_ap_percent": 0}, {"P1": 2, "P3": 2}),
        ({"gamma_ap_percent": 0, "gamma_rp_percent": 0}, {"P1": 3, "P3": 1}),
    ],
)
def test_penalty_ablation_changes_the_egp_plan(gammas, plan):
    """TEST-EGP-04: zeroing gamma_AP changes the optimum, and with AP off zeroing gamma_RP changes
    it again, so both penalty terms are active on this fixture. (gamma_RP = 0 alone keeps
    P1 2, P2 2 here.) Each optimum is the enumeration oracle's unique winner."""
    s, _ = load("pantry-four-methods")
    s = s.model_copy(update={"policy": s.policy.model_copy(update=gammas)})
    assert oracle(s, True) == [plan]
    assert plan_of(run_method(s, "EGP_PI_INSPIRED", "UNITS")) == plan


def scanned_references(s, product_id):
    """Oracle: the original full scan of routes, batches and inbound for one product."""
    from app.services.optimization.product_model import _unit_cost
    from app.services.optimization.v3 import dates, route_allowed

    product = next(p for p in s.products if p.id == product_id)
    first, last = s.first_planning_date, dates(s)[-1]
    unit_costs = {}
    for r in s.routes:
        if route_allowed(s, r):
            unit_costs.setdefault(r.from_location_id, []).append(
                _unit_cost(r, product.handling_units_per_unit)
            )
    cost = sum(
        (
            b.quantity * max(unit_costs.get(b.location_id, ()), default=Fraction(0))
            for b in s.batches
            if b.product_id == product_id and (b.expiry_date is None or b.expiry_date >= first)
        ),
        Fraction(0),
    )
    stock = sum(b.quantity for b in s.batches if b.product_id == product_id) + sum(
        i.quantity for i in s.inbound if i.product_id == product_id and i.arrival_date <= last
    )
    return cost, stock


def test_indexed_goals_and_references_equal_the_scan():
    """Code review W2-01 (7): one index per call instead of a full scan per product."""
    from app.services.optimization.pantry import pantry_index, references
    from tests.optimization.test_scale_v1 import bench_scenario

    bench = bench_scenario(14, 10, "pantry")
    costs = ("0.37", None, "1.25", "0")
    priced = tuple(
        r.model_copy(update={"cost_per_handling_unit_usd": costs[i % 4]})
        for i, r in enumerate(bench.routes)
    )
    heavy = tuple(
        p.model_copy(update={"handling_units_per_unit": 1 + i % 3})
        for i, p in enumerate(bench.products)
    )
    bench = bench.model_copy(update={"routes": priced, "products": heavy})
    for s in (load("pantry-four-methods")[0], bench):
        ix = pantry_index(s)
        for p in s.products:
            assert goals(s, p.id, ix) == goals(s, p.id)
            assert references(s, p.id, ix) == scanned_references(s, p.id)
            assert references(s, p.id) == scanned_references(s, p.id)


def test_default_policy_is_frozen_in_the_fixture():
    s, _ = load("pantry-four-methods")
    assert s.policy == DEFAULT_PANTRY_POLICY


def without_demand(s, *locations):
    return s.model_copy(
        update={"demand": tuple(d for d in s.demand if d.location_id not in locations)}
    )


def test_egp_singleton_group_not_optimized():
    """SPEC-V5: reject a singleton relative-priority group rather than fabricate a comparison."""
    s, _ = load("pantry-four-methods")
    s = without_demand(s, "P2", "P3")
    egp = run_method(s, "EGP_PI_INSPIRED", "UNITS")
    assert egp.verified and egp.transfers == ()
    assert [p.label for p in egp.products] == [SINGLETON_LABEL]
    assert plan_of(run_method(s, "CLASSICAL_GP", "UNITS")) == {"P1": 3}


def test_egp_requires_vulnerability_for_every_goal():
    s, _ = load("pantry-four-methods")
    s = s.model_copy(
        update={"vulnerability": tuple(v for v in s.vulnerability if v.location_id != "P3")}
    )
    egp = run_method(s, "EGP_PI_INSPIRED", "UNITS")
    assert not egp.verified and egp.failure_reason == "ATTRIBUTE_POLICY_COVERAGE:P3"
    assert run_method(s, "CLASSICAL_GP", "UNITS").verified


def test_pantry_hubs_never_receive():
    """A second hub with unmet demand and a route to it still never receives."""
    s, _ = load("pantry-four-methods")
    hub2 = s.locations[0].model_copy(update={"id": "H2", "name": "North Hub"})
    demand = s.demand[1].model_copy(update={"location_id": "H2"})
    route = s.routes[0].model_copy(update={"to_location_id": "H2"})
    s = s.model_copy(
        update={
            "locations": (*s.locations, hub2),
            "demand": (*s.demand, demand),
            "routes": (*s.routes, route),
        }
    )
    for method in PANTRY:
        result = run_method(s, method, "UNITS")
        assert result.verified
        assert all(t.to_location_id != "H2" for t in result.transfers)


def as_pantry(s, window):
    """retail-day5-expiry with both stores as pantries and a Pantry window."""
    roles = {"store": "pantry"}
    return s.model_copy(
        update={
            "mode": "PANTRY",
            "retail_weights": None,
            "planning_days": window,
            "policy": DEFAULT_PANTRY_POLICY,
            "locations": tuple(
                loc.model_copy(update={"role": roles[loc.role]}) for loc in s.locations
            ),
            "vulnerability": (),
        }
    )


def test_bd51_relaxed_retail_only():
    """README retail-day5-expiry: Retail moves 3; with a 3-day Pantry window only the day-3
    demand can use a shipped unit, so GP moves 1 and the verifier rejects a second unit."""
    s, _ = load("retail-day5-expiry")
    retail = run_method(s, "RETAIL_OPTIMIZED", "UNITS")
    assert [t.quantity for t in retail.transfers] == [3]
    pantry = as_pantry(s, 3)
    gp = run_method(pantry, "CLASSICAL_GP", "UNITS")
    (t,) = gp.transfers
    assert t.quantity == 1
    two = t.model_copy(update={"quantity": 2})
    assert "TRANSFER_NOT_CONSUMED_IN_WINDOW" in verify_plan(pantry, (two,)).violations
    assert verify_plan(s, (t.model_copy(update={"quantity": 3}),)).passed


def with_spare_pantry(s, mode):
    """P4 holds 5 spare cases and a known all-zero forecast; only HUB_AND_PANTRY may ship from
    it. (Without a demand row its demand would be unknown, and it would never send: W4-03.)"""
    p4 = s.locations[1].model_copy(update={"id": "P4", "name": "Pantry 4"})
    batch = s.batches[0].model_copy(update={"id": "p4b", "location_id": "P4", "quantity": 5})
    zero = s.demand[0].model_copy(
        update={"location_id": "P4", "central_literals": ("0",) * 7, "targets": (0,) * 7}
    )
    routes = tuple(
        s.routes[0].model_copy(update={"from_location_id": "P4", "to_location_id": p})
        for p in ("P1", "P2", "P3")
    )
    return s.model_copy(
        update={
            "transfer_mode": mode,
            "locations": (*s.locations, p4),
            "batches": (*s.batches, batch),
            "demand": (*s.demand, zero),
            "routes": (*s.routes, *routes),
        }
    )


@pytest.mark.parametrize("mode", ("HUB_ONLY", "HUB_AND_PANTRY"))
def test_pantry_five_methods_one_scenario_one_feasible_region(mode):
    s, _ = load("pantry-four-methods")
    s = with_spare_pantry(s, mode)
    result = compare_methods(
        s,
        PANTRY,
        "UNITS",
        scenario_id=UUID("00000000-0000-4000-8000-0000000000f1"),
        scenario_hash="c" * 64,
    )
    assert [m.method for m in result.methods] == list(PANTRY)
    senders = set()
    for m in result.methods:
        assert m.verified, (m.method, m.failure_reason)
        assert verify_plan(s, m.transfers).passed  # every plan is in the one raw region
        senders |= {t.from_location_id for t in m.transfers}
    if mode == "HUB_ONLY":
        assert senders <= {"H"}
    else:
        assert "P4" in senders


def test_pantry_rejects_usd():
    s, _ = load("pantry-four-methods")
    with pytest.raises(ValueError, match="MEASURE_NOT_IN_MODE"):
        run_method(s, "CLASSICAL_GP", "USD")


def with_rice(demand, capacity):
    """pantry-four-methods plus rice (G, 10 bags at the hub) with the given demand series."""
    s, _ = load("pantry-four-methods")
    series = s.demand[0]
    rice = ProductV3(
        id="G", name="Rice", unit="bag", handling_units_per_unit=1, unit_value_usd=None
    )
    stock = BatchV3(
        id="g1", location_id="H", product_id="G", quantity=10, expiry_date=None, non_expiring=True
    )
    rows = tuple(
        series.model_copy(
            update=dict(
                location_id=loc,
                product_id=pid,
                targets=targets,
                central_literals=tuple(str(x) for x in targets),
            )
        )
        for loc, pid, targets in demand
    )
    changed = s.model_copy(
        update=dict(
            products=(*s.products, rice),
            batches=(*s.batches, stock),
            demand=rows,
            capacities=(capacity,),
        )
    )
    return ORInputV3.model_validate(changed.model_dump())


def moved(result):
    assert result.verified, result.failure_reason
    out = {}
    for t in result.transfers:
        out[t.product_id] = out.get(t.product_id, 0) + t.quantity
    return out


def rice_without_pantry_goals(hub_demand):
    """Rice (G) at the hub and no pantry target for it (n = 0 goals). With hub demand, its 10 bags
    expire on day 1, so the hub runs short and G is at risk: CLASSICAL_GP solves it, EGP can't."""
    s, _ = load("pantry-four-methods")
    beans = tuple((d.location_id, d.product_id, d.targets) for d in s.demand)
    demand = (*beans, ("H", "G", (3, 3, 3, 0, 0, 0, 0))) if hub_demand else beans
    s = with_rice(demand, CapacityV3(location_id="H", receiving=None, dispatch=None, storage=None))
    if not hub_demand:
        return s
    expiring = tuple(
        b.model_copy(update={"expiry_date": s.first_planning_date, "non_expiring": False})
        if b.id == "g1"
        else b
        for b in s.batches
    )
    return ORInputV3.model_validate(s.model_copy(update={"batches": expiring}).model_dump())


@pytest.mark.parametrize("hub_demand", (False, True))
@pytest.mark.parametrize("method", PANTRY)
def test_product_without_pantry_goals_does_not_break_a_method(method, hub_demand):
    _, expected = load("pantry-four-methods")
    result = run_method(rice_without_pantry_goals(hub_demand), method, "UNITS")
    assert plan_of(result) == expected["plans"][method]
    if hub_demand and method == "CLASSICAL_GP":  # G was solved, so its objective was replayed
        assert next(p for p in result.products if p.product_id == "G").native_status == "OPTIMAL"


def test_singleton_product_keeps_the_shared_split():
    """One feasible region (V1-SPEC 6.2): rice is needed only at P1 (15 bags in the window), so
    EGP leaves it unoptimized, but its share of the hub's dispatch 4 (need 15:15, so 2 and 2)
    is still withheld from beans, exactly as for CLASSICAL_GP."""
    s, _ = load("pantry-four-methods")
    beans = tuple((d.location_id, d.product_id, d.targets) for d in s.demand)
    s = with_rice(
        (*beans, ("P1", "G", (5, 10, 0, 0, 0, 0, 0))),
        CapacityV3(location_id="H", receiving=None, dispatch=4, storage=None),
    )
    gp, egp = (run_method(s, m, "UNITS") for m in ("CLASSICAL_GP", "EGP_PI_INSPIRED"))
    assert moved(gp) == {"F": 2, "G": 2}
    assert moved(egp) == {"F": 2}
    assert next(p for p in egp.products if p.product_id == "G").label == SINGLETON_LABEL


@pytest.mark.parametrize(
    "fixture,mode", [("pantry-four-methods", "PANTRY"), ("retail-usd-flip", "RETAIL")]
)
def test_optimizers_record_the_solver_run(fixture, mode, monkeypatch):  # W2-06 (solver S2)
    """The recorded seed and workers are the ones every CP-SAT solve actually ran with."""
    seen = []
    real = cp_model.CpSolver.solve

    def spy(self, *args, **kwargs):
        seen.append((self.parameters.random_seed, self.parameters.num_workers))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(cp_model.CpSolver, "solve", spy)
    s, _ = load(fixture)
    for method in METHODS_BY_MODE[mode]:
        seen.clear()
        result = run_method(s, method, "UNITS")
        assert result.verified, (method, result.failure_reason)
        if not seen:
            assert result.solver is None, method
            continue
        run = result.solver
        assert (run.engine, run.version) == ("OR-Tools CP-SAT", ortools.__version__), method
        assert set(seen) == {(run.seed, run.workers)}, method
    assert result.solver is not None  # the fixture's last method is an optimizer that solves


def _without_price(s):
    data = s.model_dump(mode="json")
    data["products"][0]["unit_value_usd"] = None
    return ORInputV3.model_validate(data)


def _without_p3_rates(s):
    return s.model_copy(
        update={"vulnerability": tuple(v for v in s.vulnerability if v.location_id != "P3")}
    )


@pytest.mark.parametrize(
    "case",
    [
        ("retail-usd-flip", "RETAIL_OPTIMIZED", "USD", _without_price),  # USD_UNAVAILABLE
        ("pantry-four-methods", "EGP_PI_INSPIRED", "UNITS", _without_p3_rates),  # coverage
    ],
)
def test_no_solver_run_recorded_when_cp_sat_never_ran(case, monkeypatch):  # W2-06 (S2)
    fixture, method, measure, change = case
    calls = []
    real = cp_model.CpSolver.solve
    monkeypatch.setattr(
        cp_model.CpSolver, "solve", lambda self, *a, **k: calls.append(1) or real(self, *a, **k)
    )
    s, _ = load(fixture)
    result = run_method(change(s) if change else s, method, measure)
    assert calls == [] and result.solver is None


def test_no_solver_run_when_every_product_misses_the_deadline():  # W2-06 (S2) re-check
    s, _ = load("pantry-four-methods")
    result = run_method(s, "CLASSICAL_GP", "UNITS", method_seconds=0)
    assert result.failure_reason.startswith("METHOD_TIME_LIMIT") and result.solver is None


@pytest.mark.parametrize("method", ["EQUAL_SHARE", "CLASSICAL_GP"])
@pytest.mark.parametrize("solver", ["fake", None])
def test_publication_rebuilds_the_solver_run(method, solver):  # W2-06 (S2) re-check
    """A stored result can't publish provenance its own products don't imply."""
    s, _ = load("pantry-four-methods")
    result = run_method(s, method, "UNITS")
    baseline = project_v3(s).days
    assert publishable(s, baseline, result) == result
    fake = SolverRun(engine="OR-Tools CP-SAT", version="0.0-fake", seed=99, workers=64)
    claimed = fake if solver == "fake" else None
    if claimed == result.solver:
        return  # EQUAL_SHARE already has no solver run
    published = publishable(s, baseline, result.model_copy(update={"solver": claimed}))
    assert not published.verified
    assert published.failure_reason == "PUBLICATION_VERIFICATION_FAILED:solver"


def test_baseline_never_publishes_a_solver_run():  # W2-06 (S2) re-check
    """Even with a product claiming a native status, a baseline never ran CP-SAT."""
    s, _ = load("pantry-four-methods")
    result = run_method(s, "EQUAL_SHARE", "UNITS")
    products = (result.products[0].model_copy(update={"native_status": "OPTIMAL"}),)
    real = SolverRun(engine="OR-Tools CP-SAT", version=ortools.__version__, seed=0, workers=1)
    forged = result.model_copy(update={"products": products + result.products[1:], "solver": real})
    published = publishable(s, project_v3(s).days, forged)
    assert published.failure_reason == "PUBLICATION_VERIFICATION_FAILED:solver"
