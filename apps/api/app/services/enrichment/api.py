"""Enrichment status, retry, manual attributes, EGP blockers (W1-D06) and routes (W1-D07).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from uuid import UUID

from app.repositories import enrichment as repo
from app.repositories import networks as networks_repo
from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_enrichment import (
    EgpBlocker,
    EnrichmentStatus,
    LocationAttributes,
    LocationAttributesUpdate,
    RouteEntry,
    RouteList,
)
from app.services.enrichment.distance import DB_TO_API
from app.services.presenter_access import AccessError
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
    """The latest dataset version's routes, with the API method label."""
    with rt.engine.connect() as conn:
        found = networks_repo.networks(conn, network_id)
        if not found:
            raise AccessError("NETWORK_NOT_FOUND", 404)
        version_id = found[0].dataset_version_id
        rows = repo.routes(conn, version_id)
    return RouteList(network_id=network_id, dataset_version_id=version_id, routes=tuple(
        RouteEntry(**{**r._mapping, "method": DB_TO_API[r.method]}) for r in rows))
