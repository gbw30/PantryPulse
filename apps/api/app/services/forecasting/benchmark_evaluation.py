"""Chronological offline evaluation retaining source-native retail semantics.

Only origin-limited windows reach providers. Every expected point remains in the
report, including failed predictions and censored/missing truth. The final split
is inaccessible without explicit truth plus an opt-in; this module never opens it.
"""

import math
import random
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from .adapters.base import ProviderError
from .adapters.moving_average import MovingAverageAdapter
from .adapters.seasonal_naive import SeasonalNaiveAdapter
from .benchmark_data import (
    AVAILABILITY,
    RETAIL_BASIS,
    RETAIL_UNIT,
    SEED,
    BenchmarkDataset,
    BenchmarkFold,
    BenchmarkSeries,
    BenchmarkWindow,
    canonical_hash,
)
from .evaluation import metrics
from .schemas import ForecastPoint, ProviderIdentity

BASELINES = ("SEASONAL_NAIVE", "MOVING_AVERAGE")
EVALUATOR_VERSION = "retail-rolling-evaluation-v1"


@dataclass(frozen=True, slots=True)
class BenchmarkProvider:
    strategy: str
    identity: ProviderIdentity
    predict: Callable[[BenchmarkWindow], tuple[ForecastPoint, ...]]


@dataclass(frozen=True, slots=True)
class _MetricPair:
    actual: float
    predicted: float


def baseline_providers() -> tuple[BenchmarkProvider, ...]:
    seasonal, mean = SeasonalNaiveAdapter(), MovingAverageAdapter()
    return (
        BenchmarkProvider(
            "SEASONAL_NAIVE",
            seasonal.identity,
            lambda window: seasonal.predict_values(
                tuple(row.value for row in window.observations), cutoff=window.cutoff
            ),
        ),
        BenchmarkProvider(
            "MOVING_AVERAGE",
            mean.identity,
            lambda window: mean.predict_values(
                tuple(row.value for row in window.observations),
                cutoff=window.cutoff,
                window_days=14,
                min_samples=3,
            ),
        ),
    )


def _validated_points(points: object, fold: BenchmarkFold) -> tuple[ForecastPoint, ...]:
    try:
        if not isinstance(points, tuple):
            raise ValueError("Provider must return immutable forecast points")
        checked = tuple(ForecastPoint.model_validate(point.model_dump()) for point in points)
        if len(checked) != 7 or tuple(point.day for point in checked) != fold.truth_dates:
            raise ValueError("Provider dates do not match the exact seven-day fold")
        return checked
    except (ValidationError, ValueError, AttributeError, TypeError) as exc:
        raise ProviderError("INVALID_PROVIDER_OUTPUT", "Invalid benchmark provider output") from exc


def _scoreable(row: dict) -> bool:
    return (
        row["actual"] is not None
        and row["predicted"] is not None
        and row["unit"] == row["truth_unit"]
        and row["forecast_basis"] == row["actual_basis"]
    )


def _key(row: dict) -> tuple:
    return (row["series_id"], row["origin_cutoff"], row["day"], row["unit"], row["forecast_basis"])


def _metrics(rows: Sequence[dict]) -> dict:
    # Reuse the existing evaluator's fsum arithmetic and null-denominator rules.
    pairs = tuple(_MetricPair(row["actual"], row["predicted"]) for row in rows if _scoreable(row))
    return metrics(pairs).model_dump(mode="json")


def quantile_diagnostics(rows: Sequence[dict]) -> dict:
    available = [
        row
        for row in rows
        if _scoreable(row) and all(row[key] is not None for key in ("p10", "p50", "p90"))
    ]
    count = len(available)
    losses = {}
    for level, column in ((0.1, "p10"), (0.5, "p50"), (0.9, "p90")):
        losses[column] = (
            math.fsum(
                max(
                    level * (row["actual"] - row[column]),
                    (level - 1) * (row["actual"] - row[column]),
                )
                for row in available
            )
            / count
            if count
            else None
        )
    return {
        "interpretation": "UNCALIBRATED_MODEL_QUANTILES",
        "scored_count": count,
        "pinball_loss": losses,
        "nominal_interval_coverage": 0.8,
        "empirical_interval_coverage": (
            sum(row["p10"] <= row["actual"] <= row["p90"] for row in available) / count
            if count
            else None
        ),
        "mean_interval_width": (
            math.fsum(row["p90"] - row["p10"] for row in available) / count if count else None
        ),
    }


def summarize_records(rows: Sequence[dict]) -> dict:
    """Full expected-population counts accompany every metric aggregation."""
    count = len(rows)
    available = sum(row["predicted"] is not None for row in rows)
    basis_mismatch = sum(
        row["actual"] is not None
        and row["predicted"] is not None
        and (row["unit"] != row["truth_unit"] or row["forecast_basis"] != row["actual_basis"])
        for row in rows
    )
    failures = defaultdict(int)
    for row in rows:
        if row["error_code"]:
            failures[row["error_code"]] += 1
    return {
        "expected_count": count,
        "available_prediction_count": available,
        "availability_fraction": available / count if count else None,
        "unavailable_prediction_count": count - available,
        "missing_actual_count": sum(row["actual"] is None for row in rows),
        "basis_mismatch_count": basis_mismatch,
        "censored_actual_count": sum(row["censored"] is True for row in rows),
        "uncensored_actual_count": sum(row["censored"] is False for row in rows),
        "unknown_censoring_count": sum(row["censored"] is None for row in rows),
        "fallback_prediction_count": sum(row["fallback_used"] for row in rows),
        "primary_failure_point_count": sum(row["primary_error_code"] is not None for row in rows),
        "failure_point_counts": dict(sorted(failures.items())),
        "metrics": _metrics(rows),
        "quantile_diagnostics": quantile_diagnostics(rows),
    }


def _group(rows: Sequence[dict], field: str) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        value = row[field]
        grouped[str(value) if value is not None else "UNAVAILABLE"].append(row)
    return {key: summarize_records(grouped[key]) for key in sorted(grouped)}


def paired_metrics(rows: Sequence[dict], strategies: Sequence[str]) -> dict:
    if not strategies or len(set(strategies)) != len(strategies):
        raise ValueError("Paired comparison needs unique strategies")
    by_strategy = {strategy: {} for strategy in strategies}
    for row in rows:
        if row["strategy"] not in by_strategy or not _scoreable(row):
            continue
        key = _key(row)
        if key in by_strategy[row["strategy"]]:
            raise ValueError("Duplicate scored prediction key")
        by_strategy[row["strategy"]][key] = row
    common = set.intersection(*(set(mapping) for mapping in by_strategy.values()))
    ordered = sorted(common)
    for key in ordered:
        actuals = {by_strategy[strategy][key]["actual"] for strategy in strategies}
        if len(actuals) != 1:
            raise ValueError("Paired predictions disagree about held-out truth")
    return {
        "strategies": list(strategies),
        "common_scored_count": len(common),
        "common_keys_hash": canonical_hash(ordered),
        "metrics": {
            strategy: _metrics([by_strategy[strategy][key] for key in ordered])
            for strategy in strategies
        },
    }


def validation_baseline_selection(rows: Sequence[dict]) -> dict:
    """Lowest paired validation MAE; names break exact ties deterministically."""
    if any(row["split"] != "validation" for row in rows):
        raise ValueError("Baseline selection must not inspect final holdout")
    comparison = paired_metrics(rows, BASELINES)
    candidates = [
        strategy for strategy in BASELINES if comparison["metrics"][strategy]["mae"] is not None
    ]
    chosen = (
        min(candidates, key=lambda name: (comparison["metrics"][name]["mae"], name))
        if candidates
        else None
    )
    return {
        "selected_strategy": chosen,
        "selection_metric": "MAE_ON_BASELINE_ONLY_COMMON_VALIDATION_KEYS",
        "tie_break": "LEXICOGRAPHIC_STRATEGY_NAME",
        "paired_comparison": comparison,
        "full_coverage": {
            name: summarize_records([row for row in rows if row["strategy"] == name])
            for name in BASELINES
        },
        "final_holdout_consulted": False,
    }


def _check_folds(dataset: BenchmarkDataset) -> None:
    if type(dataset.series) is not tuple or type(dataset.validation_folds) is not tuple:
        raise TypeError("Evaluation requires immutable dataset series/folds")
    folds = dataset.validation_folds
    if len({fold.name for fold in folds}) != len(folds) or len(
        {fold.cutoff for fold in folds}
    ) != len(folds):
        raise ValueError("Duplicate validation fold names/origins")
    if tuple(sorted(folds, key=lambda fold: fold.cutoff)) != folds:
        raise ValueError("Validation origins must be ordered")


def evaluate_benchmark(
    dataset: BenchmarkDataset,
    providers: tuple[BenchmarkProvider, ...],
    *,
    split: str = "validation",
    final_truth: tuple[BenchmarkSeries, ...] | None = None,
    allow_final_holdout: bool = False,
    fallback_provider: BenchmarkProvider | None = None,
) -> tuple[dict, tuple[dict, ...]]:
    """Return report + complete point records; no source files or final data opened.

    An explicit offline fallback is per series/origin and labelled accordingly;
    it is not the application's whole-batch execution acceptance. Primary model
    comparison uses fallback_provider=None.
    """
    _check_folds(dataset)
    if (
        type(providers) is not tuple
        or not providers
        or len({p.strategy for p in providers}) != len(providers)
    ):
        raise ValueError("Evaluation needs immutable providers with distinct strategy names")
    if split == "validation":
        if final_truth is not None or allow_final_holdout:
            raise ValueError("Validation must not receive final truth or a final opt-in")
        folds, truth_series = dataset.validation_folds, dataset.series
    elif split == "final_holdout":
        if allow_final_holdout is not True or final_truth is None:
            raise PermissionError(
                "Final holdout is sealed; explicit truth and FC-07 opt-in required"
            )
        if type(final_truth) is not tuple:
            raise TypeError("Final truth must be an immutable series tuple")
        folds, truth_series = (dataset.final_fold,), final_truth
    else:
        raise ValueError("Unknown evaluation split")
    truth_by_series = {series.series_id: series for series in truth_series}
    if len(truth_by_series) != len(truth_series) or set(truth_by_series) != {
        series.series_id for series in dataset.series
    }:
        raise ValueError("Truth series must match the exact frozen cohort")
    records, executions = [], []
    for series in sorted(dataset.series, key=lambda row: row.series_id):
        actual_series = truth_by_series[series.series_id]
        truth_by_day = {row.day: row for row in actual_series.observations}
        if (
            split == "final_holdout"
            and tuple(sorted(truth_by_day)) != dataset.final_fold.truth_dates
        ):
            raise ValueError("Final truth must contain only the exact seven sealed dates")
        for fold in folds:
            window = series.at_origin(fold.cutoff)
            cohorts = {
                "training_has_zero": any(row.value == 0 for row in window.observations),
                "training_has_missing": any(row.value is None for row in window.observations),
                "training_has_censoring": any(row.censored is True for row in window.observations),
            }
            for provider in providers:
                points, primary_error, error, actual_provider, used_fallback = (
                    (),
                    None,
                    None,
                    None,
                    False,
                )
                start = time.monotonic()
                try:
                    points = _validated_points(provider.predict(window), fold)
                    actual_provider = provider.identity.name
                except ProviderError as exc:
                    primary_error = error = exc.code
                    if (
                        fallback_provider is not None
                        and fallback_provider.strategy != provider.strategy
                    ):
                        try:
                            points = _validated_points(fallback_provider.predict(window), fold)
                            actual_provider = fallback_provider.identity.name
                            error, used_fallback = None, True
                        except ProviderError as fallback_exc:
                            error = fallback_exc.code
                executions.append(
                    {
                        "strategy": provider.strategy,
                        "series_id": series.series_id,
                        "origin_cutoff": fold.cutoff.isoformat(),
                        "wall_seconds": time.monotonic() - start,
                        "actual_provider": actual_provider,
                        "primary_error_code": primary_error,
                        "error_code": error,
                        "fallback_used": used_fallback,
                    }
                )
                by_day = {point.day: point for point in points}
                for horizon, day in enumerate(fold.truth_dates, 1):
                    truth = truth_by_day.get(day)
                    point = by_day.get(day)
                    records.append(
                        {
                            "strategy": provider.strategy,
                            "actual_provider": actual_provider,
                            "series_id": series.series_id,
                            "origin": fold.name,
                            "origin_cutoff": fold.cutoff.isoformat(),
                            "split": split,
                            "day": day.isoformat(),
                            "horizon": horizon,
                            "unit": window.unit,
                            "truth_unit": actual_series.unit,
                            "forecast_basis": window.target_basis,
                            "actual_basis": actual_series.target_basis,
                            "actual": truth.value if truth is not None else None,
                            "censored": truth.censored if truth is not None else None,
                            "predicted": point.central_estimate if point is not None else None,
                            "estimate_kind": point.estimate_kind if point is not None else None,
                            "p10": point.p10 if point is not None else None,
                            "p50": point.p50 if point is not None else None,
                            "p90": point.p90 if point is not None else None,
                            "interval_method": point.interval_method
                            if point is not None
                            else "NONE",
                            "fallback_used": used_fallback,
                            "fallback_reason": primary_error if used_fallback else None,
                            "primary_error_code": primary_error,
                            "error_code": error,
                            "input_hash": window.input_hash,
                            **cohorts,
                        }
                    )
    summaries = {}
    for provider in providers:
        rows = [row for row in records if row["strategy"] == provider.strategy]
        summaries[provider.strategy] = {
            **summarize_records(rows),
            "actual_provider_cohorts": _group(rows, "actual_provider"),
            "by_horizon": _group(rows, "horizon"),
            "by_series": _group(rows, "series_id"),
            "censoring_diagnostics": _group(rows, "censored"),
            "training_cohorts": {
                name: _group(rows, name)
                for name in ("training_has_zero", "training_has_missing", "training_has_censoring")
            },
        }
    report = {
        "schema_version": EVALUATOR_VERSION,
        "experiment_scope": "OFFLINE_RETAIL_OBSERVED_SALES_PROXY",
        "availability_semantics": AVAILABILITY,
        "unit": RETAIL_UNIT,
        "target_basis": RETAIL_BASIS,
        "split": split,
        "series_count": len(dataset.series),
        "fold_count": len(folds),
        "final_holdout_consulted": split == "final_holdout",
        "dataset": {
            "source_id": dataset.source_id,
            "source_revision": dataset.source_revision,
            "manifest_hash": dataset.manifest_hash,
            "cohort_hash": dataset.cohort_hash,
            "train_sha256": dataset.source_train_sha256,
            "eval_sha256": dataset.source_eval_sha256,
        },
        "folds": [fold.as_dict() for fold in folds],
        "folds_hash": canonical_hash([fold.as_dict() for fold in folds]),
        "providers": {p.strategy: p.identity.model_dump(mode="json") for p in providers},
        "experiment_settings": {
            "horizon_days": 7,
            "mean_window_days": 14,
            "mean_min_samples": 3,
            "fallback_enabled": fallback_provider is not None,
            "fallback_scope": "OFFLINE_PER_SERIES_ORIGIN" if fallback_provider else "NONE",
            "cohort_definitions": "ORIGIN_TRAINING_HAS_ZERO_MISSING_CENSORING_V1",
            "quantiles": "RAW_UNCALIBRATED",
            "no_imputation_or_output_clipping": True,
        },
        "strategies": summaries,
        "paired": paired_metrics(records, tuple(p.strategy for p in providers)),
        "raw_predictions_hash": canonical_hash(records),
        "execution": {
            "requests": executions,
            "total_provider_wall_seconds": math.fsum(r["wall_seconds"] for r in executions),
        },
        "limitations": [
            "Normalized retail sales are not latent demand, pantry requested need or donations",
            "Uncensored diagnostics condition on realized availability; not population accuracy",
            "Short history; model pretraining overlap unknown; no fitted interval calibration",
            "Missing/failure coverage is disclosed alongside paired intersections",
        ],
    }
    if split == "validation" and all(name in summaries for name in BASELINES):
        report["baseline_selection"] = validation_baseline_selection(records)
    # Only deterministic metrics/predictions enter this identity; timings vary.
    report["metrics_hash"] = canonical_hash({k: v for k, v in report.items() if k != "execution"})
    return report, tuple(records)


def _percentile(ordered: list[float], probability: float) -> float:
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def series_cluster_comparison(
    rows: Sequence[dict], strategy: str, baseline: str, *, replicates: int = 500, seed: int = SEED
) -> dict:
    """Resample series, retaining adjacent days/overlapping origins inside clusters."""
    if type(replicates) is not int or replicates < 1:
        raise ValueError("Bootstrap replicates must be positive")
    paired_metrics(rows, (strategy, baseline))  # also checks identical truth/unique keys
    mappings = {
        name: {_key(row): row for row in rows if row["strategy"] == name and _scoreable(row)}
        for name in (strategy, baseline)
    }
    common = sorted(set(mappings[strategy]) & set(mappings[baseline]))
    clusters = defaultdict(list)
    for key in common:
        left, right = mappings[strategy][key], mappings[baseline][key]
        clusters[left["series_id"]].append(
            (abs(left["predicted"] - left["actual"]), abs(right["predicted"] - right["actual"]))
        )
    cluster_totals = [
        (
            math.fsum(left for left, _ in values),
            math.fsum(right for _, right in values),
            len(values),
        )
        for _, values in sorted(clusters.items())
    ]
    count = len(common)
    model_mae = math.fsum(left for left, _, _ in cluster_totals) / count if count else None
    baseline_mae = math.fsum(right for _, right, _ in cluster_totals) / count if count else None
    draws = []
    if count:
        rng = random.Random(seed)
        for _ in range(replicates):
            sampled = [rng.choice(cluster_totals) for _ in cluster_totals]
            draws.append(
                math.fsum(left - right for left, right, _ in sampled)
                / sum(n for _, _, n in sampled)
            )
        draws.sort()
    return {
        "strategy": strategy,
        "baseline": baseline,
        "paired_count": count,
        "series_cluster_count": len(clusters),
        "model_mae": model_mae,
        "baseline_mae": baseline_mae,
        "mae_difference": model_mae - baseline_mae if count else None,
        "relative_mae": (
            model_mae / baseline_mae if baseline_mae else 1.0 if count and model_mae == 0 else None
        ),
        "bootstrap": {
            "method": "SERIES_CLUSTER_POOLED_POINT_MAE",
            "replicates": replicates,
            "seed": seed,
            "confidence": 0.95,
            "lower": _percentile(draws, 0.025) if draws else None,
            "upper": _percentile(draws, 0.975) if draws else None,
        },
    }


def qualification_decision(
    report: dict,
    rows: Sequence[dict],
    baseline: str,
    *,
    operational_qualified: bool,
    model_strategy: str = "CHRONOS2",
) -> dict:
    """Apply the predeclared protocol; never choose/tune a baseline from final truth."""
    if report["split"] != "final_holdout":
        raise ValueError("Final qualification requires an explicit final-holdout report")
    if baseline not in BASELINES or type(operational_qualified) is not bool:
        raise ValueError("Use the frozen validation baseline and explicit runtime evidence")
    comparison = series_cluster_comparison(rows, model_strategy, baseline)
    coverage = report["strategies"][model_strategy]["availability_fraction"]
    enough = comparison["series_cluster_count"] >= 100 and coverage is not None and coverage >= 0.99
    model_mae, baseline_mae = comparison["model_mae"], comparison["baseline_mae"]
    compatible = (
        enough
        and model_mae is not None
        and baseline_mae is not None
        and (model_mae <= baseline_mae * 1.05)
    )
    improvement = compatible and comparison["bootstrap"]["upper"] < 0
    if not enough or model_mae is None or baseline_mae is None:
        quality = "INSUFFICIENT_EVIDENCE"
    elif not compatible:
        quality = "REJECTED_FOR_EVALUATED_RETAIL_PROXY_SCOPE"
    elif improvement:
        quality = "RETAIL_PROXY_IMPROVEMENT_EVIDENCE"
    else:
        quality = "RETAIL_PROXY_COMPATIBLE"
    return {
        "protocol": "forecasting-qualification-v1",
        "quality_decision": quality,
        "operational_qualified": operational_qualified,
        "scoped_model_decision": quality
        if operational_qualified
        else "EXPERIMENTAL_RUNTIME_UNQUALIFIED",
        "comparison": comparison,
        "thresholds": {"min_series": 100, "min_availability": 0.99, "max_relative_mae": 1.05},
        "pantry_demand_accuracy": "UNQUALIFIED_NO_REPRESENTATIVE_SOURCE",
        "donation_accuracy": "UNQUALIFIED_NO_REPRESENTATIVE_SOURCE",
        "interval_calibration": "UNQUALIFIED_RAW_DIAGNOSTICS_ONLY",
        "automatic_provider_or_default_switch": False,
    }
