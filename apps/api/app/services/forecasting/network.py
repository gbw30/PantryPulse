"""Network forecasts through forecast.v1 (W3-F03).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from uuid import UUID

from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_networks import NetworkForecastRequest
from app.services.v1_errors import NotImplementedV1


def submit_network_forecast(
    rt, scope, network_id: UUID, request: NetworkForecastRequest, idempotency_key: str
) -> ForecastAccepted:
    raise NotImplementedV1("W3-F03")
