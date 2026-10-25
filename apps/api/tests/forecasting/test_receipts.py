from datetime import timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.forecasting.preparation import prepare
from app.services.forecasting.schemas import HistoryBundle, SeriesKey, SeriesScope
from app.services.forecasting.service import forecast

from .conftest import AS_OF, CUTOFF, DATASET, ORG, PRODUCT, SITE, ref

DONATION = SeriesKey(organization_id=ORG, site_id=SITE, product_id=PRODUCT, target_type="DONATION")


def receipt(name, quantity, revision=1, day=CUTOFF, **kwargs):
    return {
        "source": ref(name, revision),
        "donor_id": str(UUID(int=99)),
        "receiving_site_id": str(SITE),
        "received_at": f"{day}T14:00:00Z",
        "local_day": str(day),
        "timezone": "America/New_York",
        "source_classification": "SIMULATED",
        "lines": [
            {
                "line_id": str(UUID(int=10)),
                "product_id": str(PRODUCT),
                "unit": "meal",
                "received_units": quantity,
            }
        ],
        **kwargs,
    }


def donation_bundle(receipts=(), coverage=(), **kwargs):
    return HistoryBundle(
        organization_id=ORG,
        dataset_id=DATASET,
        scope=(SeriesScope(key=DONATION, unit="meal", timezone="America/New_York"),),
        receipts=receipts,
        coverage=coverage,
        **kwargs,
    )


def test_two_events_sum_once_and_whole_receipt_revision_replaces_lines(policy):
    bundle = donation_bundle(receipts=(receipt("A", 10), receipt("A", 20, 2), receipt("B", 3)))
    frozen = prepare(bundle, data_cutoff_date=CUTOFF, snapshot_as_of=AS_OF, policy=policy)
    row = frozen.series[0].observations[-1]
    assert row.value == 23
    assert {(s.logical_key, s.revision) for s in row.sources} == {("A", 2), ("B", 1)}
    assert "INCOMPLETE_RECEIPT_COVERAGE" in row.quality_flags
    assert not forecast(frozen).ready_for_publication


def test_zero_requires_coverage_and_recorded_receipt_day_uses_site_zone(policy):
    covered = CUTOFF - timedelta(days=1)
    coverage = {
        "source": ref("coverage"),
        "key": DONATION.model_dump(mode="json"),
        "day": str(covered),
        "complete": True,
        "source_classification": "SIMULATED",
    }
    bundle = donation_bundle(
        receipts=(receipt("A", 2, day=CUTOFF - timedelta(days=2)),), coverage=(coverage,)
    )
    inputs = prepare(bundle, data_cutoff_date=CUTOFF, snapshot_as_of=AS_OF, policy=policy)
    assert [row.value for row in inputs.series[0].observations] == [2, 0, None]
    assert inputs.series[0].observations[-1].is_missing
    with pytest.raises(ValidationError, match="local day"):
        donation_bundle(receipts=(receipt("A", 2, received_at=f"{CUTOFF}T01:00:00Z"),))


def test_cross_org_unit_and_duplicate_lines_are_rejected(policy):
    with pytest.raises(ValidationError, match="Cross-organization"):
        donation_bundle(
            receipts=(receipt("A", 2, source={**ref("A"), "organization_id": UUID(int=9)}),)
        )
    bad = receipt("A", 2)
    bad["lines"][0]["unit"] = "bottle"
    with pytest.raises(ValueError, match="timezone/unit"):
        prepare(
            donation_bundle(receipts=(bad,)),
            data_cutoff_date=CUTOFF,
            snapshot_as_of=AS_OF,
            policy=policy,
        )
    duplicate = receipt("A", 2)
    duplicate["lines"] *= 2
    with pytest.raises(ValidationError, match="Duplicate receipt line"):
        donation_bundle(receipts=(duplicate,))


def test_revision_correction_moved_after_cutoff_does_not_restore_old_event(policy):
    bundle = donation_bundle(
        receipts=(receipt("A", 10), receipt("A", 20, 2, day=CUTOFF + timedelta(days=1)))
    )
    frozen = prepare(bundle, data_cutoff_date=CUTOFF, snapshot_as_of=AS_OF, policy=policy)
    assert all(row.value is None for row in frozen.series[0].observations)


def test_exact_receipt_content_changes_identity_even_with_unchanged_daily_total(policy):
    original = receipt("A", 10)
    changed = receipt("A", 10, donor_id=UUID(int=888))
    first = prepare(
        donation_bundle(receipts=(original,)),
        data_cutoff_date=CUTOFF,
        snapshot_as_of=AS_OF,
        policy=policy,
    )
    second = prepare(
        donation_bundle(receipts=(changed,)),
        data_cutoff_date=CUTOFF,
        snapshot_as_of=AS_OF,
        policy=policy,
    )
    assert first.input_hash != second.input_hash
    assert first.source_snapshot.receipts[0].donor_id != second.source_snapshot.receipts[0].donor_id
