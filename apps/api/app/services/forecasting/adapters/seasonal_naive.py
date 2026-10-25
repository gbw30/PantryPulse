from collections.abc import Sequence
from datetime import date, timedelta

from ..schemas import ForecastInput, ForecastPoint, PreparedSeries, ProviderIdentity
from .base import ProviderError


class SeasonalNaiveAdapter:
    identity = ProviderIdentity(name="SEASONAL_NAIVE")

    def predict(self, series: PreparedSeries, inputs: ForecastInput) -> tuple[ForecastPoint, ...]:
        observed = {row.day: row.value for row in series.observations if not row.is_missing}
        return self.predict_values(
            tuple(
                observed.get(inputs.data_cutoff_date - timedelta(days=i)) for i in range(6, -1, -1)
            ),
            cutoff=inputs.data_cutoff_date,
        )

    def predict_values(
        self, values: Sequence[float | None], *, cutoff: date
    ) -> tuple[ForecastPoint, ...]:
        """The same weekly baseline for a source-native, gap-explicit offline window."""
        if len(values) < 7:
            raise ProviderError("INSUFFICIENT_DATA", "A required prior weekday is missing")
        points = []
        for offset, value in enumerate(values[-7:], 1):
            day = cutoff + timedelta(days=offset)
            if value is None:
                raise ProviderError("INSUFFICIENT_DATA", "A required prior weekday is missing")
            points.append(ForecastPoint(day=day, central_estimate=value, estimate_kind="POINT"))
        return tuple(points)
