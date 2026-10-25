"""Reject invalid output; historical values and provider quantiles are never repaired."""

from datetime import timedelta

from pydantic import ValidationError

from .adapters.base import ProviderError
from .schemas import ForecastInput, ForecastOutput, ForecastPoint


def validate_points(
    points: tuple[ForecastPoint, ...], inputs: ForecastInput
) -> tuple[ForecastPoint, ...]:
    try:
        validated = tuple(ForecastPoint.model_validate(point.model_dump()) for point in points)
    except (ValidationError, AttributeError, TypeError) as exc:
        raise ProviderError(
            "INVALID_PROVIDER_OUTPUT", "Provider returned invalid numeric output"
        ) from exc
    expected = {inputs.data_cutoff_date + timedelta(days=i) for i in range(1, 8)}
    if len(validated) != 7 or {point.day for point in validated} != expected:
        raise ProviderError(
            "INVALID_PROVIDER_OUTPUT", "Provider must return seven unique future dates"
        )
    return tuple(sorted(validated, key=lambda point: point.day))


def validate_output(inputs: ForecastInput, output: ForecastOutput) -> ForecastOutput:
    """Validate a saved output against its exact frozen series scope and provenance."""
    output = ForecastOutput.model_validate(output.model_dump())
    if output.input_hash != inputs.input_hash or output.data_cutoff_date != inputs.data_cutoff_date:
        raise ValueError("Forecast output input hash/cutoff mismatch")
    prepared = {row.scope.key: row for row in inputs.series}
    results = {row.scope.key: row for row in output.series}
    if prepared.keys() != results.keys():
        raise ValueError("Forecast output scope mismatch")
    for key, result in results.items():
        series = prepared[key]
        if (
            result.scope != series.scope
            or result.target_basis != series.target_basis
            or result.diagnostics != series.diagnostics
        ):
            raise ValueError("Forecast output series identity/provenance mismatch")
        if result.status == "AVAILABLE":
            validate_points(result.points, inputs)
    return output
