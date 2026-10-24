from datetime import timedelta
from math import fsum

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
        # Divide before summing to avoid overflow for finite large observations.
        mean = fsum(value / len(values) for value in values)
        return tuple(
            ForecastPoint(
                day=inputs.data_cutoff_date + timedelta(days=offset),
                central_estimate=mean,
                estimate_kind="MEAN",
            )
            for offset in range(1, 8)
        )
