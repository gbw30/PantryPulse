"""Network reads: each network with its latest dataset version (W1-D05)."""

from uuid import UUID

import sqlalchemy as sa

_NETWORKS = sa.text(
    "SELECT n.id, n.name, n.mode, n.timezone, n.is_sample, v.id AS dataset_version_id, "
    "v.as_of_date, "
    "(SELECT count(*) FROM net_locations l WHERE l.dataset_version_id = v.id) AS location_count, "
    "(SELECT count(*) FROM net_products p WHERE p.dataset_version_id = v.id) AS product_count "
    "FROM networks n LEFT JOIN LATERAL (SELECT id, as_of_date FROM dataset_versions "
    "WHERE network_id = n.id ORDER BY recorded_at DESC, id LIMIT 1) v ON true "
    "WHERE CAST(:id AS uuid) IS NULL OR n.id = :id ORDER BY n.is_sample DESC, n.name, n.id"
)


def networks(conn: sa.Connection, network_id: UUID | None = None) -> list[sa.Row]:
    return list(conn.execute(_NETWORKS, {"id": network_id}).all())


# The version's import uploaded inbound.csv (even header-only), so "no deliveries" is data, not a
# blank. One definition for the network reads and the frozen scenario (`v` = dataset_versions).
INBOUND_FILE_PROVIDED = (
    "EXISTS (SELECT 1 FROM import_runs r, jsonb_array_elements(r.files) f "
    "WHERE r.id = v.import_run_id AND f ->> 'name' = 'inbound')")


def inbound_file_provided(conn: sa.Connection, version_id: UUID) -> bool:
    return conn.scalar(sa.text(
        f"SELECT {INBOUND_FILE_PROVIDED} FROM dataset_versions v WHERE v.id = :v"),
        {"v": version_id})
