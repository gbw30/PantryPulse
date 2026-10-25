from datetime import timedelta
from fractions import Fraction

from ..schemas import ForecastInput, ForecastPoint, PreparedSeries, ProviderIdentity
from .base import ProviderError


class MovingAverageAdapter:
    identity = ProviderIdentity(name="MOVING_AVERAGE")

    def predict(self, series: PreparedSeries, inputs: ForecastInput) -> tuple[ForecastPoint, ...]:
        start = inputs.data_cutoff_date - timedelta(days=inputs.policy.sparse_window_days)
        values = [
            row.value
            for row in series.observations
            if start < row.day <= inputs.data_cutoff_date and row.value is not None
        ]
        if len(values) < inputs.policy.sparse_min_samples:
            raise ProviderError("INSUFFICIENT_DATA", "Too few observed values in sparse window")
        # Sum decimal representations exactly and convert only the final mean.
        # Per-value float division can turn a constant 29 into 29.000000000000004,
        # which creates an extra whole unit when planning applies its daily ceiling.
        # Rational arithmetic also avoids overflow when summing finite large values.
        mean = float(sum(Fraction(str(value)) for value in values) / len(values))
        return tuple(
            ForecastPoint(
                day=inputs.data_cutoff_date + timedelta(days=offset),
                central_estimate=mean,
                estimate_kind="MEAN",
            )
            for offset in range(1, 8)
        )
