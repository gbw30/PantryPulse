"""Public mutation contracts preserve exact integer input and trusted actor boundaries."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.inventory_api import StockAdjustmentRequest


def payload(**changes):
    return dict(expected_inventory_version="7", reason="Physical count correction",
                source_reference="count-note-001",
                changes=[dict(lot_id=str(uuid4()), delta="-5")]) | changes


def test_valid_decimal_strings_preserve_signed_bigint_precision():
    value = StockAdjustmentRequest.model_validate(payload(
        expected_inventory_version=str(2**63 - 1),
        changes=[dict(lot_id=str(uuid4()), delta=str(-(2**63 - 1)))],
    ))
    assert value.expected_inventory_version == str(2**63 - 1)
    assert value.changes[0].delta == str(-(2**63 - 1))


@pytest.mark.parametrize("delta", ["0", "-0", "01", "+1", "1.5", " 1", 1, True,
                                   str(2**63), str(-(2**63))])
def test_invalid_deltas_rejected(delta):
    with pytest.raises(ValidationError):
        StockAdjustmentRequest.model_validate(payload(changes=[dict(lot_id=uuid4(), delta=delta)]))


@pytest.mark.parametrize("version", ["0", "01", "-1", 7, True, str(2**63)])
def test_invalid_versions_rejected(version):
    with pytest.raises(ValidationError):
        StockAdjustmentRequest.model_validate(payload(expected_inventory_version=version))


@pytest.mark.parametrize("changes", [{"reason": "  "}, {"source_reference": "\t"},
                                      {"organization_id": str(uuid4())}, {"actor": "admin"},
                                      {"changes": []}, {"reason": "a" * 1001}])
def test_request_is_bounded_attributed_and_cannot_select_actor(changes):
    with pytest.raises(ValidationError):
        StockAdjustmentRequest.model_validate(payload(**changes))


def test_duplicate_lots_and_oversized_commands_rejected():
    change = dict(lot_id=uuid4(), delta="1")
    with pytest.raises(ValidationError):
        StockAdjustmentRequest.model_validate(payload(changes=[change, change]))
    with pytest.raises(ValidationError):
        StockAdjustmentRequest.model_validate(payload(
            changes=[dict(lot_id=uuid4(), delta="1") for _ in range(101)],
        ))
