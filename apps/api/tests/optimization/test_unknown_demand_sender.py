# covers: V1-A23
"""W4-03: a location whose demand is unknown never sends that product (Gabriel, 2026-11-11).

networks/scenario.py gives a series without an available forecast no demand row (never zero).
A pantry or store without a demand row for a product has unknown need, so no method may treat
its stock as surplus, and the independent verifier rejects a plan that does (V1-SPEC §4
provenance, §6.2 BD-49 for stores, INVARIANTS INV-10). Known demand of zero (an AVAILABLE
series with zero targets) is not unknown and keeps sending its surplus.
"""

import pytest

from app.schemas.v1_planning import BatchV3
from app.services.optimization.methods import run_method
from app.services.optimization.v3 import pack
from app.services.optimization.verify import verify_plan
from tests.optimization.test_retail_oracle import load

PANTRY_METHODS = ("EQUAL_SHARE", "MOST_URGENT_FIRST", "CLASSICAL_GP", "EGP_PI_INSPIRED")
RETAIL_METHODS = ("SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED")


def pantry(p3_demand: str):
    """P3 holds 6 non-expiring cases and can reach P1 and P2; the hub holds none.

    p3_demand: "unknown" drops P3's demand row; "zero" keeps an AVAILABLE all-zero series."""
    s, _ = load("pantry-four-methods")
    p3 = next(d for d in s.demand if d.location_id == "P3")
    demand = tuple(d for d in s.demand if d.location_id != "P3")
    if p3_demand == "zero":
        demand += (p3.model_copy(update={"central_literals": ("0",) * 7, "targets": (0,) * 7}),)
    return s.model_copy(update={
        "transfer_mode": "HUB_AND_PANTRY",
        "batches": (BatchV3(id="p3", location_id="P3", product_id="F", quantity=6,
                            expiry_date=None, non_expiring=True),),
        "demand": demand,
        "routes": s.routes + tuple(
            s.routes[0].model_copy(update={"from_location_id": "P3", "to_location_id": to})
            for to in ("P1", "P2")),
    })


def retail(a_demand: str):
    """Store A holds 10 expiring + 10 non-expiring cases and can reach store B."""
    s, _ = load("retail-expiry-transfer")
    a = next(d for d in s.demand if d.location_id == "A")
    demand = tuple(d for d in s.demand if d.location_id != "A")
    if a_demand == "zero":
        demand += (a.model_copy(update={"central_literals": ("0",) * 7, "targets": (0,) * 7}),)
    return s.model_copy(update={"demand": demand})


def sent_from(result, location):
    return sum(t.quantity for t in result.transfers if t.from_location_id == location)


@pytest.mark.parametrize("method", PANTRY_METHODS)
def test_pantry_with_unknown_demand_sends_nothing(method):
    s = pantry("unknown")
    assert ("P3", "F") not in {(d.location_id, d.product_id) for d in s.demand}
    result = run_method(s, method, "UNITS")
    assert result.verified, result.failure_reason
    assert sent_from(result, "P3") == 0


@pytest.mark.parametrize("method", RETAIL_METHODS)
def test_store_with_unknown_sales_sends_nothing(method):
    s = retail("unknown")
    assert "A" not in {d.location_id for d in s.demand}
    result = run_method(s, method, "UNITS")
    assert result.verified, result.failure_reason
    assert sent_from(result, "A") == 0


@pytest.mark.parametrize(("scenario", "key"), [
    (pantry("unknown"), ("F", "P3", "P2")),
    (retail("unknown"), ("P", "A", "B")),
])
def test_verifier_rejects_a_transfer_out_of_unknown_demand(scenario, key):
    """A hand-packed plan, never built from any method's sender filter."""
    transfers = [p.transfer for p in pack(scenario, {key: 3})]
    report = verify_plan(scenario, transfers)
    assert not report.passed
    assert "UNKNOWN_DEMAND_SENDER" in report.violations


@pytest.mark.parametrize(("scenario", "key"), [
    (pantry("zero"), ("F", "P3", "P2")),
    (retail("zero"), ("P", "A", "B")),
])
def test_verifier_accepts_the_same_transfer_with_known_zero_demand(scenario, key):
    transfers = [p.transfer for p in pack(scenario, {key: 3})]
    report = verify_plan(scenario, transfers)
    assert report.passed, report.violations


@pytest.mark.parametrize("method", PANTRY_METHODS)
def test_pantry_with_known_zero_demand_still_sends_its_stock(method):
    """Pin: an AVAILABLE all-zero series is known demand, so P3's 6 cases are surplus."""
    result = run_method(pantry("zero"), method, "UNITS")
    assert result.verified, result.failure_reason
    assert sent_from(result, "P3") == 6


@pytest.mark.parametrize("method", RETAIL_METHODS)
def test_store_with_known_zero_sales_still_sends(method):
    result = run_method(retail("zero"), method, "UNITS")
    assert result.verified, result.failure_reason
    assert sent_from(result, "A") > 0
