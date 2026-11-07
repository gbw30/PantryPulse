"""Location read for the atlas (CR-w1-web-1, lead-built): the latest dataset version's rows.

The local session may read every network of the install (W0-network-model §2).
"""

from uuid import UUID

import sqlalchemy as sa

from app.schemas.v1_networks import LocationList, LocationSummary
from app.services.presenter_access import AccessError

_LATEST = sa.text(
    "SELECT v.id FROM networks n LEFT JOIN LATERAL (SELECT id FROM dataset_versions "
    "WHERE network_id = n.id ORDER BY recorded_at DESC, id LIMIT 1) v ON true WHERE n.id = :n"
)
_LOCATIONS = sa.text(
    "SELECT external_id AS location_id, name, role, city, state, latitude, longitude, "
    "coordinates_source FROM net_locations WHERE dataset_version_id = :v ORDER BY external_id"
)


def list_locations(rt, scope, network_id: UUID) -> LocationList:
    with rt.engine.connect() as conn:
        version = conn.execute(_LATEST, {"n": network_id}).one_or_none()
        if version is None or version.id is None:  # a network row exists only after an import
            raise AccessError("NETWORK_NOT_FOUND", 404)
        rows = conn.execute(_LOCATIONS, {"v": version.id}).mappings().all()
    return LocationList(
        network_id=network_id,
        dataset_version_id=version.id,
        locations=tuple(LocationSummary(**row) for row in rows),
    )
