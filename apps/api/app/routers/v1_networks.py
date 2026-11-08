"""v1 network routes: networks, templates, scenarios, forecasts, backtest and danger ranking."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from app.routers.v1_common import KEY, PRESENTER, RESPONSES, RUNTIME, job_accepted
from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_networks import (
    BacktestResult,
    DangerRanking,
    ForecastRunList,
    LocationList,
    LocationProjection,
    Network,
    NetworkForecastRequest,
    NetworkForecastRun,
    NetworkList,
    TemplateCatalog,
    TemplateName,
)
from app.schemas.v1_planning import NetworkMode, ScenarioOptions, ScenarioV3
from app.services.danger import ranking
from app.services.forecasting import backtest, network
from app.services.imports import templates
from app.services.networks import api, locations

router = APIRouter(prefix="/api/v1", tags=["v1-networks"], responses=RESPONSES)
CSV = {200: {"content": {"text/csv": {}}}}


@router.get("/networks", response_model=NetworkList)
def list_networks(rt=RUNTIME, scope=PRESENTER):
    return api.list_networks(rt, scope)


@router.get("/networks/{network_id}", response_model=Network)
def get_network(network_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return api.get_network(rt, scope, network_id)


@router.get("/networks/{network_id}/locations", response_model=LocationList)
def list_locations(network_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return locations.list_locations(rt, scope, network_id)


@router.get("/templates", response_model=TemplateCatalog)
def template_catalog(mode: NetworkMode | None = None, scope=PRESENTER):
    return templates.template_catalog(mode)


@router.get("/templates/{name}.csv", response_class=PlainTextResponse, responses=CSV)
def template_csv(name: TemplateName, kind: Literal["blank", "example"] = "blank", scope=PRESENTER):
    return PlainTextResponse(templates.template_csv(name, kind), media_type="text/csv")


@router.post("/networks/{network_id}/scenarios", response_model=ScenarioV3, status_code=201)
def create_scenario(network_id: UUID, body: ScenarioOptions, rt=RUNTIME, scope=PRESENTER):
    return api.create_scenario(rt, scope, network_id, body)


@router.post(
    "/networks/{network_id}/forecasts", response_model=ForecastAccepted, status_code=202
)
def submit_forecast(
    network_id: UUID,
    body: NetworkForecastRequest,
    response: Response,
    idempotency_key: KEY,
    rt=RUNTIME,
    scope=PRESENTER,
):
    accepted = network.submit_network_forecast(rt, scope, network_id, body, idempotency_key)
    return job_accepted(response, accepted)


@router.get("/networks/{network_id}/forecasts", response_model=ForecastRunList)
def list_forecast_runs(network_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return network.list_forecast_runs(rt, scope, network_id)


@router.get(
    "/networks/{network_id}/forecasts/{forecast_run_id}", response_model=NetworkForecastRun
)
def get_forecast_run(network_id: UUID, forecast_run_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return network.get_forecast_run(rt, scope, network_id, forecast_run_id)


@router.get("/forecasts/{job_id}/backtest", response_model=BacktestResult)
def get_backtest(job_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return backtest.get_backtest(rt, scope, job_id)


@router.get("/networks/{network_id}/danger", response_model=DangerRanking)
def get_danger(network_id: UUID, forecast_run_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return ranking.get_danger(rt, scope, network_id, forecast_run_id)


@router.get("/networks/{network_id}/projection", response_model=LocationProjection)
def get_projection(
    network_id: UUID, forecast_run_id: UUID, location_id: str, rt=RUNTIME, scope=PRESENTER
):
    return ranking.get_projection(rt, scope, network_id, forecast_run_id, location_id)
