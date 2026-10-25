"""Freeze forecast-derived daily demand for future scenario orchestration.

This is a forecast handoff, not the complete operational scenario (OPEN-19–22).
Donation predictions never become inventory or confirmed arrivals here.
"""

import hashlib
import json
from datetime import date
from decimal import ROUND_CEILING, Decimal
from typing import Literal, Self

from pydantic import Field, model_validator

from .postprocessing import validate_output
from .preparation import validate_input
from .schemas import (
    Contract,
    ForecastInput,
    ForecastOutput,
    ForecastPoint,
    ForecastSeriesResult,
    Quantity,
    SeriesKey,
    SeriesScope,
    series_identity,
)


class DemandChoice(Contract):
    key: SeriesKey
    mode: Literal["CENTRAL", "CONSERVATIVE"]
    buffer_fraction: Quantity | None = None


class PlanningDay(Contract):
    day: date
    units: int = Field(ge=0, strict=True)
    unrounded_units: Quantity
    method: Literal["CENTRAL", "MODEL_UPPER_QUANTILE", "EXPLICIT_BUFFER"]


def _planning_day(point: ForecastPoint, choice: DemandChoice) -> PlanningDay:
    value = Decimal(str(point.central_estimate))
    method = "CENTRAL"
    if choice.mode == "CENTRAL" and choice.buffer_fraction is not None:
        raise ValueError("Central demand does not accept a conservative buffer")
    if choice.mode == "CONSERVATIVE":
        if point.p90 is not None:
            value, method = Decimal(str(point.p90)), "MODEL_UPPER_QUANTILE"
        elif choice.buffer_fraction is not None:
            value *= Decimal(1) + Decimal(str(choice.buffer_fraction))
            method = "EXPLICIT_BUFFER"
        else:
            raise ValueError("Missing upper quantile requires an explicit buffer")
    return PlanningDay(
        day=point.day,
        units=int(value.to_integral_value(rounding=ROUND_CEILING)),
        unrounded_units=float(value),
        method=method,
    )


class PlanningSeries(Contract):
    scope: SeriesScope
    forecast_result: ForecastSeriesResult
    choice: DemandChoice
    days: tuple[PlanningDay, ...]

    @model_validator(mode="after")
    def derived_from_forecast(self) -> Self:
        if (
            self.scope != self.forecast_result.scope
            or self.choice.key != self.scope.key
            or self.forecast_result.status != "AVAILABLE"
        ):
            raise ValueError("Planning series differs from its selected forecast")
        if self.days != tuple(
            _planning_day(point, self.choice) for point in self.forecast_result.points
        ):
            raise ValueError("Planning demand must follow frozen policy and daily ceiling")
        return self


class ForecastHandoff(Contract):
    schema_version: Literal["forecast-handoff-experimental-v1"] = "forecast-handoff-experimental-v1"
    forecast_input: ForecastInput
    forecast_output: ForecastOutput
    selected: tuple[PlanningSeries, ...]
    excluded_demand: tuple[SeriesKey, ...]
    partial_scope: bool
    content_hash: str


def _digest(payload: Contract, exclude: set[str]) -> str:
    encoded = json.dumps(
        payload.model_dump(mode="json", exclude=exclude),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def freeze_handoff(
    inputs: ForecastInput,
    output: ForecastOutput,
    *,
    choices: tuple[DemandChoice, ...],
    excluded_demand: tuple[SeriesKey, ...] = (),
    allow_partial_scope: bool = False,
) -> ForecastHandoff:
    inputs = validate_input(inputs)
    output = validate_output(inputs, output)
    scope = {row.scope.key: row.scope for row in inputs.series}
    results = {row.scope.key: row for row in output.series}
    selected_keys = {choice.key for choice in choices}
    demand_keys = {key for key in scope if key.target_type == "DEMAND"}
    if not choices or len(selected_keys) != len(choices) or not selected_keys <= demand_keys:
        raise ValueError("Choose unique, included demand series")
    excluded = set(excluded_demand)
    if len(excluded) != len(excluded_demand) or excluded != demand_keys - selected_keys:
        raise ValueError("Every excluded demand series must be explicitly declared")
    if excluded and not allow_partial_scope:
        raise ValueError("Partial scope requires explicit opt-in")
    # A required donation failure also prevents a full planning-ready handoff.
    required_failures = {
        key for key, row in results.items() if row.scope.required and row.status != "AVAILABLE"
    }
    if required_failures - excluded:
        raise ValueError("Unavailable required series blocks planning handoff")
    selected = []
    for choice in sorted(choices, key=lambda c: series_identity(c.key)):
        result = results[choice.key]
        if result.status != "AVAILABLE" or result.actual_provider is None:
            raise ValueError("Selected demand series is unavailable")
        selected.append(
            PlanningSeries(
                scope=result.scope,
                forecast_result=result,
                choice=choice,
                days=tuple(_planning_day(point, choice) for point in result.points),
            )
        )
    handoff = ForecastHandoff(
        forecast_input=inputs,
        forecast_output=output,
        selected=tuple(selected),
        excluded_demand=tuple(sorted(excluded, key=series_identity)),
        partial_scope=bool(excluded) or output.partial_scope,
        content_hash="",
    )
    return handoff.model_copy(update={"content_hash": _digest(handoff, {"content_hash"})})


def verify_handoff(handoff: ForecastHandoff) -> None:
    handoff = ForecastHandoff.model_validate(handoff.model_dump())
    if handoff.content_hash != _digest(handoff, {"content_hash"}):
        raise ValueError("Frozen forecast handoff hash mismatch")
    rebuilt = freeze_handoff(
        handoff.forecast_input,
        handoff.forecast_output,
        choices=tuple(series.choice for series in handoff.selected),
        excluded_demand=handoff.excluded_demand,
        allow_partial_scope=handoff.partial_scope,
    )
    if rebuilt != handoff:
        raise ValueError("Frozen handoff contradicts selected forecasts and policy")
