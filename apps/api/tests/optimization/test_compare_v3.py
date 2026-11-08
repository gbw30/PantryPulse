# covers: V1-A14, V1-A15, V1-A22
"""or-comparison.v3: N methods on one frozen scenario; only verified results carry a plan."""

from pathlib import Path
from uuid import UUID

import pytest
from ortools.sat.python import cp_model

from app.schemas.or_inputs import ORScenarioPayload
from app.services.optimization import compare as compare_module
from app.services.optimization.compare import compare, compare_methods
from app.services.optimization.verify import verify_plan
from tests.optimization.test_retail_oracle import load

SCENARIO_ID = UUID("00000000-0000-4000-8000-0000000000c1")
HASH = "a" * 64
RETAIL = ("NO_TRANSFERS", "SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED")


def run(name, measure, methods=RETAIL):
    s, expected = load(name)
    result = compare_methods(s, methods, measure, scenario_id=SCENARIO_ID, scenario_hash=HASH)
    return s, expected, result


def plan_of(method_result):
    return sorted(
        (t.product_id, t.from_location_id, t.to_location_id, t.quantity)
        for t in method_result.transfers
    )


@pytest.mark.parametrize("measure", ("UNITS", "USD"))
def test_retail_three_methods_units_and_usd(measure):
    s, expected, result = run("retail-usd-flip", measure)
    assert (result.scenario_id, result.scenario_hash, result.mode, result.measure) == (
        SCENARIO_ID,
        HASH,
        "RETAIL",
        measure,
    )
    assert tuple(m.method for m in result.methods) == RETAIL
    assert all(m.verified and m.measure == measure for m in result.methods)
    optimized = result.methods[2]
    assert plan_of(optimized) == sorted(
        (t["product_id"], t["from_location_id"], t["to_location_id"], t["quantity"])
        for t in expected[measure]["transfers"]
    )


@pytest.mark.parametrize("name", ("retail-expiry-transfer", "retail-lost-vs-waste"))
def test_every_published_result_verified(name):
    s, _, result = run(name, "UNITS")
    published = [m for m in result.methods if m.transfers]
    assert published  # the fixture makes at least one method move stock
    for m in result.methods:
        assert m.verified
        assert verify_plan(s, m.transfers).passed


def test_failed_method_reported_others_still_published(monkeypatch):
    monkeypatch.setattr(cp_model.CpSolver, "status_name", lambda self, status=None: "UNKNOWN")
    _, _, result = run("retail-expiry-transfer", "UNITS")
    none, soonest, optimized = result.methods
    assert (optimized.native_status, optimized.verified, optimized.transfers) == (
        "UNKNOWN",
        False,
        (),
    )
    assert optimized.failure_reason == "NO_SOLUTION:P"
    assert none.verified and soonest.verified and soonest.transfers


def test_unverified_result_never_published(monkeypatch):
    """A method that claims verification for an infeasible plan is published without it."""
    real = compare_module.run_method

    def forged(scenario, method, measure, **kwargs):
        result = real(scenario, method, measure, **kwargs)
        if method != "RETAIL_OPTIMIZED":
            return result
        (t,) = result.transfers  # README: 6 units; a 7th a1 unit can't sell before expiry
        return result.model_copy(update={"transfers": (t.model_copy(update={"quantity": 7}),)})

    monkeypatch.setattr(compare_module, "run_method", forged)
    s, _, result = run("retail-expiry-transfer", "UNITS")
    optimized = result.methods[2]
    assert (optimized.verified, optimized.transfers, optimized.effects) == (False, (), ())
    assert optimized.failure_reason.startswith("PUBLICATION_VERIFICATION_FAILED:")
    assert "TRANSFER_NOT_CONSUMED_IN_WINDOW" in optimized.failure_reason
    assert result.methods[1].verified  # the other methods still publish


def test_method_error_reported_others_still_published(monkeypatch):
    real = compare_module.run_method

    def broken(scenario, method, measure, **kwargs):
        if method == "SOONEST_EXPIRY_FIRST":
            raise RuntimeError("boom")
        return real(scenario, method, measure, **kwargs)

    monkeypatch.setattr(compare_module, "run_method", broken)
    _, _, result = run("retail-expiry-transfer", "UNITS")
    soonest = result.methods[1]
    assert (soonest.verified, soonest.failure_reason) == (False, "METHOD_ERROR:RuntimeError")
    assert result.methods[2].verified and result.methods[2].transfers


def test_methods_must_belong_to_the_scenario_mode():
    from app.services.jobs.registry import InputRejected

    with pytest.raises(InputRejected):
        run("retail-expiry-transfer", "UNITS", ("NO_TRANSFERS", "EQUAL_SHARE"))


def test_v2_paired_comparison_unchanged():
    """V1-A22: or-comparison.v2 still pairs CLASSICAL_GP and EGP_PI_INSPIRED on or-input-v2."""
    data = Path(__file__).resolve().parents[4] / "data/demo/or-v2"
    scenario = ORScenarioPayload.model_validate_json(
        (data / "six-beneficiary-v2.snapshot.json").read_text()
    )
    result = compare(scenario)
    assert tuple(str(m.method) for m in result.methods) == ("CLASSICAL_GP", "EGP_PI_INSPIRED")
    assert result.outcome == "SUCCEEDED"
    assert all(m.outcome == "VERIFIED" for m in result.methods)
