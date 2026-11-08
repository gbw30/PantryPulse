"""Network forecasts through forecast.v1 (W3-F03).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from uuid import UUID

from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_networks import ForecastRunList, NetworkForecastRequest, NetworkForecastRun
from app.services.v1_errors import NotImplementedV1


def submit_network_forecast(
    rt, scope, network_id: UUID, request: NetworkForecastRequest, idempotency_key: str
) -> ForecastAccepted:
    raise NotImplementedV1("W3-F03")


def list_forecast_runs(rt, scope, network_id: UUID) -> ForecastRunList:
    """The network's forecast.v1 jobs, newest first (CR-w1-web-2)."""
    raise NotImplementedV1("W3-F03")


def get_forecast_run(rt, scope, network_id: UUID, forecast_run_id: UUID) -> NetworkForecastRun:
    """A published network run's series by CSV ids (CR-w1-web-4)."""
    raise NotImplementedV1("W3-F03")
