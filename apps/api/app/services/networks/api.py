"""Network reads (W1-D05) and scenario creation (W1-D09).

The local session may read every network of the install (W0-network-model §2). A failed
first import leaves no networks row, so it never appears here.
"""

from uuid import UUID, uuid4

import sqlalchemy as sa

from app.repositories import networks as repo
from app.schemas.v1_networks import Network, NetworkList
from app.schemas.v1_planning import ScenarioOptions, ScenarioV3
from app.services.networks.scenario import build_scenario
from app.services.optimization.canonical import operational_hash
from app.services.presenter_access import AccessError


def list_networks(rt, scope) -> NetworkList:
    with rt.engine.connect() as conn:
        return NetworkList(networks=tuple(Network(**row._mapping) for row in repo.networks(conn)))


def get_network(rt, scope, network_id: UUID) -> Network:
    with rt.engine.connect() as conn:
        rows = repo.networks(conn, network_id)
    if not rows:
        raise AccessError("NETWORK_NOT_FOUND", 404)
    return Network(**rows[0]._mapping)


def create_scenario(rt, scope, network_id: UUID, options: ScenarioOptions) -> ScenarioV3:
    """Freeze the network's latest version and a forecast run into an immutable scenario."""
    with rt.engine.begin() as conn:
        rows = repo.networks(conn, network_id)
        if not rows:
            raise AccessError("NETWORK_NOT_FOUND", 404)
        payload = build_scenario(conn, rows[0], options)
        content_hash = operational_hash(payload)
        row = conn.execute(sa.text(
            "INSERT INTO planning_scenarios_v3 (id, organization_id, network_id, "
            "dataset_version_id, forecast_run_id, content_hash, payload) VALUES (:id, :org, "
            ":net, :ver, :run, :hash, CAST(:payload AS jsonb)) RETURNING id, recorded_at"),
            {"id": uuid4(), "org": payload.organization_id, "net": network_id,
             "ver": payload.dataset_version_id, "run": payload.forecast_run_id,
             "hash": content_hash, "payload": payload.model_dump_json()}).one()
    return ScenarioV3(id=row.id, network_id=network_id, recorded_at=row.recorded_at,
                      content_hash=content_hash, payload=payload)
