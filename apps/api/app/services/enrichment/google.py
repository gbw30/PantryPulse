"""Bring-your-own Google key: lookup preview, Routes API client, cache (W1-D08).

S6: Routes API computeRouteMatrix, TRAFFIC_UNAWARE (Essentials SKU), one request per receiver
with its uncached senders as origins, so the preview count is the billed element count.
Results go to the install-wide google_distance_cache and relabel routes as google_road with
their fetch date. routes.csv travel days always win, and a provider error keeps the
straight-line routes. The key travels only in a request header: never in a payload, an
output, an error or a log."""

import json
import math
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from app.repositories import networks as networks_repo
from app.repositories.jobs import TrustedScope
from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_enrichment import GoogleLookupPreview
from app.services.enrichment import settings
from app.services.presenter_access import AccessError

CONTRACT = "routes-google.v1"
ROUTES_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
FIELD_MASK = "originIndex,destinationIndex,status,condition,distanceMeters,duration"
TIMEOUT_S = 30

Point = tuple[Decimal, Decimal]
Transport = Callable[[urllib.request.Request], bytes]


class GoogleUnavailable(Exception):
    """A safe code only (GOOGLE_HTTP_403, GOOGLE_UNAVAILABLE, ...): never the key."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def urlopen_transport(request: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310
        return response.read()


def _waypoint(point: Point) -> dict[str, Any]:
    return {"waypoint": {"location": {"latLng": {"latitude": float(point[0]),
                                                 "longitude": float(point[1])}}}}


class GoogleClient:
    def __init__(self, key: str, transport: Transport = urlopen_transport):
        if not key:
            raise GoogleUnavailable("GOOGLE_KEY_MISSING")
        self._key, self.transport = key, transport

    def distances(self, origins: Sequence[Point],
                  destination: Point) -> list[tuple[int, int] | None]:
        """(meters, seconds) per origin; None where Google found no route."""
        request = urllib.request.Request(
            ROUTES_URL, method="POST",
            data=json.dumps({"origins": [_waypoint(o) for o in origins],
                             "destinations": [_waypoint(destination)], "travelMode": "DRIVE",
                             "routingPreference": "TRAFFIC_UNAWARE"}).encode(),
            headers={"Content-Type": "application/json", "X-Goog-Api-Key": self._key,
                     "X-Goog-FieldMask": FIELD_MASK})
        try:
            raw = self.transport(request)
        except urllib.error.HTTPError as error:  # its message or body may echo the key
            raise GoogleUnavailable(f"GOOGLE_HTTP_{error.code}") from None
        except (OSError, ValueError):
            raise GoogleUnavailable("GOOGLE_UNAVAILABLE") from None
        return self.parse(raw, len(origins), 0)

    @staticmethod
    def parse(raw: bytes, origins: int, destination: int) -> list[tuple[int, int] | None]:
        found: list[tuple[int, int] | None] = [None] * origins
        try:
            for e in json.loads(raw):
                # proto3 JSON leaves out zero values, so a missing index means 0.
                if e.get("destinationIndex", 0) != destination:
                    continue
                if e.get("status") or e.get("condition") != "ROUTE_EXISTS":
                    continue
                found[e.get("originIndex", 0)] = (
                    int(e.get("distanceMeters", 0)),
                    math.ceil(float(e.get("duration", "0s").removesuffix("s"))))
        except (ValueError, TypeError, AttributeError, IndexError):
            raise GoogleUnavailable("GOOGLE_BAD_RESPONSE") from None
        return found


_PAIRS = (
    "SELECT DISTINCT f.latitude AS olat, f.longitude AS olon, t.latitude AS dlat, "
    "t.longitude AS dlon, c.origin_lat IS NOT NULL AS cached FROM net_routes r "
    "JOIN net_locations f ON f.id = r.from_location_id "
    "JOIN net_locations t ON t.id = r.to_location_id "
    "LEFT JOIN google_distance_cache c ON c.origin_lat = f.latitude AND c.origin_lon = "
    "f.longitude AND c.dest_lat = t.latitude AND c.dest_lon = t.longitude "
    # routes.csv travel days ('user') always win; disabled routes need no lookup.
    "WHERE r.dataset_version_id = :v AND r.method <> 'user' AND NOT r.disabled "
    "ORDER BY dlat, dlon, olat, olon")


def _pairs(conn: sa.Connection, version_id: UUID) -> list[sa.Row]:
    return list(conn.execute(sa.text(_PAIRS), {"v": version_id}).all())


def google_input(conn: sa.Connection, version_id: UUID) -> dict[str, Any]:
    """The uncached lookups, one group per receiver (one billed request each)."""
    groups: dict[tuple[str, str], list[list[str]]] = {}
    for p in _pairs(conn, version_id):
        if not p.cached:
            groups.setdefault((str(p.dlat), str(p.dlon)), []).append([str(p.olat), str(p.olon)])
    return {"dataset_version_id": str(version_id),
            "lookups": [[d[0], d[1], origins] for d, origins in groups.items()]}


def google_step(payload: dict[str, Any], client: GoogleClient) -> dict[str, Any]:
    """Runs in the step child. Stops at the first provider error and keeps what it got."""
    results: list[list[Any]] = []
    for dlat, dlon, origins in payload["lookups"]:
        destination = (Decimal(dlat), Decimal(dlon))
        try:
            found = client.distances([(Decimal(a), Decimal(b)) for a, b in origins], destination)
        except GoogleUnavailable as error:
            return {"results": results, "error": error.code}
        results.extend([*origin, dlat, dlon, *value]
                       for origin, value in zip(origins, found, strict=True) if value)
    return {"results": results, "error": None}


def apply_google(conn: sa.Connection, version_id: UUID, step: dict[str, Any],
                 now: datetime) -> None:
    """Cache the new results, then relabel every route with a cached pair as google_road."""
    if step["results"]:
        conn.execute(sa.text(
            "INSERT INTO google_distance_cache VALUES (:olat, :olon, :dlat, :dlon, :meters, "
            ":seconds, :at) ON CONFLICT DO NOTHING"),
            [{"olat": Decimal(r[0]), "olon": Decimal(r[1]), "dlat": Decimal(r[2]),
              "dlon": Decimal(r[3]), "meters": r[4], "seconds": r[5], "at": now}
             for r in step["results"]])
    conn.execute(sa.text(
        "UPDATE net_routes r SET method = 'google', "
        "distance_miles = round(c.distance_meters / 1609.344, 3), "
        "road_hours = round(c.duration_seconds / 3600.0, 3), "
        "travel_days = greatest(1, ceil(c.duration_seconds / 86400.0)), "
        "fetched_at = c.fetched_at "
        "FROM net_locations f, net_locations t, google_distance_cache c "
        "WHERE r.dataset_version_id = :v AND r.method <> 'user' "
        "AND f.id = r.from_location_id AND t.id = r.to_location_id "
        "AND c.origin_lat = f.latitude AND c.origin_lon = f.longitude "
        "AND c.dest_lat = t.latitude AND c.dest_lon = t.longitude"), {"v": version_id})


def _latest(conn: sa.Connection, network_id: UUID) -> sa.Row:
    found = networks_repo.networks(conn, network_id)
    if not found:
        raise AccessError("NETWORK_NOT_FOUND", 404)
    return found[0]


def preview_lookups(rt, scope, network_id: UUID) -> GoogleLookupPreview:
    with rt.engine.connect() as conn:
        pairs = _pairs(conn, _latest(conn, network_id).dataset_version_id)
    cached = sum(1 for p in pairs if p.cached)
    return GoogleLookupPreview(lookups=len(pairs) - cached, cached=cached)


def fetch_routes(rt, scope, network_id: UUID, idempotency_key: str) -> ForecastAccepted:
    """Submit routes-google.v1 for the latest version. Without a saved key nothing is sent,
    so the user sees "add a key" instead of a failed job."""
    with rt.engine.connect() as conn:
        version_id = _latest(conn, network_id).dataset_version_id
        if not settings.google_key_saved(conn):
            raise AccessError("GOOGLE_KEY_MISSING", 409)
        org = conn.scalar(sa.text("SELECT organization_id FROM networks WHERE id = :n"),
                          {"n": network_id})
        payload = google_input(conn, version_id)
    accepted = rt.queue.submit(TrustedScope(org, scope.actor_ref), CONTRACT, payload,
                               idempotency_key)
    url = f"/api/v1/networks/{network_id}/routes"
    return ForecastAccepted(job_id=accepted.job_id, attempt_id=accepted.attempt_id,
                            state=accepted.state, replayed=accepted.replayed, status_url=url,
                            result_url=url)
