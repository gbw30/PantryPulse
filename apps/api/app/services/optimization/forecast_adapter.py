"""Exact OR boundary; never runs a provider or promotes numerical readiness to a commit."""

from decimal import Decimal, Inexact, Rounded, localcontext
from uuid import UUID

from app.schemas.or_inputs import DemandDay, DemandModifier, DemandSeries, ForecastSeries
from app.services.demand_targets import round_daily_targets
from app.services.forecasting.handoff import ForecastHandoff, verify_handoff


def adapt_series(
    forecasts: tuple[ForecastSeries, ...], modifiers: tuple[DemandModifier, ...]
) -> tuple[DemandSeries, ...]:
    choices = {(x.site_id, x.product_id): x for x in modifiers}
    if len(choices) != len(modifiers) or set(choices) != {
        (x.site_id, x.product_id) for x in forecasts
    }:
        raise ValueError("DEMAND_CHOICE_COVERAGE")
    result = []
    for forecast in forecasts:
        choice = choices[forecast.site_id, forecast.product_id]
        estimates, metadata = [], []
        for point in forecast.days:
            value, method = Decimal(point.central_literal), "CENTRAL"
            if choice.mode == "CONSERVATIVE":
                if point.p90_literal is not None:
                    value, method = Decimal(point.p90_literal), "MODEL_UPPER_QUANTILE"
                elif choice.buffer_fraction is not None:
                    method = "EXPLICIT_BUFFER"
                else:
                    raise ValueError("MISSING_CONSERVATIVE_BUFFER")
            source_literal = str(value)
            # OR-DEC-010 [PROVISIONAL]: apply all modifiers to original estimate then ceil once.
            with localcontext() as context:
                context.prec = 64
                context.traps[Inexact] = context.traps[Rounded] = True
                if method == "EXPLICIT_BUFFER":
                    value *= Decimal(1) + Decimal(choice.buffer_fraction)
                value *= Decimal(choice.multiplier)
            estimates.append((point.day, value))
            metadata.append((source_literal, format(value, "f"), method))
        rounded = round_daily_targets(estimates)
        result.append(
            DemandSeries(
                site_id=forecast.site_id,
                product_id=forecast.product_id,
                unit=forecast.unit,
                forecast_result_id=forecast.id,
                actual_provider=forecast.actual_provider,
                basis=forecast.basis,
                numeric_conversion=forecast.numeric_conversion,
                upstream_metadata_json=forecast.upstream_metadata_json,
                days=tuple(
                    DemandDay(
                        day=p.day,
                        units=p.target,
                        source_literal=m[0],
                        unrounded_literal=m[1],
                        method=m[2],
                    )
                    for p, m in zip(rounded.points, metadata, strict=True)
                ),
            )
        )
    return tuple(sorted(result, key=lambda x: (str(x.site_id), str(x.product_id))))


def adapt_forecasts(
    handoff: ForecastHandoff,
    choices: tuple[DemandModifier, ...],
    *,
    committed_result_ids: tuple[UUID, ...],
    planning_ready: bool,
) -> tuple[DemandSeries, ...]:
    """Adapt a committed handoff; caller supplies actual publication proof, never inferred."""
    verify_handoff(handoff)
    if not planning_ready or set(committed_result_ids) != {
        row.forecast_result.result_id for row in handoff.selected
    }:
        raise ValueError("SOURCE_NOT_COMMITTED")
    import json

    from app.schemas.or_inputs import ForecastDay

    forecasts = []
    for selected in handoff.selected:
        row, scope = selected.forecast_result, selected.scope
        prepared = next(s for s in handoff.forecast_input.series if s.scope.key == scope.key)
        classifications = sorted(
            {c for p in prepared.observations for c in p.source_classifications}
        )
        classification = classifications[0] if len(classifications) == 1 else "MIXED"
        kinds = {p.estimate_kind for p in row.points}
        intervals = {p.interval_method for p in row.points}
        if len(kinds) != 1 or len(intervals) != 1:
            raise ValueError("Mixed per-date estimate types require a later schema version")
        metadata = json.dumps(
            {
                "original_handoff_hash": handoff.content_hash,
                "forecast_input_hash": handoff.forecast_input.input_hash,
                "scope": scope.model_dump(mode="json"),
                "result": row.model_dump(mode="json"),
                "source_classifications": classifications,
                "partial_scope": handoff.partial_scope,
                "excluded_demand": [k.model_dump(mode="json") for k in handoff.excluded_demand],
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        forecasts.append(
            ForecastSeries(
                id=row.result_id,
                run_id=handoff.forecast_output.run_id,
                source_id=handoff.forecast_input.dataset_id,
                organization_id=scope.key.organization_id,
                site_id=scope.key.site_id,
                product_id=scope.key.product_id,
                unit=scope.unit,
                timezone=scope.timezone,
                source_revision=handoff.content_hash,
                actual_provider=row.actual_provider.name,
                basis=row.target_basis,
                source_classification=classification,
                estimate_kind=next(iter(kinds)),
                interval_method=next(iter(intervals)),
                cutoff=handoff.forecast_input.data_cutoff_date,
                generated_at=handoff.forecast_output.generated_at,
                committed=True,
                planning_ready=True,
                numeric_conversion="LEGACY_FLOAT_LITERAL",
                upstream_metadata_json=metadata,
                days=tuple(
                    ForecastDay(
                        day=p.day,
                        central_literal=str(p.central_estimate),
                        p10_literal=None if p.p10 is None else str(p.p10),
                        p50_literal=None if p.p50 is None else str(p.p50),
                        p90_literal=None if p.p90 is None else str(p.p90),
                    )
                    for p in row.points
                ),
            )
        )
    result = adapt_series(tuple(forecasts), choices)
    # With unchanged choices, preserve experimental handoff's verified daily targets.
    old = {(x.scope.key.site_id, x.scope.key.product_id): x for x in handoff.selected}
    for series in result:
        choice = next(
            x for x in choices if (x.site_id, x.product_id) == (series.site_id, series.product_id)
        )
        previous = old[series.site_id, series.product_id]
        old_buffer = (
            None
            if previous.choice.buffer_fraction is None
            else Decimal(str(previous.choice.buffer_fraction))
        )
        new_buffer = None if choice.buffer_fraction is None else Decimal(choice.buffer_fraction)
        if (
            Decimal(choice.multiplier) == 1
            and choice.mode == previous.choice.mode
            and old_buffer == new_buffer
        ):
            if tuple(p.units for p in series.days) != tuple(p.units for p in previous.days):
                raise ValueError("HANDOFF_TARGET_EQUIVALENCE_FAILED")
    return result
