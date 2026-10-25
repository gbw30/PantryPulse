"""Fail-closed boundary while actual pinned Chronos qualification remains paused.

No torch/chronos imports, model download, or inference on import. The lockfile
contains chronos-forecasting 2.3.2, but no checkpoint/native gap contract has been
qualified. A future qualified adapter must implement ForecastAdapter and run
inside the controlled executor. A mock is never actual Chronos evidence.
"""

from ..schemas import ForecastInput, ForecastPoint, PreparedSeries, ProviderIdentity
from .base import ProviderError


class Chronos2Adapter:
    identity = ProviderIdentity(name="CHRONOS2", package_version="2.3.2")

    def predict(self, series: PreparedSeries, inputs: ForecastInput) -> tuple[ForecastPoint, ...]:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE",
            "Pinned Chronos checkpoint and native gap handling are unqualified",
        )
