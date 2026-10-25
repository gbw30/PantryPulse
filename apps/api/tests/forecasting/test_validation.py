from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.services.forecasting.adapters.base import ProviderError
from app.services.forecasting.postprocessing import validate_points
from app.services.forecasting.schemas import ForecastPoint, ProviderIdentity, SeriesScope
from app.services.forecasting.service import forecast

from .conftest import KEY
from .test_core import frozen
from .test_receipts import receipt


@pytest.mark.parametrize(
    "fields",
    [
        {"central_estimate": -1},
        {"central_estimate": float("inf")},
        {"p10": 5, "p90": 2, "interval_method": "MODEL_QUANTILES"},
        {"p50": 2},
        {"estimate_kind": "MEDIAN"},
    ],
)
def test_bad_output_rejected(fields):
    with pytest.raises(ValidationError):
        ForecastPoint(
            **{"day": "2026-10-24", "central_estimate": 3, "estimate_kind": "MEAN", **fields}
        )


def test_dates_must_be_exact_and_mean_is_independent_of_median(history, policy):
    inputs = frozen(history(), policy)
    points = tuple(
        ForecastPoint(
            day=inputs.data_cutoff_date + timedelta(days=i),
            central_estimate=4,
            estimate_kind="MEAN",
            p10=1,
            p50=3,
            p90=5,
            interval_method="MODEL_QUANTILES",
        )
        for i in range(1, 8)
    )
    assert validate_points(points, inputs) == points
    for bad in (points[:-1], (*points[:-1], points[0])):
        with pytest.raises(ProviderError, match="seven unique"):
            validate_points(bad, inputs)


class BrokenAdapter:
    identity = ProviderIdentity(name="TEST_PROVIDER")

    def predict(self, series, inputs):
        raise RuntimeError("programming error should not become a successful baseline")


class InvalidOutputAdapter:
    identity = ProviderIdentity(name="TEST_PROVIDER")

    def predict(self, series, inputs):
        return (
            ForecastPoint.model_construct(
                day=inputs.data_cutoff_date,
                central_estimate=-10,
                estimate_kind="POINT",
            ),
        )


def test_invalid_provider_output_only_falls_back_with_permission(history, policy):
    blocked = forecast(frozen(history(), policy), adapter=InvalidOutputAdapter())
    assert blocked.series[0].errors[0].code == "INVALID_PROVIDER_OUTPUT"
    allowed = forecast(
        frozen(history(), policy, allow_fallback=True), adapter=InvalidOutputAdapter()
    )
    assert allowed.series[0].actual_provider.name == "MOVING_AVERAGE"
    assert allowed.series[0].fallback_reason == "INVALID_PROVIDER_OUTPUT"


def test_programming_errors_do_not_fall_back(history, policy):
    with pytest.raises(RuntimeError):
        forecast(frozen(history(), policy, allow_fallback=True), adapter=BrokenAdapter())


def test_optional_failure_is_disclosed_and_required_failure_blocks(history, policy):
    bundle = history()
    optional_key = KEY.model_copy(update={"target_type": "DONATION"})
    optional = SeriesScope(
        key=optional_key, unit="meal", timezone="America/New_York", required=False
    )
    bundle = bundle.model_copy(update={"scope": (*bundle.scope, optional)})
    result = forecast(frozen(bundle, policy))
    assert result.ready_for_publication and result.partial_scope
    assert {row.status for row in result.series} == {"AVAILABLE", "INSUFFICIENT_DATA"}
    bundle = bundle.model_copy(
        update={"scope": (*bundle.scope[:1], optional.model_copy(update={"required": True}))}
    )
    assert not forecast(frozen(bundle, policy)).ready_for_publication


def test_mixed_provider_summary_retains_per_series_outcomes(history, policy):
    from .conftest import CUTOFF

    bundle = history(
        receipts=tuple(receipt(f"event:{i}", 3, day=CUTOFF - timedelta(days=i)) for i in (0, 2, 8))
    )
    donation = KEY.model_copy(update={"target_type": "DONATION"})
    bundle = bundle.model_copy(
        update={
            "scope": (
                *bundle.scope,
                SeriesScope(
                    key=donation,
                    unit="meal",
                    timezone="America/New_York",
                ),
            ),
        }
    )
    inputs = frozen(bundle, policy, allow_fallback=True)
    result = forecast(inputs)
    assert result.ready_for_publication and not result.partial_scope
    assert result.actual_providers == ("MOVING_AVERAGE", "SEASONAL_NAIVE")
    assert next(row for row in result.series if row.scope.key == donation).fallback_used
