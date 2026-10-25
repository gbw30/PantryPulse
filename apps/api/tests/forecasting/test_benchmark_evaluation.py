"""Hand arithmetic, all-population accounting and temporal/holdout isolation."""

import builtins
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.services.forecasting.adapters.base import ProviderError
from app.services.forecasting.adapters.moving_average import MovingAverageAdapter
from app.services.forecasting.adapters.seasonal_naive import SeasonalNaiveAdapter
from app.services.forecasting.benchmark_data import (
    BenchmarkDataset,
    BenchmarkFold,
    BenchmarkObservation,
    BenchmarkSeries,
    series_id,
)
from app.services.forecasting.benchmark_evaluation import (
    BenchmarkProvider,
    baseline_providers,
    evaluate_benchmark,
    paired_metrics,
    qualification_decision,
    series_cluster_comparison,
    summarize_records,
)
from app.services.forecasting.schemas import ForecastPoint, ProviderIdentity
from scripts import evaluate_retail_forecasting as cli
from scripts.evaluate_retail_forecasting import run_final_holdout

D = date(2024, 3, 28)


def dataset(count=2, value=2.0):
    series = tuple(
        BenchmarkSeries(
            series_id(store, 17),
            store,
            17,
            tuple(BenchmarkObservation(D + timedelta(days=i), value, i % 2) for i in range(90)),
        )
        for store in range(count)
    )
    folds = tuple(
        BenchmarkFold(
            f"validation-{offset}",
            D + timedelta(days=offset - 1),
            tuple(D + timedelta(days=offset - 1 + i) for i in range(1, 8)),
        )
        for offset in (62, 69, 76, 83)
    )
    return BenchmarkDataset(
        "synthetic-retail-test",
        "c" * 40,
        series,
        folds,
        BenchmarkFold(
            "final",
            D + timedelta(days=89),
            tuple(D + timedelta(days=i) for i in range(90, 97)),
            "final_holdout",
        ),
        "a" * 64,
        "b" * 64,
        "d" * 64,
        "e" * 64,
    )


def provider(name, value=1.0, *, fail_store=None, bug=False, quantiles=False, wrong_dates=False):
    def predict(window):
        if bug:
            raise ValueError("programming defect")
        if fail_store is not None and window.series_id.startswith(f"store:{fail_store}/"):
            raise ProviderError("INSUFFICIENT_DATA", "declared test failure")
        return tuple(
            ForecastPoint(
                day=window.cutoff + timedelta(days=(1 if wrong_dates else offset)),
                central_estimate=value,
                estimate_kind="MEDIAN" if quantiles else "POINT",
                p10=0 if quantiles else None,
                p50=value if quantiles else None,
                p90=4 if quantiles else None,
                interval_method="MODEL_QUANTILES" if quantiles else "NONE",
            )
            for offset in range(1, 8)
        )

    return BenchmarkProvider(name, ProviderIdentity(name=name), predict)


def test_hand_calculated_metrics_quantiles_and_censor_cohorts():
    report, rows = evaluate_benchmark(dataset(count=1), (provider("CHRONOS2", quantiles=True),))
    result = report["strategies"]["CHRONOS2"]
    assert result["metrics"] == {"scored_count": 28, "mae": 1, "bias": -1, "wape": 0.5}
    assert result["expected_count"] == result["available_prediction_count"] == 28
    assert result["censored_actual_count"] == result["uncensored_actual_count"] == 14
    quantiles = result["quantile_diagnostics"]
    assert quantiles["pinball_loss"] == {"p10": 0.2, "p50": 0.5, "p90": pytest.approx(0.2)}
    assert quantiles["empirical_interval_coverage"] == 1
    assert quantiles["mean_interval_width"] == 4
    assert quantiles["interpretation"] == "UNCALIBRATED_MODEL_QUANTILES"
    assert all(row["unit"] == "NORMALIZED_RETAIL_SALES" for row in rows)
    assert report["availability_semantics"] == "RETROSPECTIVE_EVENT_TIME"
    assert set(result["by_horizon"]) == {str(i) for i in range(1, 8)}


def test_no_pairs_and_zero_truth_denominator_are_unavailable_not_zero_error():
    report, _ = evaluate_benchmark(
        dataset(count=1, value=0), (provider("SEASONAL_NAIVE", value=1),)
    )
    assert report["strategies"]["SEASONAL_NAIVE"]["metrics"] == {
        "scored_count": 28,
        "mae": 1,
        "bias": 1,
        "wape": None,
    }
    report, _ = evaluate_benchmark(dataset(count=1), (provider("CHRONOS2", fail_store=0),))
    assert report["strategies"]["CHRONOS2"]["metrics"] == {
        "scored_count": 0,
        "mae": None,
        "bias": None,
        "wape": None,
    }


def test_uneven_availability_retains_failures_and_baseline_selection_is_not_chronos_filtered():
    report, _ = evaluate_benchmark(
        dataset(),
        (
            provider("SEASONAL_NAIVE", value=3),
            provider("MOVING_AVERAGE", value=0),
            provider("CHRONOS2", value=2, fail_store=0),
        ),
    )
    model = report["strategies"]["CHRONOS2"]
    assert model["expected_count"] == 56
    assert model["available_prediction_count"] == model["unavailable_prediction_count"] == 28
    assert model["failure_point_counts"] == {"INSUFFICIENT_DATA": 28}
    assert report["paired"]["common_scored_count"] == 28
    selection = report["baseline_selection"]
    assert selection["selected_strategy"] == "SEASONAL_NAIVE"
    assert selection["paired_comparison"]["common_scored_count"] == 56
    assert selection["final_holdout_consulted"] is False


def test_zero_central_estimate_and_point_only_baseline_do_not_invent_quantiles():
    report, _ = evaluate_benchmark(dataset(count=1, value=0), baseline_providers())
    for result in report["strategies"].values():
        assert result["metrics"]["mae"] == 0
        assert result["quantile_diagnostics"]["scored_count"] == 0
        assert result["quantile_diagnostics"]["empirical_interval_coverage"] is None
    assert report["baseline_selection"]["selected_strategy"] == "MOVING_AVERAGE"


def test_only_provider_errors_enable_explicit_offline_fallback():
    fallback = provider("MOVING_AVERAGE", value=2)
    report, rows = evaluate_benchmark(
        dataset(count=1), (provider("CHRONOS2", fail_store=0),), fallback_provider=fallback
    )
    actual = report["strategies"]["CHRONOS2"]
    assert actual["fallback_prediction_count"] == actual["primary_failure_point_count"] == 28
    assert set(actual["actual_provider_cohorts"]) == {"MOVING_AVERAGE"}
    assert all(row["fallback_reason"] == "INSUFFICIENT_DATA" for row in rows)
    with pytest.raises(ValueError, match="programming defect"):
        evaluate_benchmark(
            dataset(count=1), (provider("CHRONOS2", bug=True),), fallback_provider=fallback
        )


def test_invalid_provider_date_mapping_is_counted_without_repair():
    report, _ = evaluate_benchmark(dataset(count=1), (provider("CHRONOS2", wrong_dates=True),))
    actual = report["strategies"]["CHRONOS2"]
    assert actual["available_prediction_count"] == 0
    assert actual["failure_point_counts"] == {"INVALID_PROVIDER_OUTPUT": 28}


def test_missing_actual_and_basis_mismatch_are_counted_separately():
    _, rows = evaluate_benchmark(dataset(count=1), (provider("CHRONOS2"),))
    actual = summarize_records(
        (
            {**rows[0], "actual": None},
            {**rows[1], "actual_basis": "SOME_DIFFERENT_BASIS"},
            {**rows[2], "truth_unit": "meal"},
        )
    )
    assert actual["missing_actual_count"] == 1
    assert actual["basis_mismatch_count"] == 2
    assert actual["metrics"]["scored_count"] == 0


def test_paired_comparisons_reject_duplicate_keys_and_disagreeing_truth():
    _, rows = evaluate_benchmark(
        dataset(count=1), (provider("SEASONAL_NAIVE"), provider("MOVING_AVERAGE"))
    )
    with pytest.raises(ValueError, match="Duplicate"):
        paired_metrics((*rows, rows[0]), ("SEASONAL_NAIVE", "MOVING_AVERAGE"))
    changed = tuple(
        {**row, "actual": 99} if row["strategy"] == "MOVING_AVERAGE" else row for row in rows
    )
    with pytest.raises(ValueError, match="disagree"):
        paired_metrics(changed, ("SEASONAL_NAIVE", "MOVING_AVERAGE"))


def test_future_observations_never_reach_provider_or_change_earlier_predictions():
    original = dataset(count=1)
    cutoff = original.validation_folds[0].cutoff
    changed_series = replace(
        original.series[0],
        observations=tuple(
            replace(row, value=12345) if row.day > cutoff else row
            for row in original.series[0].observations
        ),
    )
    altered = replace(original, series=(changed_series,))
    _, before = evaluate_benchmark(original, baseline_providers())
    _, after = evaluate_benchmark(altered, baseline_providers())
    early_before = [
        (r["predicted"], r["input_hash"])
        for r in before
        if r["origin_cutoff"] == cutoff.isoformat()
    ]
    early_after = [
        (r["predicted"], r["input_hash"]) for r in after if r["origin_cutoff"] == cutoff.isoformat()
    ]
    assert early_before == early_after
    assert any(r["actual"] != other["actual"] for r, other in zip(before, after, strict=True))


def test_final_truth_requires_explicit_opt_in_and_is_not_accepted_by_validation():
    with pytest.raises(PermissionError, match="sealed"):
        evaluate_benchmark(dataset(), baseline_providers(), split="final_holdout")
    with pytest.raises(ValueError, match="Validation"):
        evaluate_benchmark(dataset(), baseline_providers(), final_truth=())
    with pytest.raises(PermissionError, match="sealed"):
        run_final_holdout(
            Path("absent"),
            Path("absent"),
            Path("absent"),
            model_cache_dir="absent",
            operational_qualified=False,
        )


def test_actual_final_truth_keys_and_dates_must_exactly_match_frozen_scope():
    original = dataset(count=1)
    fake_final = replace(
        original.series[0],
        observations=tuple(
            BenchmarkObservation(day, 2, 0) for day in original.final_fold.truth_dates
        ),
    )
    report, _ = evaluate_benchmark(
        original,
        baseline_providers(),
        split="final_holdout",
        final_truth=(fake_final,),
        allow_final_holdout=True,
    )
    assert report["final_holdout_consulted"] is True
    assert "baseline_selection" not in report
    assert report["fold_count"] == 1
    with pytest.raises(ValueError, match="exact seven"):
        evaluate_benchmark(
            original,
            baseline_providers(),
            split="final_holdout",
            final_truth=original.series,
            allow_final_holdout=True,
        )


def test_mutable_or_duplicate_or_unordered_folds_are_rejected_without_changing_source_hashes():
    original = dataset()
    for folds in [
        list(original.validation_folds),
        (*original.validation_folds, original.validation_folds[0]),
        original.validation_folds[::-1],
    ]:
        with pytest.raises((ValueError, TypeError)):
            evaluate_benchmark(replace(original, validation_folds=folds), baseline_providers())


def test_baseline_helpers_keep_calendar_gaps_and_exact_mean():
    naive, mean = SeasonalNaiveAdapter(), MovingAverageAdapter()
    with pytest.raises(ProviderError, match="prior weekday"):
        naive.predict_values((1, None, 3, 4, 5, 6, 7), cutoff=D)
    points = mean.predict_values((None, *([29] * 13)), cutoff=D)
    assert [point.central_estimate for point in points] == [29] * 7
    assert points[0].day == D + timedelta(days=1)
    with pytest.raises(ProviderError, match="Too few"):
        mean.predict_values((0, None), cutoff=D)


def test_cluster_bootstrap_keeps_adjacent_points_together_and_is_reproducible():
    _, rows = evaluate_benchmark(
        dataset(), (provider("CHRONOS2", value=4), provider("SEASONAL_NAIVE", value=3))
    )
    # One complete series has +1 absolute-error difference, the other has -1.
    changed = tuple(
        {**row, "predicted": 2}
        if row["strategy"] == "CHRONOS2" and row["series_id"].startswith("store:1/")
        else row
        for row in rows
    )
    actual = series_cluster_comparison(changed, "CHRONOS2", "SEASONAL_NAIVE")
    assert actual == series_cluster_comparison(changed, "CHRONOS2", "SEASONAL_NAIVE")
    assert actual["paired_count"] == 56
    assert actual["series_cluster_count"] == 2
    assert actual["mae_difference"] == 0
    assert actual["bootstrap"]["lower"] == -1
    assert actual["bootstrap"]["upper"] == 1


def test_final_decision_uses_predeclared_counts_and_leaves_pantry_qualification_open():
    synthetic = dataset(count=100)
    fake_final = tuple(
        replace(
            series,
            observations=tuple(
                BenchmarkObservation(day, 2, 0) for day in synthetic.final_fold.truth_dates
            ),
        )
        for series in synthetic.series
    )
    report, rows = evaluate_benchmark(
        synthetic,
        (provider("CHRONOS2", value=2), provider("SEASONAL_NAIVE", value=3)),
        split="final_holdout",
        final_truth=fake_final,
        allow_final_holdout=True,
    )
    decision = qualification_decision(report, rows, "SEASONAL_NAIVE", operational_qualified=True)
    assert decision["quality_decision"] == "RETAIL_PROXY_IMPROVEMENT_EVIDENCE"
    assert decision["comparison"]["series_cluster_count"] == 100
    assert decision["comparison"]["bootstrap"]["upper"] == -1
    assert decision["pantry_demand_accuracy"].startswith("UNQUALIFIED")
    assert decision["donation_accuracy"].startswith("UNQUALIFIED")
    assert decision["automatic_provider_or_default_switch"] is False
    report["strategies"]["CHRONOS2"]["availability_fraction"] = 0.98
    assert (
        qualification_decision(report, rows, "SEASONAL_NAIVE", operational_qualified=True)[
            "quality_decision"
        ]
        == "INSUFFICIENT_EVIDENCE"
    )


def test_final_code_change_is_detected_and_opening_remains_consumed(tmp_path, monkeypatch):
    original = dataset(count=1)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("synthetic test manifest, not external data")
    monkeypatch.setattr(cli, "load_dataset", lambda _: original)
    monkeypatch.setattr(cli, "model_file_identity", lambda _: {"synthetic": "a" * 64})
    monkeypatch.setattr(
        cli,
        "configured_providers",
        lambda _: (
            provider("SEASONAL_NAIVE", value=3),
            provider("MOVING_AVERAGE", value=1),
            provider("CHRONOS2", value=2),
        ),
    )
    monkeypatch.setattr(cli, "code_identity", lambda: {"code_hash": "before"})
    monkeypatch.setattr(cli, "_runtime", lambda: {"packages": {}})
    validation_dir = tmp_path / "validation"
    cli.run_validation(manifest, validation_dir, cli.ChronosConfig("c" * 40, cache_dir="fake"))
    fake_truth = tuple(
        replace(
            series,
            observations=tuple(
                BenchmarkObservation(day, 2, 0) for day in original.final_fold.truth_dates
            ),
        )
        for series in original.series
    )
    monkeypatch.setattr(cli, "load_final_holdout", lambda *a, **k: fake_truth)
    real_evaluate = cli.evaluate_benchmark

    def changing_code(*args, **kwargs):
        result = real_evaluate(*args, **kwargs)
        monkeypatch.setattr(cli, "code_identity", lambda: {"code_hash": "after"})
        return result

    monkeypatch.setattr(cli, "evaluate_benchmark", changing_code)
    with pytest.raises(ValueError, match="changed during final"):
        cli.run_final_holdout(
            validation_dir,
            tmp_path,
            tmp_path / "final",
            model_cache_dir="fake",
            operational_qualified=False,
            allow_final_holdout=True,
        )
    assert (validation_dir / "final-holdout-opened.json").is_file()
    monkeypatch.setattr(cli, "code_identity", lambda: {"code_hash": "before"})
    with pytest.raises(FileExistsError):
        cli.run_final_holdout(
            validation_dir,
            tmp_path,
            tmp_path / "final",
            model_cache_dir="fake",
            operational_qualified=False,
            allow_final_holdout=True,
        )


def test_rss_measurement_is_optional_on_platforms_without_resource(monkeypatch):
    native_import = builtins.__import__

    def without_resource(name, *args, **kwargs):
        if name == "resource":
            raise ModuleNotFoundError("resource unavailable on this platform")
        return native_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_resource)
    assert cli.peak_rss_kib() is None
