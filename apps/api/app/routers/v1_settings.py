"""v1 enrichment, routes and local settings. The Google key is write-only."""

from uuid import UUID

from fastapi import APIRouter, Response

from app.routers.v1_common import KEY, PRESENTER, RESPONSES, RUNTIME, job_accepted
from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_enrichment import (
    EnrichmentStatus,
    GoogleKey,
    GoogleLookupPreview,
    LocalSettings,
    LocationAttributes,
    LocationAttributesUpdate,
    RouteList,
)
from app.services.enrichment import api, google, settings

router = APIRouter(prefix="/api/v1", tags=["v1-settings"], responses=RESPONSES)


@router.get("/networks/{network_id}/enrichment", response_model=EnrichmentStatus)
def enrichment_status(network_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return api.enrichment_status(rt, scope, network_id)


@router.post(
    "/networks/{network_id}/enrichment/retry", response_model=ForecastAccepted, status_code=202
)
def retry_enrichment(
    network_id: UUID, response: Response, idempotency_key: KEY, rt=RUNTIME, scope=PRESENTER
):
    return job_accepted(response, api.retry_enrichment(rt, scope, network_id, idempotency_key))


@router.put(
    "/networks/{network_id}/locations/{location_id}/attributes", response_model=LocationAttributes
)
def set_attributes(
    network_id: UUID, location_id: str, body: LocationAttributesUpdate, rt=RUNTIME, scope=PRESENTER
):
    return api.set_location_attributes(rt, scope, network_id, location_id, body)


@router.get("/networks/{network_id}/routes", response_model=RouteList)
def list_routes(network_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return api.list_routes(rt, scope, network_id)


@router.post("/networks/{network_id}/routes/google-preview", response_model=GoogleLookupPreview)
def google_preview(network_id: UUID, rt=RUNTIME, scope=PRESENTER):
    return google.preview_lookups(rt, scope, network_id)


@router.post(
    "/networks/{network_id}/routes/google-fetch", response_model=ForecastAccepted, status_code=202
)
def google_fetch(
    network_id: UUID, response: Response, idempotency_key: KEY, rt=RUNTIME, scope=PRESENTER
):
    return job_accepted(response, google.fetch_routes(rt, scope, network_id, idempotency_key))


@router.get("/settings", response_model=LocalSettings)
def get_settings(rt=RUNTIME, scope=PRESENTER):
    return settings.get_settings(rt)


@router.put("/settings/google-maps-key", response_model=LocalSettings)
def set_google_key(body: GoogleKey, rt=RUNTIME, scope=PRESENTER):
    return settings.set_google_key(rt, body.key)


@router.delete("/settings/google-maps-key", response_model=LocalSettings)
def delete_google_key(rt=RUNTIME, scope=PRESENTER):
    return settings.delete_google_key(rt)
