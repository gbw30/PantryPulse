"""Pure synchronous computation, intended for a future durable job's controlled worker.

This entry point does not implement HTTP submission, persistence or job admission.
Only explicitly classified provider failures permit fallback. Validation/bugs are
not relabeled as a successful provider substitution.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import ValidationError

from .adapters.base import ForecastAdapter, ProviderError
from .adapters.chronos2 import Chronos2Adapter
from .adapters.moving_average import MovingAverageAdapter
from .adapters.seasonal_naive import SeasonalNaiveAdapter
from .postprocessing import validate_output, validate_points
from .preparation import validate_input
from .schemas import ForecastInput, ForecastOutput, ForecastSeriesResult, StructuredError


def forecast(
    inputs: ForecastInput,
    *,
    adapter: ForecastAdapter | None = None,
    run_id: UUID | None = None,
    single_candidate: bool = False,
) -> ForecastOutput:
    inputs = validate_input(inputs)
    adapters = {
        "SEASONAL_NAIVE": SeasonalNaiveAdapter,
        "MOVING_AVERAGE": MovingAverageAdapter,
        "CHRONOS2": Chronos2Adapter,
    }
    primary = adapter if adapter is not None else adapters[inputs.policy.strategy]()
    generated_at = datetime.now(UTC)
    results = []
    for series in inputs.series:
        warnings = set(series.warnings)
        fallback_reason = None
        errors = ()
        points = ()
        actual = None
        failure = None
        candidates = [primary]
        if inputs.policy.allow_fallback and not single_candidate:
            if inputs.policy.strategy == "CHRONOS2":
                candidates.append(SeasonalNaiveAdapter())
            if inputs.policy.strategy != "MOVING_AVERAGE":
                candidates.append(MovingAverageAdapter())
        for candidate in candidates:
            try:
                try:
                    raw_points = candidate.predict(series, inputs)
                except ValidationError as exc:
                    raise ProviderError(
                        "INVALID_PROVIDER_OUTPUT",
                        "Provider returned invalid numeric output",
                    ) from exc
                points = validate_points(raw_points, inputs)
                actual = candidate.identity
                if actual.name == "MOVING_AVERAGE":
                    warnings.add("SPARSE_HISTORY")
                break
            except ProviderError as exc:
                failure = exc
                if fallback_reason is None:
                    fallback_reason = exc.code
        if actual is None:
            assert failure is not None
            errors = (
                StructuredError(
                    code=failure.code,
                    message=failure.safe_message,
                    category="DATA" if failure.code == "INSUFFICIENT_DATA" else "PROVIDER",
                    retryable=False,
                ),
            )
        status = (
            "AVAILABLE"
            if actual
            else "INSUFFICIENT_DATA"
            if failure and failure.code == "INSUFFICIENT_DATA"
            else "FAILED"
        )
        results.append(
            ForecastSeriesResult(
                result_id=uuid4(),
                scope=series.scope,
                status=status,
                target_basis=series.target_basis,
                diagnostics=series.diagnostics,
                actual_provider=actual,
                fallback_used=actual is not None and fallback_reason is not None,
                fallback_reason=fallback_reason,
                input_hash=inputs.input_hash,
                generated_at=generated_at,
                warnings=tuple(sorted(warnings)),
                errors=errors,
                points=points,
            )
        )
    required = [row for row in results if row.scope.required]
    return ForecastOutput(
        run_id=run_id or uuid4(),
        input_hash=inputs.input_hash,
        data_cutoff_date=inputs.data_cutoff_date,
        generated_at=generated_at,
        completed_at=datetime.now(UTC),
        ready_for_publication=bool(required) and all(row.status == "AVAILABLE" for row in required),
        partial_scope=any(not row.scope.required and row.status != "AVAILABLE" for row in results),
        actual_providers=tuple(
            sorted({row.actual_provider.name for row in results if row.actual_provider is not None})
        ),
        warnings=tuple(sorted({warning for row in results for warning in row.warnings})),
        series=tuple(results),
    )


def reusable_result(inputs: ForecastInput, saved: ForecastOutput) -> ForecastOutput | None:
    """Pure reuse eligibility; future repository must implement atomic lookup/admission.

    Return the original object and its original timestamps/provider/fallback metadata.
    The repository must separately require committed publication before reuse.
    Callers implementing forced refresh bypass this function. No in-memory cache or
    inference is performed here.
    """
    inputs = validate_input(inputs)
    if saved.input_hash != inputs.input_hash or not saved.ready_for_publication:
        return None
    validate_output(inputs, saved)
    return saved
