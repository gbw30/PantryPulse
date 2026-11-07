"""Enrichment status, retry, manual attributes, EGP blockers (W1-D06) and routes (W1-D07).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from uuid import UUID

from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_enrichment import (
    EgpBlocker,
    EnrichmentStatus,
    LocationAttributes,
    LocationAttributesUpdate,
    RouteList,
)
from app.services.v1_errors import NotImplementedV1


def enrichment_status(rt, scope, network_id: UUID) -> EnrichmentStatus:
    raise NotImplementedV1("W1-D06")


def retry_enrichment(rt, scope, network_id: UUID, idempotency_key: str) -> ForecastAccepted:
    raise NotImplementedV1("W1-D06")


def set_location_attributes(
    rt, scope, network_id: UUID, location_id: str, update: LocationAttributesUpdate
) -> LocationAttributes:
    raise NotImplementedV1("W1-D06")


def egp_blockers(rt, network_id: UUID, dataset_version_id: UUID) -> list[EgpBlocker]:
    raise NotImplementedV1("W1-D06")


def list_routes(rt, scope, network_id: UUID) -> RouteList:
    raise NotImplementedV1("W1-D07")
