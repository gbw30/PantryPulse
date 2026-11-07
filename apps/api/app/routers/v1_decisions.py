"""v1 comparisons (or-comparison.v3), decision actions and plan export, scoped to a network."""

from uuid import UUID

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from app.routers.v1_common import KEY, PRESENTER, RESPONSES, RUNTIME, job_accepted
from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_planning import (
    AllocationMethod,
    ComparisonRequestV3,
    DecisionActions,
    ExportRequest,
    SavedComparisonV3,
)
from app.services.optimization import api_v3

router = APIRouter(prefix="/api/v1", tags=["v1-decisions"], responses=RESPONSES)
BASE = "/networks/{network_id}/comparisons"


@router.post(BASE, response_model=ForecastAccepted, status_code=202)
def submit_comparison(
    network_id: UUID,
    body: ComparisonRequestV3,
    response: Response,
    idempotency_key: KEY,
    rt=RUNTIME,
    scope=PRESENTER,
):
    accepted = api_v3.submit_comparison(rt, scope, network_id, body, idempotency_key)
    return job_accepted(response, accepted)


@router.get(BASE + "/{comparison_id}", response_model=SavedComparisonV3)
def get_comparison(network_id: UUID, comparison_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return api_v3.get_comparison(rt, scope, network_id, comparison_id)


@router.get(BASE + "/{comparison_id}/methods/{method}/actions", response_model=DecisionActions)
def actions(
    network_id: UUID, comparison_id: UUID, method: AllocationMethod, rt=RUNTIME, scope=PRESENTER
):
    return api_v3.comparison_actions(rt, scope, network_id, comparison_id, method)


@router.post(
    BASE + "/{comparison_id}/methods/{method}/export",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
def export(
    network_id: UUID,
    comparison_id: UUID,
    method: AllocationMethod,
    body: ExportRequest,
    rt=RUNTIME,
    scope=PRESENTER,
):
    csv = api_v3.export_comparison(rt, scope, network_id, comparison_id, method, body.action_ids)
    return PlainTextResponse(csv, media_type="text/csv")
