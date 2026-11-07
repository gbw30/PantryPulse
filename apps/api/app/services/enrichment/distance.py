"""Straight-line candidate routes and travel days (W1-D07).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from collections.abc import Sequence
from decimal import Decimal

from app.schemas.v1_enrichment import CandidateRoute, GeoLocation
from app.services.v1_errors import NotImplementedV1


def candidate_routes(
    locations: Sequence[GeoLocation],
    k: int = 10,
    radius_miles: int = 150,
    road_factor: Decimal = Decimal("1.3"),
    mph: int = 45,
) -> list[CandidateRoute]:
    raise NotImplementedV1("W1-D07")


def travel_days(road_miles: Decimal, mph: int = 45) -> int:
    """max(1, ceil(road_hours / 24)), confirmed by Gabriel 2026-11-04."""
    raise NotImplementedV1("W1-D07")
