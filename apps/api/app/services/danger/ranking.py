"""Danger ranking per location, driven by one product (W3-F05).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from uuid import UUID

from app.schemas.v1_networks import DangerRanking, DangerRow
from app.schemas.v1_planning import NetworkMode
from app.services.v1_errors import NotImplementedV1


def danger_ranking(projection, mode: NetworkMode) -> list[DangerRow]:
    raise NotImplementedV1("W3-F05")


def get_danger(rt, scope, network_id: UUID, forecast_run_id: UUID) -> DangerRanking:
    raise NotImplementedV1("W3-F05")
