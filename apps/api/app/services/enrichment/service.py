"""Enrichment of one dataset version (W1-D06): input, geocode step, apply.

The enrichment.v1 job splits these the way CR-w1-data-2 requires: `enrichment_input` reads
the addresses at submit time, `geocode_step` runs in the DB-less step child (the only part
that calls Census), and `apply_enrichment` writes ~100 location rows and the refreshed
routes at publish. `run_enrichment` chains the three in-process for tests.

Enrichment fills only unknown fields: given or geocoded coordinates and looked-up rates are
never overwritten, and manual values live in their own columns."""

from typing import Any
from uuid import UUID

import sqlalchemy as sa

from app.schemas.v1_enrichment import GeoLocation, LocationAttributes
from app.services.enrichment.census import (
    AcsTable,
    Address,
    CensusClient,
    CensusUnavailable,
    Geocode,
)
from app.services.enrichment.distance import candidate_routes, candidate_row

ACS_TABLES = "ACS5 B17001,B22003"
EGP_ROLES = ("pantry",)  # EGP weighs receiving pantries; hubs never receive
NO_MATCH_HINT = ("Census found no match. Correct the street, city, state or ZIP, or enter "
                 "latitude and longitude for this location in locations.csv")
UNCONFIRMED = "unconfirmed address match"  # a Non_Exact geocode (W2-06 A7)
TIE_HINT = ("Census found more than one match. Make the address more specific, or enter "
            "latitude and longitude for this location in locations.csv")


def enrichment_input(conn: sa.Connection, version_id: UUID) -> dict[str, Any]:
    rows = conn.execute(sa.text(
        "SELECT external_id, street, city, state, zip FROM net_locations WHERE "
        "dataset_version_id = :v AND latitude IS NULL ORDER BY external_id COLLATE \"C\""),
        {"v": version_id}).all()
    return {"dataset_version_id": str(version_id), "addresses": [list(r) for r in rows]}


def geocode_step(payload: dict[str, Any], client: CensusClient) -> dict[str, Any]:
    """Runs without database access. An outage is a result, not a job failure."""
    try:
        found = client.geocode([Address(*a) for a in payload["addresses"]])
    except CensusUnavailable as error:
        return {"geocodes": [], "error": str(error)}
    return {"geocodes": [
        {"location_id": g.location_id, "status": g.status, "matched_address": g.matched_address,
         "latitude": None if g.latitude is None else str(g.latitude),
         "longitude": None if g.longitude is None else str(g.longitude),
         "tract_geoid": g.tract_geoid} for g in found.values()], "error": None}


def apply_enrichment(conn: sa.Connection, version_id: UUID, step: dict[str, Any],
                     acs: AcsTable | None) -> dict[str, Any]:
    """Store geocodes and ACS rates; return the manifest the status reads back."""
    addresses = {r.external_id: Address(*r) for r in conn.execute(sa.text(
        "SELECT external_id, street, city, state, zip FROM net_locations WHERE "
        "dataset_version_id = :v"), {"v": version_id})}
    unmatched, located = [], False
    for g in (Geocode(**g) for g in step["geocodes"]):
        if g.latitude is not None:
            located |= conn.execute(sa.text(
                "UPDATE net_locations SET latitude = :lat, longitude = :lon, coordinates_source "
                "= 'census_geocoder', tract_geoid = :tract, acs_source = :note WHERE "
                "dataset_version_id = :v AND external_id = :e AND latitude IS NULL"),
                {"lat": g.latitude, "lon": g.longitude, "tract": g.tract_geoid,
                 # kept in acs_source so a later rate fill still knows (rates are NULL here)
                 "note": UNCONFIRMED if g.status == "Non_Exact" else None,
                 "v": version_id, "e": g.location_id}).rowcount > 0
        if g.status != "Exact":
            hint = {"No_Match": NO_MATCH_HINT, "Tie": TIE_HINT}.get(g.status) or (
                f"Census matched a different address: {g.matched_address}. Check it; if it's "
                "wrong, correct the address or enter latitude and longitude in locations.csv")
            unmatched.append({"location_id": g.location_id,
                              "address": addresses[g.location_id].text(), "hint": hint})
    errors = [step["error"]] if step["error"] else []
    if acs is None:
        errors.append("The ACS tract table is not installed, so poverty and SNAP rates "
                      "stay unknown")
    else:
        _fill_rates(conn, version_id, acs)
    if located:
        refresh_routes(conn, version_id)
    return {"unmatched": unmatched, "last_error": "; ".join(errors) or None}


def _fill_rates(conn: sa.Connection, version_id: UUID, acs: AcsTable) -> None:
    pending = conn.execute(sa.text(
        "SELECT id, tract_geoid, acs_source FROM net_locations WHERE dataset_version_id = :v AND "
        "tract_geoid IS NOT NULL AND poverty_rate IS NULL AND snap_rate IS NULL"),
        {"v": version_id}).all()
    updates = [{"id": r.id, "poverty": poverty, "snap": snap,
                "source": ACS_TABLES + (f"; {UNCONFIRMED}" if r.acs_source == UNCONFIRMED else ""),
                "year": acs.year, "at": acs.fetched_at}
               for r in pending for poverty, snap in (acs.rates(r.tract_geoid),)
               if poverty is not None or snap is not None]
    if updates:
        conn.execute(sa.text(
            "UPDATE net_locations SET poverty_rate = :poverty, snap_rate = :snap, acs_source = "
            ":source, acs_year = :year, acs_fetched_at = :at WHERE id = :id"), updates)


def refresh_routes(conn: sa.Connection, version_id: UUID) -> None:
    """Recompute straight-line routes; routes.csv and Google rows stay as they are."""
    located = conn.execute(sa.text(
        "SELECT id, organization_id, external_id, latitude, longitude, role FROM net_locations "
        "WHERE dataset_version_id = :v AND latitude IS NOT NULL"), {"v": version_id}).all()
    ids = {r.external_id: r.id for r in located}
    conn.execute(sa.text("DELETE FROM net_routes WHERE dataset_version_id = :v AND NOT "
                         "is_override AND method = 'straight_line'"), {"v": version_id})
    kept = set(conn.execute(sa.text(
        "SELECT from_location_id, to_location_id FROM net_routes WHERE dataset_version_id = :v"),
        {"v": version_id}).all())
    geo = [GeoLocation(id=r.external_id, latitude=r.latitude, longitude=r.longitude,
                       role=r.role) for r in located]
    rows = [candidate_row(c) for c in candidate_routes(geo)
            if (ids[c.from_location_id], ids[c.to_location_id]) not in kept]
    if rows:
        conn.execute(sa.text(
            "INSERT INTO net_routes (id, organization_id, dataset_version_id, from_location_id, "
            "to_location_id, method, distance_miles, road_hours, travel_days, is_override, "
            "disabled) VALUES (gen_random_uuid(), :org, :v, :src, :dst, :method, "
            ":distance_miles, :road_hours, :travel_days, false, false)"),
            [{**r, "org": located[0].organization_id, "v": version_id,
              "src": ids[r["from"]], "dst": ids[r["to"]]} for r in rows])


def run_enrichment(engine: sa.Engine, version_id: UUID, client: CensusClient,
                   acs: AcsTable | None) -> dict[str, Any]:
    with engine.connect() as conn:
        payload = enrichment_input(conn, version_id)
    step = geocode_step(payload, client)
    with engine.begin() as conn:
        return apply_enrichment(conn, version_id, step, acs)


_ATTRIBUTES = (
    "SELECT external_id, role, poverty_rate, snap_rate, manual_poverty_rate, manual_snap_rate, "
    "excluded, tract_geoid, acs_year, acs_fetched_at, acs_source, EXISTS (SELECT 1 FROM "
    "dataset_versions v JOIN networks n ON n.id = v.network_id WHERE v.id = "
    "net_locations.dataset_version_id AND n.is_sample) AS is_sample FROM net_locations "
    "WHERE dataset_version_id = :v")


def location_attributes(conn: sa.Connection, version_id: UUID,
                        external_id: str | None = None) -> list[LocationAttributes]:
    sql = (_ATTRIBUTES + (" AND external_id = :e" if external_id else "")
           + ' ORDER BY external_id COLLATE "C"')  # code-point order: frozen payloads match
    return [_attributes(r) for r in conn.execute(sa.text(sql),
                                                 {"v": version_id, "e": external_id})]


def _attributes(r: sa.Row) -> LocationAttributes:
    looked_up = None if r.acs_year is None else f"ACS 5-year {r.acs_year}, tract {r.tract_geoid}"
    if looked_up and UNCONFIRMED in (r.acs_source or ""):
        looked_up += f" ({UNCONFIRMED})"
    if r.excluded:
        return LocationAttributes(location_id=r.external_id, state="excluded", poverty_rate=None,
                                  snap_rate=None, source=None, fetched_at=None)
    poverty = r.poverty_rate if r.manual_poverty_rate is None else r.manual_poverty_rate
    snap = r.snap_rate if r.manual_snap_rate is None else r.manual_snap_rate
    if r.manual_poverty_rate is not None or r.manual_snap_rate is not None:
        # One manual rate beside a looked-up one: name each rate's source.
        acs_rate = next((name for name, manual, value in (
            ("poverty_rate", r.manual_poverty_rate, r.poverty_rate),
            ("snap_rate", r.manual_snap_rate, r.snap_rate))
            if manual is None and value is not None), None)
        if acs_rate is None or looked_up is None:
            # V1-SPEC §8. shortcut: a user's own edit on a sample location also reads "sample
            # values" (no column tells it from the template value); add one if samples get edited.
            source, fetched_at = "sample values" if r.is_sample else "manual", None
        else:
            manual_rate = "snap_rate" if acs_rate == "poverty_rate" else "poverty_rate"
            source = f"{manual_rate}: manual; {acs_rate}: {looked_up}"
            fetched_at = r.acs_fetched_at
        return LocationAttributes(location_id=r.external_id, state="manual", poverty_rate=poverty,
                                  snap_rate=snap, source=source, fetched_at=fetched_at)
    return LocationAttributes(
        location_id=r.external_id,
        state="known" if poverty is not None and snap is not None else "unknown",
        poverty_rate=poverty, snap_rate=snap, source=looked_up,
        fetched_at=None if looked_up is None else r.acs_fetched_at)


def blockers(conn: sa.Connection, version_id: UUID) -> list[tuple[str, tuple[str, ...]]]:
    """(location_id, missing rates) for each EGP receiver that is neither known nor excluded."""
    found = []
    for a, row in ((_attributes(r), r) for r in conn.execute(
            sa.text(_ATTRIBUTES + ' ORDER BY external_id COLLATE "C"'), {"v": version_id})):
        if row.role in EGP_ROLES and a.state != "excluded":
            missing = tuple(name for name, value in (("poverty_rate", a.poverty_rate),
                                                     ("snap_rate", a.snap_rate)) if value is None)
            if missing:
                found.append((a.location_id, missing))
    return found
