"""W5-L01 contract carry-ins: scenario donations, danger/projection basis, not-evaluated scores.

Schema-only: the fields are filled by lane w5-data (D01-D03). Defaults must keep every
existing producer and stored scenario valid, and an empty `donations` keeps the hash.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.v1_networks import (
    BacktestScore,
    DangerRow,
    LocationBacktest,
    ProductProjection,
)
from app.schemas.v1_planning import ORInputV3
from app.services.optimization.canonical import operational_hash
from tests.test_v1_contract import ROWS, _scenario

MINI = Path(__file__).parent / "networks" / "fixtures" / "mini-network"
DONATION = {"location_id": "P1", "product_id": "SKU0", "actual_provider": "SEASONAL_NAIVE",
            "fallback_reason": None, "central_literals": ["1.50", "0", "2", "0", "0", "3", "1"]}


def _with(*donations):
    return _scenario(2, 1, **ROWS, donations=list(donations))


# --- donations on or-input-v3 ---------------------------------------------------------------

def test_donations_default_to_empty_and_stay_out_of_the_canonical_form():
    payload = _scenario(2, 1, **ROWS)  # one payload: _scenario draws fresh ids per call
    bare = ORInputV3.model_validate(payload)
    explicit = ORInputV3.model_validate({**payload, "donations": []})
    assert bare.donations == explicit.donations == ()
    assert "donations" not in bare.model_dump(mode="json")
    assert "donations" not in bare.model_dump(mode="python")
    assert operational_hash(bare) == operational_hash(explicit)


@pytest.mark.parametrize("mode", ["validation", "serialization"])
def test_published_schema_does_not_promise_donations(mode):
    # The API omits empty donations, so a client type must treat the field as optional.
    schema = ORInputV3.model_json_schema(mode=mode)
    assert "donations" not in schema.get("required", [])
    assert "default" not in schema["properties"]["donations"]


def test_stored_mini_network_scenario_keeps_its_golden_hash():
    # The golden as frozen before W5-L01; W5-D01 regenerated expected-scenario.json with donations.
    stored = json.loads((MINI / "expected-scenario-pre-w5.json").read_text())
    assert "donations" not in stored  # frozen before W5-L01
    scenario = ORInputV3.model_validate(stored)
    assert scenario.model_dump(mode="json") == stored
    assert operational_hash(scenario) == (MINI / "expected-hash-pre-w5.txt").read_text().strip()


def test_a_donation_row_is_frozen_and_hashed():
    payload = _with(DONATION)
    with_row = ORInputV3.model_validate(payload)
    row = with_row.donations[0]
    assert row.central_literals == ("1.5", "0", "2", "0", "0", "3", "1")  # exact, normalized
    assert with_row.model_dump(mode="json")["donations"][0]["location_id"] == "P1"
    without = ORInputV3.model_validate({**payload, "donations": []})
    assert operational_hash(with_row) != operational_hash(without)
    again = ORInputV3.model_validate(with_row.model_dump(mode="json"))
    assert operational_hash(again) == operational_hash(with_row)


def test_donations_are_described_as_display_only():
    text = ORInputV3.model_fields["donations"].description or ""
    assert "never supply" in text and "not confirmed" in text


@pytest.mark.parametrize("provider", [None, ""])
def test_donation_requires_a_provider(provider):
    row = {**DONATION, "actual_provider": provider}
    with pytest.raises(ValidationError, match=r"donations\.0\.actual_provider"):
        ORInputV3.model_validate(_with(row))
    missing = {k: v for k, v in DONATION.items() if k != "actual_provider"}
    with pytest.raises(ValidationError, match=r"donations\.0\.actual_provider"):
        ORInputV3.model_validate(_with(missing))


def test_donation_fallback_needs_a_reason():
    ORInputV3.model_validate(_with({**DONATION, "actual_provider": "MOVING_AVERAGE",
                                    "fallback_reason": "seasonal-naive history too short"}))
    with pytest.raises(ValidationError, match=r"donations\.0\.fallback_reason"):
        ORInputV3.model_validate(_with({**DONATION, "fallback_reason": ""}))


@pytest.mark.parametrize("points", [6, 8])
def test_donation_needs_exactly_seven_points(points):
    with pytest.raises(ValidationError, match=r"donations\.0\.central_literals"):
        ORInputV3.model_validate(_with({**DONATION, "central_literals": ["1"] * points}))


@pytest.mark.parametrize("literal", ["-1", "abc"])
def test_donation_points_are_nonnegative_decimal_literals(literal):
    with pytest.raises(ValidationError, match=r"donations\.0\.central_literals"):
        ORInputV3.model_validate(
            _with({**DONATION, "central_literals": [literal] + ["1"] * 6}))


def test_donation_rejects_a_duplicate_location_and_product():
    with pytest.raises(ValidationError, match="DUPLICATE_ROW"):
        ORInputV3.model_validate(_with(DONATION, {**DONATION, "actual_provider": "OTHER"}))


@pytest.mark.parametrize("field", ["location_id", "product_id"])
def test_donation_rejects_an_unknown_reference(field):
    with pytest.raises(ValidationError, match="UNKNOWN_REFERENCE"):
        ORInputV3.model_validate(_with({**DONATION, field: "NOPE"}))


# --- basis on danger rows and projections ---------------------------------------------------

DANGER = dict(location_id="P1", rank=1, score_ratio=Decimal("0.5"), band="high",
              reason="unmet", driving_product_id="SKU0", driving_units=3, unit="case",
              first_deficit_date=None)
PROJECTION = dict(product_id="SKU0", unit="case", dates=(date(2026, 11, 6),), target=(1,),
                  served=(1,), unmet=(0,), eligible_stock_now=1, expiring_unsold=None,
                  donation_forecast=None)


@pytest.mark.parametrize("model, fields", [(DangerRow, DANGER), (ProductProjection, PROJECTION)])
def test_basis_defaults_to_unknown_and_uses_the_demand_vocabulary(model, fields):
    assert model(**fields).basis is None  # existing producers stay valid; hubs stay None
    for basis in ("demand", "sales"):
        assert model(**fields, basis=basis).basis == basis
    with pytest.raises(ValidationError, match="literal_error"):
        model(**fields, basis="requested")


# --- not-evaluated backtest scores ----------------------------------------------------------

SCORE = dict(origins_evaluated=4, wape_pct=None, bias_pct=None, scored_points=28)


def test_existing_backtest_statuses_stay_valid():
    BacktestScore(**SCORE, status="evaluated")  # a null WAPE was legal before W5-L01
    BacktestScore(origins_evaluated=0, wape_pct=None, bias_pct=None, scored_points=0,
                  status="not_evaluated_insufficient_history")
    assert BacktestScore(**{**SCORE, "wape_pct": Decimal("12.5")},
                         status="evaluated").reason is None


def test_zero_actual_score_is_not_evaluated_with_a_machine_reason():
    score = BacktestScore(**SCORE, status="not_evaluated_zero_actual",
                          reason="sum_actual_zero")
    assert (score.status, score.reason) == ("not_evaluated_zero_actual", "sum_actual_zero")
    row = LocationBacktest(location_id="P1", unit="case", series_count=2, score=score)
    assert row.model_dump(mode="json")["score"]["reason"] == "sum_actual_zero"


def test_not_evaluated_score_has_no_metrics():
    with pytest.raises(ValidationError, match="NOT_EVALUATED_HAS_NO_METRICS"):
        BacktestScore(**{**SCORE, "wape_pct": Decimal("1")}, status="not_evaluated_zero_actual",
                      reason="sum_actual_zero")


def test_evaluated_score_has_no_reason():
    with pytest.raises(ValidationError, match="REASON_ONLY_WHEN_NOT_EVALUATED"):
        BacktestScore(**SCORE, status="evaluated", reason="sum_actual_zero")


def test_not_evaluated_reason_is_a_machine_code():
    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        BacktestScore(**SCORE, status="not_evaluated_zero_actual", reason="Sum is zero!")
