"""Network reads: each network with its latest dataset version (W1-D05)."""

from uuid import UUID

import sqlalchemy as sa

from app.repositories.jobs import TrustedScope
from app.services.presenter_access import AccessError

# The version's import uploaded inbound.csv (even header-only), so "no deliveries" is data, not a
# blank. One definition for the network reads and the frozen scenario (`v` = dataset_versions).
INBOUND_FILE_PROVIDED = (
    "EXISTS (SELECT 1 FROM import_runs r, jsonb_array_elements(r.files) f "
    "WHERE r.id = v.import_run_id AND f ->> 'name' = 'inbound')")

_NETWORKS = sa.text(
    "SELECT n.id, n.name, n.mode, n.timezone, n.is_sample, v.id AS dataset_version_id, "
    "v.as_of_date, "
    "(SELECT count(*) FROM net_locations l WHERE l.dataset_version_id = v.id) AS location_count, "
    "(SELECT count(*) FROM net_products p WHERE p.dataset_version_id = v.id) AS product_count, "
    f"CASE WHEN v.id IS NULL THEN NULL ELSE {INBOUND_FILE_PROVIDED} END "
    "AS inbound_file_provided FROM networks n LEFT JOIN LATERAL (SELECT id, as_of_date, "
    "import_run_id FROM dataset_versions WHERE network_id = n.id "
    "ORDER BY recorded_at DESC, id LIMIT 1) v ON true "
    "WHERE CAST(:id AS uuid) IS NULL OR n.id = :id ORDER BY n.is_sample DESC, n.name, n.id"
)


def networks(conn: sa.Connection, network_id: UUID | None = None) -> list[sa.Row]:
    return list(conn.execute(_NETWORKS, {"id": network_id}).all())


def inbound_file_provided(conn: sa.Connection, version_id: UUID) -> bool:
    return conn.scalar(sa.text(
        f"SELECT {INBOUND_FILE_PROVIDED} FROM dataset_versions v WHERE v.id = :v"),
        {"v": version_id})


def network_organization(conn: sa.Connection, network_id: UUID) -> UUID:
    """The one tenancy rule (W0-network-model §2): a network's rows and jobs are under its own
    organization; the client never names it. 404 if there is no such network."""
    organization = conn.scalar(sa.text("SELECT organization_id FROM networks WHERE id = :n"),
                               {"n": network_id})
    if organization is None:
        raise AccessError("NETWORK_NOT_FOUND", 404)
    return organization


def network_scope(conn: sa.Connection, scope: TrustedScope, network_id: UUID) -> TrustedScope:
    """The network's organization, acting as the session's actor."""
    return TrustedScope(network_organization(conn, network_id), scope.actor_ref)
