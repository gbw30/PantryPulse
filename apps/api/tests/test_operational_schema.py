"""Issue #8 validation examples; not database or transaction evidence."""

from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.operational import (
    Count,
    DemandQuantities,
    ExpiryDeclaration,
    ReceiptLine,
    ReceiptRevision,
)
from app.services.inventory.contracts import local_day, require_same_organization


@pytest.mark.parametrize("value", [-1, True, False, 1.0, "1", float("nan"), 2**63])
def test_invalid_count(value):
    with pytest.raises(ValidationError):
        Count(value=value)


@pytest.mark.parametrize("value", [0, 1, 2**63 - 1])
def test_valid_count(value):
    assert Count(value=value).value == value


def test_demand_arithmetic_and_missingness():
    assert DemandQuantities(requested=60, fulfilled=45, unmet=15).requested == 60
    assert DemandQuantities(requested=None, fulfilled=45, unmet=None).requested is None
    assert DemandQuantities(requested=0, fulfilled=0, unmet=0).requested == 0


@pytest.mark.parametrize(
    "values", [(60, 45, 16), (40, 45, None), (40, None, 45), (None, None, None)]
)
def test_invalid_demand(values):
    with pytest.raises(ValidationError):
        DemandQuantities(requested=values[0], fulfilled=values[1], unmet=values[2])


def make_receipt(**changes):
    return ReceiptRevision(**({
        "organization_id": UUID(int=1), "receipt_id": UUID(int=2),
        "revision_id": UUID(int=3), "revision": 1, "source_id": UUID(int=4),
        "source_record_key": "receipt-1", "source_classification": "SIMULATED",
        "receiving_site_id": UUID(int=5), "donor_id": UUID(int=6),
        "received_at": datetime(2026, 10, 25, 2, tzinfo=UTC),
        "recorded_at": datetime(2026, 10, 25, 3, tzinfo=UTC),
        "local_day": date(2026, 10, 24), "calendar_version_id": UUID(int=7),
        "timezone": "America/New_York", "is_void": False,
        "lines": ({"line_key": "meal-1", "product_id": UUID(int=8), "quantity": 30},),
    } | changes))


def test_complete_receipt_and_immutable_lines():
    receipt = make_receipt()
    assert receipt.lines[0].quantity == 30
    assert isinstance(receipt.lines, tuple)
    with pytest.raises(ValidationError):
        receipt.lines[0].quantity = 50


@pytest.mark.parametrize("changes", [
    {"lines": ()}, {"local_day": date(2026, 10, 25)}, {"timezone": "Not/A_Zone"},
    {"is_void": "false"}, {"revision": 0}, {"revision": True},
    {"received_at": datetime(2026, 10, 25)},
])
def test_invalid_receipt(changes):
    with pytest.raises(ValidationError):
        make_receipt(**changes)


def test_duplicate_lines_and_void_receipts():
    line = ReceiptLine(line_key="same", product_id=UUID(int=8), quantity=20)
    with pytest.raises(ValidationError):
        make_receipt(lines=(line, line))
    assert make_receipt(is_void=True, lines=()).is_void
    with pytest.raises(ValidationError):
        make_receipt(is_void=True)


@pytest.mark.parametrize("kind,expiry", [
    ("DATED", None), ("UNKNOWN", date(2026, 10, 24)),
    ("NON_EXPIRING", date(2026, 10, 24)),
])
def test_contradictory_expiry(kind, expiry):
    with pytest.raises(ValidationError):
        ExpiryDeclaration(kind=kind, expires_on=expiry)


def test_expiry_day_and_non_expiring_are_distinct_from_unknown():
    item = ExpiryDeclaration(kind="DATED", expires_on=date(2026, 10, 24))
    assert item.permits_day(date(2026, 10, 24))
    assert not item.permits_day(date(2026, 10, 25))
    assert not ExpiryDeclaration(kind="UNKNOWN", expires_on=None).permits_day(date(2026, 10, 24))
    assert ExpiryDeclaration(kind="NON_EXPIRING", expires_on=None).permits_day(date(2099, 1, 1))


def test_ownership_and_local_calendar():
    require_same_organization(UUID(int=1), UUID(int=1))
    with pytest.raises(ValueError, match="organization"):
        require_same_organization(UUID(int=1), UUID(int=2))
    assert local_day(
        datetime(2026, 10, 25, 2, tzinfo=UTC), "America/New_York"
    ) == date(2026, 10, 24)
    for hour in (5, 6):
        assert local_day(
            datetime(2026, 11, 1, hour, 30, tzinfo=UTC), "America/New_York"
        ) == date(2026, 11, 1)
    with pytest.raises(ValueError):
        local_day(datetime(2026, 11, 1, 1, 30), "America/New_York")


def test_extra_fields_do_not_silently_enter_contract():
    with pytest.raises(ValidationError):
        DemandQuantities(requested=1, fulfilled=1, unmet=0, on_hand=20)
