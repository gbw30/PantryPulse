from collections.abc import Sequence
from datetime import date, timedelta
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
        return self.predict_values(
            values,
            cutoff=inputs.data_cutoff_date,
            window_days=inputs.policy.sparse_window_days,
            min_samples=inputs.policy.sparse_min_samples,
        )

    def predict_values(
        self,
        values: Sequence[float | None],
        *,
        cutoff: date,
        window_days: int = 14,
        min_samples: int = 3,
    ) -> tuple[ForecastPoint, ...]:
        """Exact mean of observed values in an explicit trailing calendar window.

        Defaults here describe the frozen offline experiment; production predict()
        always passes its explicitly selected policy values.
        """
        if (
            type(window_days) is not int
            or type(min_samples) is not int
            or (not 1 <= min_samples <= window_days <= 366)
        ):
            raise ValueError("Invalid explicit sparse-history policy")
        observed = [value for value in values[-window_days:] if value is not None]
        if len(observed) < min_samples:
            raise ProviderError("INSUFFICIENT_DATA", "Too few observed values in sparse window")
        # Sum decimal representations exactly and convert only the final mean.
        # Per-value float division can turn a constant 29 into 29.000000000000004,
        # which creates an extra whole unit when planning applies its daily ceiling.
        # Rational arithmetic also avoids overflow when summing finite large values.
        mean = float(sum(Fraction(str(value)) for value in observed) / len(observed))
        return tuple(
            ForecastPoint(
                day=cutoff + timedelta(days=offset),
                central_estimate=mean,
                estimate_kind="MEAN",
            )
            for offset in range(1, 8)
        )
