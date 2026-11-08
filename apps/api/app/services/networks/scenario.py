"""Network → frozen or-input-v3 scenario (W1-D09, V1-SPEC §6.1–6.3, W0-08 §5).

`build_scenario` reads one dataset version and one forecast run and returns the ORInputV3 the
comparison solves. Only confirmed resources are supply: on-hand batches, plus inbound rows
arriving inside the seven days, each counted once. Donation forecasts are never supply. A
series without an available forecast gets no demand row (never zero). Inputs the templates
don't carry are explicit assumptions: blank capacities mean no limit, reserve floors 0 unless
set, no cost budget unless set, Retail weights 1/1 unless set.
"""

import hashlib
import math
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from pydantic import ValidationError

from app.repositories import networks as networks_repo
from app.schemas.or_inputs import decimal_literal
from app.schemas.v1_planning import (
    BatchV3,
    CapacityV3,
    DemandSeriesV3,
    InboundV3,
    LocationV3,
    ORInputV3,
    ProductV3,
    RetailWeights,
    RouteV3,
    ScenarioOptions,
    VulnerabilityV3,
    resolve_window_and_policy,
)
from app.services.demand_targets import round_daily_targets
from app.services.enrichment.distance import DB_TO_API
from app.services.enrichment.service import blockers, location_attributes
from app.services.forecasting.schemas import ForecastOutput
from app.services.jobs.registry import InputRejected
from app.services.presenter_access import AccessError

NO_LIMIT = "capacity not provided — no limit assumed"
SENDERS = frozenset({"hub", "distribution_center"})  # never receive
HORIZON_DAYS = 7


def _rejected(code: str, message: str, **details) -> InputRejected:
    error = InputRejected(code, message)
    error.details = details
    return error


def _rows(conn: sa.Connection, sql: str, version_id: UUID) -> list[sa.Row]:
    return list(conn.execute(sa.text(sql), {"v": version_id}))


def build_scenario(conn: sa.Connection, network: sa.Row, options: ScenarioOptions) -> ORInputV3:
    """`network` is a networks repository row (its latest version and as-of date)."""
    mode = network.mode.upper()
    planning_days, policy = resolve_window_and_policy(mode, options)
    version_id = options.dataset_version_id
    if version_id != network.dataset_version_id:
        known = conn.scalar(sa.text(
            "SELECT 1 FROM dataset_versions WHERE id = :v AND network_id = :n"),
            {"v": version_id, "n": network.id})
        raise (AccessError("STALE_DATASET_VERSION", 409) if known
               else AccessError("DATASET_VERSION_NOT_FOUND", 404))
    org = conn.scalar(sa.text("SELECT organization_id FROM networks WHERE id = :n"),
                      {"n": network.id})
    forecast = _forecast(conn, options.forecast_run_id, org, version_id, network.as_of_date)
    assumptions: list[str] = []

    locations = _rows(conn, "SELECT id, external_id, name, role, receiving_capacity_per_day "
                            "FROM net_locations WHERE dataset_version_id = :v "
                            'ORDER BY external_id COLLATE "C"', version_id)
    products = _rows(conn, "SELECT id, external_id, name, unit, unit_value_usd, "
                           "handling_units_per_unit, handling_units_given FROM net_products "
                           'WHERE dataset_version_id = :v ORDER BY external_id COLLATE "C"',
                           version_id)
    fractional = [p.external_id for p in products if p.handling_units_per_unit % 1]
    if fractional:
        raise _rejected("HANDLING_UNITS_NOT_WHOLE", "The optimizer needs whole handling units "
                        "per unit; enter a whole number in products.csv and import again",
                        products=fractional)
    assumed = [p.external_id for p in products if not p.handling_units_given]
    if assumed:  # V1-SPEC §6.1: a blank handling_units_per_unit is 1, shown as an assumption
        assumptions.append(f"Handling units per unit: 1 assumed for {', '.join(assumed)} "
                           "(blank in products.csv)")
    location_ids = {r.id: r.external_id for r in locations}
    product_ids = {r.id: r.external_id for r in products}

    demand = _demand(forecast, location_ids, product_ids, assumptions)
    inbound, provided = _inbound(conn, version_id, assumptions)
    rounded: list[str] = []
    routes = _routes(conn, version_id, options.transfer_mode, assumptions, rounded)
    capacities = _capacities(locations, assumptions, rounded)
    if rounded:
        assumptions.append("Capacities rounded down to whole handling units: "
                           + "; ".join(rounded))
    vulnerability = _vulnerability(conn, version_id, assumptions) if mode == "PANTRY" else ()

    reserves = options.reserve_floors
    assumptions.append("Reserve floors: 0 " + (
        "except " + ", ".join(f"{r.location_id} × {r.product_id}" for r in reserves)
        + " (set in this scenario)" if reserves else
        "for every location and product (none set in this scenario)"))
    if options.cost_budget_minor is None:
        assumptions.append("Cost budget: off (none set)")
    weights = options.retail_weights
    if mode == "RETAIL":
        assumptions.append(
            "Retail weights: w_exp = 1, w_lost = 1 (v1 defaults; editable)" if weights is None
            else f"Retail weights: w_exp = {weights.w_exp}, w_lost = {weights.w_lost} "
                 "(set in this scenario)")
        weights = weights or RetailWeights(w_exp=1, w_lost=1)

    batches = _batches(conn, version_id, network.as_of_date,
                       {r.external_id: r.unit for r in products}, assumptions)
    try:
        return ORInputV3(
            network_id=network.id, organization_id=org, dataset_version_id=version_id,
            forecast_run_id=options.forecast_run_id, mode=mode,
            transfer_mode=options.transfer_mode, timezone=network.timezone,
            snapshot_as_of=network.as_of_date,
            first_planning_date=network.as_of_date + timedelta(days=1),
            planning_days=planning_days, policy=policy,
            locations=tuple(LocationV3(id=r.external_id, name=r.name, role=r.role)
                            for r in locations),
            products=tuple(ProductV3(
                id=r.external_id, name=r.name, unit=r.unit,
                handling_units_per_unit=int(r.handling_units_per_unit),
                unit_value_usd=None if r.unit_value_usd is None else str(r.unit_value_usd))
                for r in products),
            batches=tuple(batches), demand=tuple(demand), inbound=tuple(inbound),
            inbound_file_provided=provided, routes=tuple(routes), capacities=tuple(capacities),
            global_handling=None, cost_budget_minor=options.cost_budget_minor,
            reserves=reserves, retail_weights=weights, vulnerability=tuple(vulnerability),
            assumptions=tuple(assumptions))
    except ValidationError as error:
        first = error.errors()[0]
        raise _rejected("SCENARIO_INVALID", f"The scenario can't be frozen: {first['msg']}",
                        location=[str(x) for x in first["loc"]]) from None


def _forecast(conn: sa.Connection, run_id: UUID, org: UUID, version_id: UUID,
              as_of) -> ForecastOutput:
    row = conn.execute(sa.text(
        "SELECT organization_id, planning_ready, frozen_input, output FROM forecast_runs "
        "WHERE id = :f"), {"f": run_id}).one_or_none()
    if row is None or row.organization_id != org:
        raise AccessError("FORECAST_RUN_NOT_FOUND", 404)
    if str(row.frozen_input.get("dataset_id")) != str(version_id):
        raise AccessError("FORECAST_VERSION_MISMATCH", 409)
    if not row.planning_ready:
        raise AccessError("FORECAST_NOT_PLANNING_READY", 409)
    output = ForecastOutput.model_validate(row.output)
    if output.data_cutoff_date != as_of:  # its seven days must be the scenario's seven days
        raise AccessError("FORECAST_VERSION_MISMATCH", 409)
    return output


def _demand(forecast: ForecastOutput, location_ids: dict, product_ids: dict,
            assumptions: list[str]) -> list[DemandSeriesV3]:
    demand, missing, donations = [], [], 0
    for series in forecast.series:
        key = series.scope.key
        if key.site_id not in location_ids or key.product_id not in product_ids:
            raise AccessError("FORECAST_VERSION_MISMATCH", 409)
        loc, prod = location_ids[key.site_id], product_ids[key.product_id]
        if key.target_type == "DONATION":  # shown elsewhere, never supply (V1-SPEC §6.1)
            donations += series.status == "AVAILABLE"
        elif series.status != "AVAILABLE":
            missing.append(f"{loc} × {prod} ({series.status})")
        else:
            literals = tuple(decimal_literal(str(p.central_estimate)) for p in series.points)
            rounded = round_daily_targets([(p.day, Decimal(x))
                                           for p, x in zip(series.points, literals, strict=True)])
            demand.append(DemandSeriesV3(
                location_id=loc, product_id=prod,
                basis="demand" if series.target_basis == "REQUESTED" else "sales",
                actual_provider=series.actual_provider.name,
                fallback_reason=series.fallback_reason, central_literals=literals,
                targets=tuple(p.target for p in rounded.points)))
    if missing:
        assumptions.append("No available forecast, so no demand target (not zero): "
                           + ", ".join(sorted(missing)))
    if donations:
        assumptions.append(f"Expected donations (forecast, not confirmed) for {donations} "
                           "series are shown but never counted as supply")
    return sorted(demand, key=lambda d: (d.location_id, d.product_id))


def _inbound(conn: sa.Connection, version_id: UUID,
             assumptions: list[str]) -> tuple[list[InboundV3], bool]:
    rows = _rows(conn, "SELECT i.line_no, l.external_id AS loc, p.external_id AS prod, "
                       "i.quantity, i.arrival_date, i.expiry_date, i.non_expiring, "
                       "i.within_horizon FROM net_inbound i "
                       "JOIN net_locations l ON l.id = i.location_id "
                       "JOIN net_products p ON p.id = i.product_id "
                       "WHERE i.dataset_version_id = :v ORDER BY i.line_no", version_id)
    provided = networks_repo.inbound_file_provided(conn, version_id)
    if not provided:
        assumptions.append("no scheduled deliveries provided")
    later = [r for r in rows if not r.within_horizon]
    if later:
        assumptions.append("Inbound outside the seven-day horizon, not counted: " + "; ".join(
            f"line {r.line_no} {r.loc} × {r.prod} {r.quantity} arriving {r.arrival_date}"
            for r in later))
    return [InboundV3(id=f"inbound-{r.line_no}", location_id=r.loc, product_id=r.prod,
                      quantity=r.quantity, arrival_date=r.arrival_date,
                      expiry_date=r.expiry_date, non_expiring=r.non_expiring)
            for r in rows if r.within_horizon], provided


def _batches(conn: sa.Connection, version_id: UUID, as_of, units: dict[str, str],
             assumptions: list[str]) -> list[BatchV3]:
    """On-hand lots, less those no planning day can use. A lot is usable through its expiry
    date (optimization/kernel.py, v3.eligible), but planning starts at as_of + 1, so a lot
    with expiry <= as_of (the as-of day included) would only count as day-1 waste."""
    rows = _rows(conn, "SELECT l.external_id AS loc, p.external_id AS prod, b.external_id AS lot, "
                       "b.quantity, b.expiry_date, b.non_expiring FROM net_batches b "
                       "JOIN net_locations l ON l.id = b.location_id "
                       "JOIN net_products p ON p.id = b.product_id "
                       "WHERE b.dataset_version_id = :v ORDER BY "
                       'l.external_id COLLATE "C", p.external_id COLLATE "C", '
                       'b.external_id COLLATE "C"', version_id)
    kept, expired = [], []
    for r in rows:
        dated = not r.non_expiring and r.expiry_date is not None
        (expired if dated and r.expiry_date <= as_of else kept).append(r)
    if expired:  # per product in its own unit, never summed across products
        assumptions.append(
            f"Batches that expire on or before the as-of date {as_of} can't be used from the "
            f"first planning day {as_of + timedelta(days=1)}, so they are left out: " + "; ".join(
                f"{prod}: " + ", ".join(f"{r.loc} {r.lot} {r.quantity} {units[prod]} "
                                        f"(expiry {r.expiry_date})"
                                        for r in expired if r.prod == prod)
                for prod in sorted({r.prod for r in expired}, key=str.encode)))
    return [BatchV3(id=_batch_id(r.loc, r.prod, r.lot), location_id=r.loc, product_id=r.prod,
                    quantity=r.quantity, expiry_date=r.expiry_date, non_expiring=r.non_expiring)
            for r in kept]


def _batch_id(location: str, product: str, batch: str) -> str:
    """`location/product/batch` when it fits BatchV3.id (64) unambiguously; otherwise a
    deterministic hash. Readable ids have exactly two slashes, hashed ones none."""
    parts = (location, product, batch)
    readable = "/".join(parts)
    if len(readable) <= 64 and not any("/" in part for part in parts):
        return readable
    # NUL can't appear in an imported cell, so it separates the parts unambiguously.
    return "h-" + hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:40]


def _whole(value: Decimal | None, label: str, rounded: list[str]) -> int | None:
    """Floor to whole handling units, so a capacity is never exceeded; list any change."""
    if value is None:
        return None
    whole = math.floor(value)
    if whole != value:
        rounded.append(f"{label} {value.normalize():f} → {whole}")
    return whole


def _routes(conn: sa.Connection, version_id: UUID, transfer_mode,
            assumptions: list[str], rounded: list[str]) -> list[RouteV3]:
    rows = _rows(conn, "SELECT f.external_id AS src, t.external_id AS dst, f.role, r.method, "
                       "r.distance_miles, r.travel_days, r.cost_per_handling_unit, "
                       "r.capacity_per_batch FROM net_routes r "
                       "JOIN net_locations f ON f.id = r.from_location_id "
                       "JOIN net_locations t ON t.id = r.to_location_id "
                       "WHERE r.dataset_version_id = :v AND NOT r.disabled "
                       'ORDER BY f.external_id COLLATE "C", t.external_id COLLATE "C"',
                 version_id)
    if transfer_mode == "HUB_ONLY":
        rows = [r for r in rows if r.role in SENDERS]
    usable = [r for r in rows if r.travel_days is not None and r.travel_days <= HORIZON_DAYS]
    if len(usable) < len(rows):
        assumptions.append("Routes longer than 7 travel days left out: " + ", ".join(
            f"{r.src}→{r.dst}" for r in rows if r not in usable))
    blank = sum(r.capacity_per_batch is None for r in usable)
    if blank:
        assumptions.append(f"Route capacity per batch on {blank} of {len(usable)} routes: "
                           f"{NO_LIMIT}")
    return [RouteV3(from_location_id=r.src, to_location_id=r.dst, travel_days=r.travel_days,
                    method=DB_TO_API[r.method],
                    road_miles=None if r.distance_miles is None else str(r.distance_miles),
                    cost_per_handling_unit_usd=None if r.cost_per_handling_unit is None
                    else str(r.cost_per_handling_unit),
                    capacity_per_batch=_whole(r.capacity_per_batch, f"{r.src}→{r.dst} per batch",
                                              rounded))
            for r in usable]


def _capacities(locations: list[sa.Row], assumptions: list[str],
                rounded: list[str]) -> list[CapacityV3]:
    blank = [r.external_id for r in locations
             if r.role not in SENDERS and r.receiving_capacity_per_day is None]
    if blank:
        assumptions.append(f"Receiving capacity at {', '.join(blank)}: {NO_LIMIT}")
    assumptions.append(f"Dispatch, storage and global handling capacity: {NO_LIMIT} "
                       "(the templates don't carry them)")
    return [CapacityV3(location_id=r.external_id,
                       receiving=_whole(r.receiving_capacity_per_day,
                                        f"{r.external_id} receiving", rounded),
                       dispatch=None, storage=None) for r in locations]


def _vulnerability(conn: sa.Connection, version_id: UUID,
                   assumptions: list[str]) -> list[VulnerabilityV3]:
    """EGP needs both rates for every pantry, or its explicit exclusion (BD-08)."""
    found = blockers(conn, version_id)
    if found:
        raise _rejected(
            "EGP_ATTRIBUTES_UNRESOLVED", "Enter poverty and SNAP rates, or exclude the location "
            "from EGP, for every listed pantry before freezing a Pantry scenario",
            locations=[{"location_id": loc, "missing": list(missing)} for loc, missing in found])
    pantries = {r.external_id for r in _rows(
        conn, "SELECT external_id FROM net_locations WHERE dataset_version_id = :v "
              "AND role = 'pantry'", version_id)}
    attributes = [a for a in location_attributes(conn, version_id) if a.location_id in pantries]
    excluded = [a.location_id for a in attributes if a.state == "excluded"]
    if excluded:
        assumptions.append(f"{', '.join(excluded)} excluded from EGP by the user")
    return [VulnerabilityV3(location_id=a.location_id, poverty_rate=str(a.poverty_rate),
                            snap_rate=str(a.snap_rate), source=a.source or "manual")
            for a in attributes if a.state in ("known", "manual")]
