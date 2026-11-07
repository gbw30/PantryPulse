"""Network reads (W1-D05) and scenario creation (W1-D09).

The local session may read every network of the install (W0-network-model §2). A failed
first import leaves no networks row, so it never appears here.
"""

from uuid import UUID

from app.repositories import networks as repo
from app.schemas.v1_networks import Network, NetworkList
from app.schemas.v1_planning import ScenarioOptions, ScenarioV3
from app.services.presenter_access import AccessError
from app.services.v1_errors import NotImplementedV1


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
    raise NotImplementedV1("W1-D09")
