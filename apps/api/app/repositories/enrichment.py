"""Enrichment reads: a dataset version's stored routes (W1-D07)."""

from uuid import UUID

import sqlalchemy as sa

_ROUTES = sa.text(
    "SELECT f.external_id AS from_location_id, t.external_id AS to_location_id, "
    "r.distance_miles AS road_miles, r.travel_days, r.method, r.fetched_at, "
    "r.is_override AS override, r.disabled FROM net_routes r "
    "JOIN net_locations f ON f.id = r.from_location_id "
    "JOIN net_locations t ON t.id = r.to_location_id "
    "WHERE r.dataset_version_id = :v ORDER BY f.external_id, t.external_id"
)


def routes(conn: sa.Connection, dataset_version_id: UUID) -> list[sa.Row]:
    return list(conn.execute(_ROUTES, {"v": dataset_version_id}).all())
