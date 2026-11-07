# covers: V1-A14
"""Pantry methods on or-input-v3: hand values, an enumeration oracle independent of CP-SAT, the
EGP group/coverage rules, hubs never receiving, BD-51 and both transfer modes (W1-S02..S04).

Hand values come from data/demo/or-v3/README.md (pantry-four-methods).
"""

import itertools
from decimal import Decimal
from fractions import Fraction
from uuid import UUID

import pytest

from app.schemas.v1_planning import DEFAULT_PANTRY_POLICY, METHODS_BY_MODE
from app.services.optimization.compare import compare_methods
from app.services.optimization.methods import PER_PRODUCT_LABEL, run_method
from app.services.optimization.pantry import (
    SINGLETON_LABEL,
    coefficients,
    goals,
    pantry_objectives,
    solve_pantry_product,
)
from app.services.optimization.product_model import Shares
from app.services.optimization.projection import project_v3
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
    """P4 holds 5 spare cases and has no demand; only HUB_AND_PANTRY may ship from it."""
    p4 = s.locations[1].model_copy(update={"id": "P4", "name": "Pantry 4"})
    batch = s.batches[0].model_copy(update={"id": "p4b", "location_id": "P4", "quantity": 5})
    routes = tuple(
        s.routes[0].model_copy(update={"from_location_id": "P4", "to_location_id": p})
        for p in ("P1", "P2", "P3")
    )
    return s.model_copy(
        update={
            "transfer_mode": mode,
            "locations": (*s.locations, p4),
            "batches": (*s.batches, batch),
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
