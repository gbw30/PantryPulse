"""Chronological, provider-neutral evaluation with explicit coverage and paired sets."""

from collections import defaultdict
from datetime import date
from math import fsum
from typing import Literal

from pydantic import AwareDatetime

from .preparation import prepare
from .schemas import (
    Contract,
    ForecastPolicy,
    ForecastSeriesResult,
    HistoryBundle,
    SeriesKey,
    series_identity,
)
from .service import forecast


class EvaluationOrigin(Contract):
    data_cutoff_date: date
    snapshot_as_of: AwareDatetime


class ScoredPair(Contract):
    key: SeriesKey
    unit: str
    origin: EvaluationOrigin
    day: date
    actual: float
    predicted: float
    actual_basis: str
    forecast_basis: str
    actual_provider: str
    fallback_used: bool


class Metrics(Contract):
    scored_count: int
    mae: float | None
    bias: float | None
    wape: float | None


class MetricGroup(Contract):
    target_type: str
    product_id: str
    unit: str
    actual_basis: str
    actual_provider: str | None
    metrics: Metrics


class FoldResult(Contract):
    origin: EvaluationOrigin
    input_hash: str
    expected_count: int
    predicted_count: int
    unavailable_prediction_count: int
    missing_actual_count: int
    basis_mismatch_count: int
    fallback_series_count: int
    series_results: tuple[ForecastSeriesResult, ...]
    pairs: tuple[ScoredPair, ...]


class EvaluationReport(Contract):
    schema_version: Literal["forecast-evaluation-experimental-v1"] = (
        "forecast-evaluation-experimental-v1"
    )
    policy: ForecastPolicy
    truth_as_of: AwareDatetime
    availability_semantics: str
    source_classifications: tuple[str, ...]
    aggregation: Literal["POOLED_WITHIN_TARGET_PRODUCT_UNIT_BASIS"] = (
        "POOLED_WITHIN_TARGET_PRODUCT_UNIT_BASIS"
    )
    bias_sign: Literal["POSITIVE_IS_OVERPREDICTION"] = "POSITIVE_IS_OVERPREDICTION"
    folds: tuple[FoldResult, ...]
    strategy_metrics: tuple[MetricGroup, ...]
    actual_provider_metrics: tuple[MetricGroup, ...]


def metrics(pairs: tuple[ScoredPair, ...]) -> Metrics:
    n = len(pairs)
    if not n:
        return Metrics(scored_count=0, mae=None, bias=None, wape=None)
    absolute = fsum(abs(pair.predicted - pair.actual) for pair in pairs)
    actual_total = fsum(pair.actual for pair in pairs)
    return Metrics(
        scored_count=n,
        mae=absolute / n,
        bias=fsum(pair.predicted - pair.actual for pair in pairs) / n,
        wape=absolute / actual_total if actual_total else None,
    )


def grouped_metrics(
    pairs: tuple[ScoredPair, ...], *, by_provider: bool = False
) -> tuple[MetricGroup, ...]:
    groups = defaultdict(list)
    for pair in pairs:
        group = (
            pair.key.target_type,
            str(pair.key.product_id),
            pair.unit,
            pair.actual_basis,
            pair.actual_provider if by_provider else "",
        )
        groups[group].append(pair)
    return tuple(
        MetricGroup(
            target_type=target,
            product_id=product,
            unit=unit,
            actual_basis=basis,
            actual_provider=provider or None,
            metrics=metrics(tuple(groups[group])),
        )
        for group in sorted(groups)
        for target, product, unit, basis, provider in [group]
    )


def backtest(
    history: HistoryBundle,
    *,
    origins: tuple[EvaluationOrigin, ...],
    policy: ForecastPolicy,
    truth_as_of: AwareDatetime,
) -> EvaluationReport:
    from datetime import timedelta

    if not origins or len(set(origins)) != len(origins):
        raise ValueError("Evaluation requires unique, explicit historical origins")
    if any(origin.snapshot_as_of > truth_as_of for origin in origins):
        raise ValueError("Held-out truth cannot predate an origin's knowledge cutoff")
    folds = []
    labels = set()
    for origin in sorted(origins, key=lambda row: (row.data_cutoff_date, row.snapshot_as_of)):
        inputs = prepare(
            history,
            data_cutoff_date=origin.data_cutoff_date,
            snapshot_as_of=origin.snapshot_as_of,
            policy=policy,
        )
        output = forecast(inputs)
        labels.update(
            label
            for series in inputs.series
            for row in series.observations
            for label in row.source_classifications
        )
        actuals = prepare(
            history,
            data_cutoff_date=origin.data_cutoff_date + timedelta(days=7),
            snapshot_as_of=truth_as_of,
            # Truth is scored per day, not fitted as a combined training series.
            # Keep proxy authorization, but allow different actual bases to reach
            # mismatch accounting. The training policy above remains unchanged.
            policy=policy.model_copy(update={"allow_mixed_proxy_history": True}),
        )
        lookup = {
            row.scope.key: {observation.day: observation for observation in row.observations}
            for row in actuals.series
        }
        pairs = []
        predicted = missing = mismatch = 0
        for result in output.series:
            predicted += len(result.points)
            for point in result.points:
                actual = lookup[result.scope.key].get(point.day)
                if actual is None or actual.is_missing:
                    missing += 1
                    continue
                if result.target_basis != "MIXED" and result.target_basis != actual.target_basis:
                    mismatch += 1
                    continue
                labels.update(actual.source_classifications)
                pairs.append(
                    ScoredPair(
                        key=result.scope.key,
                        unit=result.scope.unit,
                        origin=origin,
                        day=point.day,
                        actual=actual.value,
                        predicted=point.central_estimate,
                        actual_basis=actual.target_basis,
                        forecast_basis=result.target_basis,
                        actual_provider=result.actual_provider.name,
                        fallback_used=result.fallback_used,
                    )
                )
        expected = len(inputs.series) * 7
        folds.append(
            FoldResult(
                origin=origin,
                input_hash=inputs.input_hash,
                expected_count=expected,
                predicted_count=predicted,
                unavailable_prediction_count=expected - predicted,
                missing_actual_count=missing,
                basis_mismatch_count=mismatch,
                fallback_series_count=sum(row.fallback_used for row in output.series),
                pairs=tuple(pairs),
                series_results=output.series,
            )
        )
    all_pairs = tuple(pair for fold in folds for pair in fold.pairs)
    return EvaluationReport(
        policy=policy,
        truth_as_of=truth_as_of,
        availability_semantics=history.availability_semantics,
        source_classifications=tuple(sorted(labels)),
        folds=tuple(folds),
        strategy_metrics=grouped_metrics(all_pairs),
        actual_provider_metrics=grouped_metrics(all_pairs, by_provider=True),
    )


def paired_metrics(reports: tuple[EvaluationReport, ...]) -> tuple[tuple[MetricGroup, ...], ...]:
    """Compare every strategy on the same origin/series/day/basis and identical truth.

    The original reports retain full failure and coverage counts; an empty paired
    group is not evidence of equal accuracy. Fallback remains attributed to the
    actual provider in each ScoredPair.
    """
    if len(reports) < 2:
        raise ValueError("Paired metrics require at least two strategy reports")
    lookups = []
    for report in reports:
        lookup = {}
        for fold in report.folds:
            for pair in fold.pairs:
                identity = (
                    pair.origin,
                    series_identity(pair.key),
                    pair.day,
                    pair.unit,
                    pair.actual_basis,
                )
                lookup[identity] = pair
        lookups.append(lookup)
    common = set(lookups[0]).intersection(*(set(lookup) for lookup in lookups[1:]))
    for identity in common:
        if len({lookup[identity].actual for lookup in lookups}) != 1:
            raise ValueError("Paired reports disagree about held-out truth")
    return tuple(
        grouped_metrics(tuple(lookup[identity] for identity in sorted(common, key=str)))
        for lookup in lookups
    )
