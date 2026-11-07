"""Enrichment status, retry, manual attributes, EGP blockers (W1-D06) and routes (W1-D07).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from uuid import UUID

import sqlalchemy as sa

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
from app.services.enrichment import service
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
    """A manual value for both rates, or an explicit exclusion from EGP, on the latest version.
    Looked-up values stay in their own columns, so the source of each stays visible."""
    with rt.engine.begin() as conn:
        version_id = _latest_version(conn, network_id)
        values = ({"poverty": None, "snap": None, "excluded": True,
                   "reason": "excluded from EGP by the user"} if update.excluded else
                  {"poverty": update.poverty_rate, "snap": update.snap_rate, "excluded": False,
                   "reason": None})
        changed = conn.execute(sa.text(
            "UPDATE net_locations SET manual_poverty_rate = coalesce(:poverty, "
            "manual_poverty_rate), manual_snap_rate = coalesce(:snap, manual_snap_rate), "
            "excluded = :excluded, exclusion_reason = :reason "
            "WHERE dataset_version_id = :v AND external_id = :e"),
            {**values, "v": version_id, "e": location_id}).rowcount
        if not changed:
            raise AccessError("LOCATION_NOT_FOUND", 404)
        [attributes] = service.location_attributes(conn, version_id, location_id)
    return attributes


def egp_blockers(rt, network_id: UUID, dataset_version_id: UUID) -> list[EgpBlocker]:
    with rt.engine.connect() as conn:
        if not conn.scalar(sa.text("SELECT 1 FROM dataset_versions WHERE id = :v AND "
                                   "network_id = :n"), {"v": dataset_version_id, "n": network_id}):
            raise AccessError("DATASET_VERSION_NOT_FOUND", 404)
        found = service.blockers(conn, dataset_version_id)
    return [EgpBlocker(location_id=location_id, missing=missing) for location_id, missing in found]


def _latest_version(conn: sa.Connection, network_id: UUID) -> UUID:
    found = networks_repo.networks(conn, network_id)
    if not found:
        raise AccessError("NETWORK_NOT_FOUND", 404)
    return found[0].dataset_version_id


def list_routes(rt, scope, network_id: UUID) -> RouteList:
    """The latest dataset version's routes, with the API method label."""
    with rt.engine.connect() as conn:
        version_id = _latest_version(conn, network_id)
        rows = repo.routes(conn, version_id)
    return RouteList(network_id=network_id, dataset_version_id=version_id, routes=tuple(
        RouteEntry(**{**r._mapping, "method": DB_TO_API[r.method]}) for r in rows))
