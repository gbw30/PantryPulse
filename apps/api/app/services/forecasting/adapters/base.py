from typing import Protocol

from ..schemas import ForecastInput, ForecastPoint, PreparedSeries, ProviderIdentity


class ProviderError(Exception):
    """Only these safe, classified failures may trigger a provider fallback."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


class ForecastAdapter(Protocol):
    identity: ProviderIdentity

    def predict(
        self, series: PreparedSeries, inputs: ForecastInput
    ) -> tuple[ForecastPoint, ...]: ...
