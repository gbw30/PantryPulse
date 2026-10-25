"""Current inventory semantics, independent of forecasting and worker availability."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.repositories.inventory import build_snapshot


def lot(amount, eligibility="ELIGIBLE", kind="DATED", expiry=date(2026, 10, 24)):
    return dict(id=uuid4(), batch_key="fixture", on_hand=amount, eligibility=eligibility,
                expiry_kind=kind, expires_on=expiry, metadata_version=1)


def snapshot(lots, now=datetime(2026, 10, 25, 2, tzinfo=UTC), version=3):
    return build_snapshot(
        site=dict(id=uuid4(), name="Pantry", timezone="America/New_York"),
        product=dict(id=uuid4(), name="Meals", base_unit="meal"),
        version=version, lots=lots, now=now,
    )


def test_expiry_uses_site_day_and_is_inclusive():
    result = snapshot([lot(10)])
    assert result.local_date == date(2026, 10, 24)
    assert result.usable_quantity == 10
    next_day = snapshot([lot(10)], datetime(2026, 10, 25, 4, tzinfo=UTC))
    assert next_day.usable_quantity == 0
    assert next_day.excluded_quantities["EXPIRED"] == 10


def test_exclusion_buckets_are_disjoint_and_never_combine_units():
    result = snapshot([
        lot(10), lot(20, kind="NON_EXPIRING", expiry=None),
        lot(4, expiry=date(2026, 10, 23)),
        lot(5, "HELD", expiry=date(2026, 10, 23)),
        lot(6, "INELIGIBLE"), lot(7, "UNKNOWN"),
        lot(8, kind="UNKNOWN", expiry=None),
    ])
    assert result.on_hand_quantity == 60
    assert result.usable_quantity == 30
    assert result.excluded_quantity == 30
    assert sum(result.excluded_quantities.values()) == result.excluded_quantity
    assert result.base_unit == "meal"
    assert len(result.lots) == 7
    assert result.lots[4].exclusion_reason == "INELIGIBLE"


def test_empty_stock_does_not_fabricate_a_saved_version():
    result = snapshot([], version=None)
    assert result.inventory_version is None
    assert result.on_hand_quantity == result.usable_quantity == 0
    assert result.lots == ()


def test_quantities_are_decimal_strings_to_preserve_bigint_precision_in_browser():
    result = snapshot([lot(2**63 - 1), lot(2**63 - 1)])
    body = result.model_dump(mode="json")
    assert body["on_hand_quantity"] == str(2 * (2**63 - 1))
    assert body["lots"][0]["on_hand_quantity"] == str(2**63 - 1)
    assert body["inventory_version"] == "3"


@pytest.mark.parametrize("eligibility", ["HELD", "INELIGIBLE", "UNKNOWN"])
def test_expired_held_unknown_stock_is_counted_only_once(eligibility):
    result = snapshot([lot(9, eligibility, expiry=date(2026, 10, 23))])
    assert result.excluded_quantity == 9
    assert sum(result.excluded_quantities.values()) == 9
