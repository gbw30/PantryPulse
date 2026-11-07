"""Straight-line candidate routes, travel days and routes.csv overrides (W1-D07)."""

import math
from collections.abc import Sequence
from decimal import ROUND_CEILING, Decimal
from typing import Any

from app.schemas.v1_enrichment import CandidateRoute, GeoLocation
from app.services.imports.validate import ParsedRoute

EARTH_RADIUS_MILES = 3958.8
MILES = Decimal("0.001")
SENDER_ONLY = frozenset({"hub", "distribution_center"})  # they never receive transfers
API_TO_DB = {"straight_line_estimate": "straight_line", "google_road": "google",
             "routes_csv": "user"}
DB_TO_API = {db: api for api, db in API_TO_DB.items()}


def haversine_miles(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> Decimal:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return Decimal(2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))).quantize(MILES)


def travel_days(road_miles: Decimal, mph: int = 45) -> int:
    """max(1, ceil(road_hours / 24)), confirmed by Gabriel 2026-11-04."""
    return max(1, int((road_miles / (mph * 24)).to_integral_value(ROUND_CEILING)))


def _route(source: GeoLocation, target: GeoLocation, road_factor: Decimal,
           mph: int) -> CandidateRoute:
    straight = haversine_miles(source.latitude, source.longitude, target.latitude,
                               target.longitude)
    road = (straight * road_factor).quantize(MILES)
    return CandidateRoute(from_location_id=source.id, to_location_id=target.id,
                          straight_miles=straight, road_miles=road,
                          travel_days=travel_days(road, mph), method="straight_line_estimate")


def candidate_routes(
    locations: Sequence[GeoLocation],
    k: int = 10,
    radius_miles: int = 150,
    road_factor: Decimal = Decimal("1.3"),
    mph: int = 45,
) -> list[CandidateRoute]:
    """Each receiver's k nearest senders within radius_miles (straight line), nearest first."""
    routes: list[CandidateRoute] = []
    for target in locations:
        if target.role in SENDER_ONLY:
            continue
        near = sorted((r for r in (_route(s, target, road_factor, mph)
                                   for s in locations if s.id != target.id)
                       if r.straight_miles <= radius_miles),
                      key=lambda r: (r.straight_miles, r.from_location_id))
        routes.extend(near[:k])
    return routes


def route_rows(locations: Sequence[GeoLocation],
               overrides: Sequence[ParsedRoute]) -> list[dict[str, Any]]:
    """net_routes rows: the candidates, with each routes.csv row applied on top.

    A blank routes.csv travel_days overrides nothing, so the estimate and its label stay; the
    validator rejects such a row when either end has no coordinates."""
    rows = {(r.from_location_id, r.to_location_id): _row(r)
            for r in candidate_routes(locations)}
    by_id = {loc.id: loc for loc in locations}
    for o in overrides:
        pair = (o.from_location_id, o.to_location_id)
        row = rows.get(pair)
        if row is None and pair[0] in by_id and pair[1] in by_id:
            row = _row(_route(by_id[pair[0]], by_id[pair[1]], Decimal("1.3"), 45))
        if row is None:  # given travel_days, unlocated ends: no distance known
            row = {"from": pair[0], "to": pair[1], "distance_miles": None, "road_hours": None}
        if o.travel_days is not None:
            row.update(method="user", travel_days=o.travel_days)
        row.update(cost=o.cost_per_handling_unit, capacity=o.capacity_per_batch,
                   is_override=True, disabled=o.disabled)
        rows[pair] = row
    return list(rows.values())


def _row(route: CandidateRoute, mph: int = 45) -> dict[str, Any]:
    return {"from": route.from_location_id, "to": route.to_location_id,
            "method": API_TO_DB[route.method], "distance_miles": route.road_miles,
            "road_hours": (route.road_miles / mph).quantize(MILES),
            "travel_days": route.travel_days, "cost": None, "capacity": None,
            "is_override": False, "disabled": False}
