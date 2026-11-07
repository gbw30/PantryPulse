# covers: V1-A15
"""RETAIL_OPTIMIZED against hand-derived oracle fixtures (data/demo/or-v3/README.md).

Every expected value was derived by hand before the solver existed. Expired and lost units are
read per product (never summed across products); the per-product objective is recomputed here
from the result's own effects, then compared with the hand value.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.schemas.v1_planning import ORInputV3, TransferV3

DATA = Path(__file__).resolve().parents[4] / "data/demo/or-v3"
FIXTURES = (
    "retail-expiry-transfer",
    "retail-lost-vs-waste",
    "retail-usd-flip",
    "retail-usd-no-flip",
    "retail-nothing-to-move",
    "retail-day5-expiry",
)
MEASURES = ("UNITS", "USD")
# W1-S01 commits these failing; W1-S03 removes the mark.
PENDING = pytest.mark.xfail(strict=True, raises=(NotImplementedError, ImportError))


def load(name):
    scenario = ORInputV3.model_validate_json((DATA / f"{name}.input.json").read_text())
    expected = json.loads((DATA / f"{name}.expected.json").read_text())
    return scenario, expected


def transfer_key(t):
    t = t if isinstance(t, dict) else t.model_dump(mode="json")
    return (
        t["product_id"],
        t["from_location_id"],
        t["to_location_id"],
        t["quantity"],
        str(t["ship_date"]),
        str(t["arrival_date"]),
        tuple(t["batch_ids"]),
    )


@PENDING
@pytest.mark.parametrize("measure", MEASURES)
@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_matches_oracle(name, measure):
    from app.services.optimization.methods import run_method

    scenario, expected = load(name)
    want = expected[measure]
    result = run_method(scenario, "RETAIL_OPTIMIZED", measure)

    assert result.verified and result.failure_reason is None
    assert result.native_status == "OPTIMAL"
    assert result.retail_weights.model_dump() == expected["weights"]
    prices = {p.id: Decimal(p.unit_value_usd) for p in scenario.products}
    w = expected["weights"]
    for product_id, values in want["products"].items():
        rows = [e for e in result.effects if e.product_id == product_id]
        expired = sum(e.expired_with_plan for e in rows)
        lost = sum(e.unmet_with_plan for e in rows)
        objective = w["w_exp"] * expired + w["w_lost"] * lost
        if measure == "USD":
            objective *= prices[product_id]
        assert (expired, lost) == (values["expired"], values["lost"]), product_id
        assert Decimal(objective) == Decimal(values["objective"]), product_id
    if want["objective"] is None:
        assert result.objective is None  # no units total across different products
    else:
        assert Decimal(result.objective) == Decimal(want["objective"])
    assert sorted(map(transfer_key, result.transfers)) == sorted(
        map(transfer_key, want["transfers"])
    )
    starved = [
        p.product_id
        for p in result.products
        if p.label == "capacity share too small to move one unit"
    ]
    assert starved == want["starved_products"]


@PENDING
@pytest.mark.parametrize("measure", MEASURES)
@pytest.mark.parametrize("name", FIXTURES)
def test_verifier_accepts_expected_allocations(name, measure):
    """The hand-derived plans pass the independent verifier and reproduce the hand counts."""
    from app.services.optimization.verify import verify_plan

    scenario, expected = load(name)
    want = expected[measure]
    transfers = tuple(
        TransferV3.model_validate(t | {"id": f"t{i}"}) for i, t in enumerate(want["transfers"])
    )
    report = verify_plan(scenario, transfers)
    assert report.passed, report.violations
    for product_id, values in want["products"].items():
        days = [d for d in report.days if d.product_id == product_id]
        assert sum(d.expired for d in days) == values["expired"]
        assert sum(d.unmet for d in days) == values["lost"]
