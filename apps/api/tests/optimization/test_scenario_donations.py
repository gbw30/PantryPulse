# covers: V1-A16, V1-A23
"""W5-D01: a frozen scenario's donation forecasts in the why text and in per-product cuts.

Donations are display only (V1-SPEC §6.1): each action's why names the receiver's expected
donations over the same days as its projected unmet, or says it has no donation forecast. They
never change a plan, a projection or a verification. Hand values: data/demo/or-v3/README.md.
"""

from uuid import UUID

import pytest

from app.schemas.v1_planning import ORInputV3
from app.services.optimization.actions import _Plan, decision_actions
from app.services.optimization.methods import run_method
from app.services.optimization.verify import only_product
from tests.optimization.test_retail_oracle import load
from tests.optimization.test_scale_v1 import bench_scenario

COMPARISON = UUID("00000000-0000-4000-8000-0000000000d2")


def donation(location, product, *central, provider="SEASONAL_NAIVE", fallback=None):
    return {"location_id": location, "product_id": product, "actual_provider": provider,
            "fallback_reason": fallback, "central_literals": list(central)}


def with_donations(s: ORInputV3, *rows) -> ORInputV3:
    return ORInputV3.model_validate({**s.model_dump(mode="json"), "donations": list(rows)})


def test_why_text_lists_expected_donations():
    """EGP ships 2 cases to P1 and 2 to P2 over a 2-day window (README). P1's donations over
    those 2 days are 1.5 + 0 (days 3-7 are outside the window); P2 has no donation forecast."""
    s = with_donations(load("pantry-four-methods")[0],
                       donation("P1", "F", "1.5", "0", "4", "4", "4", "4", "4"))
    result = run_method(s, "EGP_PI_INSPIRED", "UNITS")
    plain = run_method(load("pantry-four-methods")[0], "EGP_PI_INSPIRED", "UNITS")
    assert result.transfers == plain.transfers  # never supply: the plan is unchanged
    why = {a.action_text.split(" to ")[1].split(",")[0]: a.why_text
           for a in decision_actions(s, result, comparison_id=COMPARISON).actions}
    assert why["Pantry 1"] == (
        "Pantry 1 runs out on Nov 3 (projected unmet 3 cases over 2 days); "
        "Central Hub has 4 cases beyond its protected need. "
        "At Pantry 1, expected donations (forecast, not confirmed): 1.5 cases over 2 days, "
        "not counted as supply. "
        "One more unit is infeasible: the sender has no more eligible stock."
    )
    assert "Pantry 2 has no donation forecast." in why["Pantry 2"]
    assert "expected donations" not in why["Pantry 2"]


def test_retail_why_counts_donations_over_the_seven_day_horizon():
    s = with_donations(load("retail-expiry-transfer")[0],
                       donation("B", "P", "1", "0", "0", "0", "0", "0", "0.25"),
                       donation("A", "P", "9", "9", "9", "9", "9", "9", "9"))  # sender: not named
    (action,) = decision_actions(s, run_method(s, "RETAIL_OPTIMIZED", "UNITS"),
                                 comparison_id=COMPARISON).actions
    assert ("At Store B, expected donations (forecast, not confirmed): 1.25 cases over 7 days, "
            "not counted as supply.") in action.why_text
    assert action.why_text.count("expected donations") == 1


def test_one_unit_of_donations_is_singular():
    s = with_donations(load("retail-expiry-transfer")[0],
                       donation("B", "P", "1", "0", "0", "0", "0", "0", "0"))
    (action,) = decision_actions(s, run_method(s, "RETAIL_OPTIMIZED", "UNITS"),
                                 comparison_id=COMPARISON).actions
    assert "(forecast, not confirmed): 1 case over 7 days" in action.why_text


@pytest.mark.parametrize("method", ["EQUAL_SHARE", "CLASSICAL_GP"])
def test_per_product_scenario_keeps_only_its_donations(method):
    s = bench_scenario(14, 10, "pantry")
    receivers = [loc.id for loc in s.locations if loc.role == "pantry"][:2]
    rows = [donation(loc, p.id, *["2"] * 7) for loc in receivers for p in s.products]
    s = with_donations(s, *rows)
    for p in s.products:
        for sub in (only_product(s, p.id), only_product(s, p.id, set(receivers[:1]))):
            again = ORInputV3.model_validate(sub.model_dump(mode="json"))  # no UNKNOWN_REFERENCE
            assert {d.product_id for d in again.donations} == {p.id}
    result = run_method(s, method, "UNITS")
    assert result.verified and result.transfers, result.failure_reason
    plan = _Plan.of(s, result)
    for p in {t.product_id for t in result.transfers}:
        sub = ORInputV3.model_validate(plan.sub(p).model_dump(mode="json"))
        assert [(d.location_id, d.product_id) for d in sub.donations] == [
            (loc, p) for loc in receivers]
    assert decision_actions(s, result, comparison_id=COMPARISON).actions
