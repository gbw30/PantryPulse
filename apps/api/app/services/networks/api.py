"""Network reads and scenario creation (W1-D05, W1-D09).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from uuid import UUID

from app.schemas.v1_networks import Network, NetworkList
from app.schemas.v1_planning import ScenarioOptions, ScenarioV3
from app.services.v1_errors import NotImplementedV1


def list_networks(rt, scope) -> NetworkList:
    raise NotImplementedV1("W1-D05")


def get_network(rt, scope, network_id: UUID) -> Network:
    raise NotImplementedV1("W1-D05")


def create_scenario(rt, scope, network_id: UUID, options: ScenarioOptions) -> ScenarioV3:
    raise NotImplementedV1("W1-D09")
