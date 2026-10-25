from datetime import timedelta

from ..schemas import ForecastInput, ForecastPoint, PreparedSeries, ProviderIdentity
from .base import ProviderError


class SeasonalNaiveAdapter:
    identity = ProviderIdentity(name="SEASONAL_NAIVE")

    def predict(self, series: PreparedSeries, inputs: ForecastInput) -> tuple[ForecastPoint, ...]:
        observed = {row.day: row.value for row in series.observations if not row.is_missing}
        points = []
        for offset in range(1, 8):
            day = inputs.data_cutoff_date + timedelta(days=offset)
            reference = day - timedelta(days=7)
            value = observed.get(reference)
            if value is None:
                raise ProviderError("INSUFFICIENT_DATA", "A required prior weekday is missing")
            points.append(ForecastPoint(day=day, central_estimate=value, estimate_kind="POINT"))
        return tuple(points)
