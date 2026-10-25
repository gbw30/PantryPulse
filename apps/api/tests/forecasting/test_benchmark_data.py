"""Independent source-semantics, temporal isolation and frozen-artifact regressions."""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app.services.forecasting.benchmark_data import (
    AVAILABILITY,
    TRANSFORM_VERSION,
    BenchmarkFold,
    BenchmarkObservation,
    BenchmarkWindow,
    canonical_hash,
    file_sha256,
    load_dataset,
    materialize_series,
    read_manifest,
    select_cohort,
)
from scripts.forecasting_data import load_final_holdout

D = date(2024, 3, 28)


def row(day, value=2.5, **changes):
    return {
        "store_id": 3,
        "product_id": 17,
        "dt": day.isoformat(),
        "sale_amount": value,
        "stock_hour6_22_cnt": 0,
        "hours_stock_status": [0] * 24,
        **changes,
    }


def series(length=90):
    return materialize_series(
        [row(D + timedelta(days=i), value=float(i % 4)) for i in range(length)],
        start=D,
        end=D + timedelta(days=length - 1),
    )[0]


def test_missing_source_day_is_null_while_observed_zero_remains_zero():
    actual = materialize_series(
        [row(D, 0), row(D + timedelta(days=2), None)], start=D, end=D + timedelta(days=2)
    )[0]
    assert [(r.value, r.source_present, r.censored) for r in actual.observations] == [
        (0, True, False),
        (None, False, None),
        (None, True, False),
    ]
    with pytest.raises(FrozenInstanceError):
        actual.observations[0].value = 90


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), "0", True])
def test_bad_observed_values_are_rejected_without_coercion(value):
    with pytest.raises(ValueError, match="finite"):
        BenchmarkObservation(D, value)


def test_stockout_status_preserves_daytime_count_and_raw_nightly_flags():
    flags = (1,) * 6 + (0,) * 16 + (1,) * 2
    actual = BenchmarkObservation(D, 0, 0, flags)
    assert actual.censored is False
    assert actual.hourly_stockout_status == flags
    assert BenchmarkObservation(D, 0, 2, flags).censored is True
    assert BenchmarkObservation(D, None).censored is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"stockout_hours": -1},
        {"stockout_hours": 18},
        {"stockout_hours": True},
        {"hourly_stockout_status": (0,) * 23},
        {"hourly_stockout_status": (0,) * 23 + (2,)},
        {"hourly_stockout_status": (False,) * 24},
        {"source_present": False, "value": 0},
    ],
)
def test_invalid_masks_and_absent_row_claims_fail(kwargs):
    values = {"value": None, **kwargs}
    with pytest.raises(ValueError):
        BenchmarkObservation(D, **values)


def test_duplicate_and_out_of_split_dates_fail_instead_of_being_aggregated():
    with pytest.raises(ValueError, match="Duplicate"):
        materialize_series([row(D), row(D)], start=D, end=D)
    with pytest.raises(ValueError, match="outside"):
        materialize_series([row(D + timedelta(days=1))], start=D, end=D)


def test_source_ids_cannot_be_bool_and_dates_cannot_be_datetime():
    with pytest.raises(TypeError):
        materialize_series([row(D, store_id=True)], start=D, end=D)
    with pytest.raises(TypeError):
        BenchmarkObservation(datetime(2024, 3, 28), 2)


def test_target_unit_and_identity_cannot_be_relabelled_as_pantry_need():
    original = series(3)
    for changes in [{"unit": "meal"}, {"target_basis": "REQUESTED"}, {"series_id": "pantry:3"}]:
        with pytest.raises(ValueError):
            replace(original, **changes)


def test_series_calendar_is_ordered_unique_and_gap_explicit():
    original = series(3)
    for observations in [
        original.observations[::-1],
        (original.observations[0],) * 2,
        (original.observations[0], original.observations[2]),
    ]:
        with pytest.raises(ValueError, match="gap-explicit"):
            replace(original, observations=observations)


def test_cohort_selection_uses_only_ids_and_is_stable_under_source_order():
    keys = [(3, 17), (3, 18), (8, 99), (9, 4)]
    assert select_cohort(keys, 2) == select_cohort(keys[::-1], 2)
    assert select_cohort(keys, 2) == ("store:3/product:17", "store:9/product:4")
    with pytest.raises(ValueError):
        select_cohort(keys + [keys[0]], 2)
    with pytest.raises(ValueError):
        select_cohort(keys, 5)


def test_changing_future_values_or_masks_cannot_change_origin_input():
    original = series(90)
    cutoff = D + timedelta(days=61)
    future_changed = replace(
        original,
        observations=tuple(
            replace(observation, value=999_999, stockout_hours=17)
            if observation.day > cutoff
            else observation
            for observation in original.observations
        ),
    )
    before, after = original.at_origin(cutoff), future_changed.at_origin(cutoff)
    assert len(before.observations) == 62
    assert before == after
    assert before.input_hash == after.input_hash
    assert before.availability_semantics == AVAILABILITY
    changed_past = replace(
        original,
        observations=(replace(original.observations[0], value=500), *original.observations[1:]),
    )
    assert changed_past.at_origin(cutoff).input_hash != before.input_hash
    with pytest.raises(ValueError, match="future"):
        BenchmarkWindow(original.series_id, cutoff, original.observations)


def test_folds_require_seven_future_dates_and_cannot_overlap_final_truth():
    valid = BenchmarkFold("v", D, tuple(D + timedelta(days=i) for i in range(1, 8)))
    assert valid.truth_dates[-1] == date(2024, 4, 4)
    with pytest.raises(ValueError):
        replace(valid, truth_dates=valid.truth_dates[:-1])


def make_manifest(tmp_path: Path) -> Path:
    original = series(90)
    artifact = tmp_path / "pilot-training.json"
    artifact.write_text(json.dumps({"series": [original.as_dict()]}))
    cutoff = D + timedelta(days=89)
    manifest = {
        "transform_version": TRANSFORM_VERSION,
        "source_id": "Dingdong-Inc/FreshRetailNet-50K",
        "source_revision": "c" * 40,
        "series_ids": [original.series_id],
        "cohort_hash": canonical_hash([original.series_id]),
        "training_artifact": {"filename": artifact.name, "sha256": file_sha256(artifact)},
        "validation_folds": [
            BenchmarkFold(
                "validation",
                D + timedelta(days=61),
                tuple(D + timedelta(days=i) for i in range(62, 69)),
            ).as_dict()
        ],
        "final_fold": BenchmarkFold(
            "final",
            cutoff,
            tuple(cutoff + timedelta(days=i) for i in range(1, 8)),
            "final_holdout",
        ).as_dict(),
        "raw_files": {"train.parquet": {"sha256": "a" * 64}, "eval.parquet": {"sha256": "b" * 64}},
        "final_holdout_values_included": False,
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def test_manifest_and_training_content_are_verified_and_final_truth_is_excluded(tmp_path):
    path = make_manifest(tmp_path)
    dataset = load_dataset(path)
    assert len(dataset.series) == 1
    assert len(dataset.series[0].observations) == 90
    assert dataset.final_fold.truth_dates[0] > dataset.series[0].observations[-1].day
    artifact = tmp_path / "pilot-training.json"
    artifact.write_text(artifact.read_text().replace('"value": 0.0', '"value": 3.0', 1))
    with pytest.raises(ValueError, match="artifact checksum"):
        load_dataset(path)


def test_changed_manifest_or_cohort_fails_before_loading(tmp_path):
    path = make_manifest(tmp_path)
    manifest = json.loads(path.read_text())
    manifest["series_ids"] = ["store:999/product:999"]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest checksum"):
        read_manifest(path)
    manifest["manifest_hash"] = canonical_hash(
        {k: v for k, v in manifest.items() if k != "manifest_hash"}
    )
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Cohort"):
        read_manifest(path)


def test_holdout_open_requires_explicit_opt_in_before_any_file_access(tmp_path):
    with pytest.raises(PermissionError, match="sealed"):
        load_final_holdout(tmp_path / "does-not-exist.json", tmp_path)


def test_dataset_rejects_truth_in_ordinary_series_and_duplicate_scope(tmp_path):
    dataset = load_dataset(make_manifest(tmp_path))
    with pytest.raises(ValueError, match="Duplicate"):
        replace(dataset, series=(dataset.series[0], dataset.series[0]))
    with pytest.raises(ValueError, match="final truth"):
        replace(dataset, series=(series(97),))
    with pytest.raises(ValueError, match="before final"):
        replace(
            dataset,
            validation_folds=(
                BenchmarkFold(
                    "bad",
                    D + timedelta(days=84),
                    tuple(D + timedelta(days=i) for i in range(85, 92)),
                ),
            ),
        )
