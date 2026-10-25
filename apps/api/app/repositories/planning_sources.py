"""Coherent database-backed operational packages. Client settings never replace stock."""

import hashlib
import json
from datetime import timedelta
from uuid import uuid5
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from app.models import operational as m
from app.models.forecasts import ForecastRun
from app.models.jobs import compute_jobs
from app.schemas.or_inputs import ORInputPackage, SourceRef
from app.services.forecasting.postprocessing import validate_output
from app.services.forecasting.preparation import validate_input
from app.services.forecasting.schemas import ForecastInput, ForecastOutput
from app.services.inventory.stock import StockError
from app.services.optimization.canonical import operational_hash
from app.services.optimization.decisions import DECISION_IDS


def source_fingerprint(conn, org):
    """Aggregate on the DB to avoid downloading historical facts during freshness reads."""
    result = {}
    immutable = (m.DemandRevision, m.ReceiptRevision, m.DonationCoverageRevision, ForecastRun)
    mutable = (
        m.Site,
        m.SiteCalendar,
        m.Product,
        m.Category,
        m.DataSource,
        m.InventoryVersion,
        m.InventoryLot,
        m.ExpectedSupply,
        m.ReceiptReconciliation,
    )
    for model in (*immutable, *mutable):
        name = model.__tablename__  # Closed server-owned table names, never request SQL.
        if model in immutable:
            row = conn.execute(
                sa.select(sa.func.count(), sa.func.max(model.recorded_at)).where(
                    model.organization_id == org,
                )
            ).one()
            result[name] = [str(value) for value in row]
        else:
            result[name] = conn.scalar(
                sa.text(
                    "SELECT md5(COALESCE(string_agg(md5(row_to_json(t)::text), "
                    "'' ORDER BY id), '')) "
                    f"FROM {name} t WHERE organization_id = :org"
                ),
                {"org": org},
            )
    return hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()


def assert_sources(conn, package):
    conn.execute(
        sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {
            "key": f"vp-operational:{package.organization_id}",
        },
    )
    ref = next((ref for ref in package.source_refs if ref.kind == "VP_DATABASE"), None)
    if ref is not None and ref.content_hash != source_fingerprint(conn, package.organization_id):
        raise StockError("OPERATIONAL_SOURCES_CHANGED", 409)


def forecast_from_connection(conn, org, run_id):
    row = (
        conn.execute(
            sa.select(ForecastRun.__table__)
            .join(
                compute_jobs,
                sa.and_(
                    compute_jobs.c.job_id == ForecastRun.job_id,
                    compute_jobs.c.organization_id == org,
                ),
            )
            .where(
                ForecastRun.organization_id == org,
                ForecastRun.id == run_id,
                compute_jobs.c.state == "SUCCEEDED",
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise StockError("FORECAST_NOT_FOUND", 404)
    if not row["planning_ready"]:
        raise StockError("FORECAST_NOT_PLANNING_READY", 409)
    inputs = validate_input(ForecastInput.model_validate(row["frozen_input"]))
    output = validate_output(inputs, ForecastOutput.model_validate(row["output"]))
    if output.run_id != run_id:
        raise StockError("FORECAST_INTEGRITY_FAILED", 409)
    return inputs, output


def operational_rows(conn, org, model, maximum=100):
    rows = (
        conn.execute(
            sa.select(model.__table__)
            .where(model.organization_id == org)
            .order_by(model.id)
            .limit(maximum + 1)
        )
        .mappings()
        .all()
    )
    if len(rows) > maximum:
        raise StockError("PLANNING_SCOPE_TOO_LARGE", 422)
    return rows


def capture(conn, org, body):
    inputs, output = forecast_from_connection(conn, org, body.forecast_run_id)
    now = conn.scalar(sa.select(sa.func.clock_timestamp()))
    sites = [row for row in operational_rows(conn, org, m.Site, 14) if row["active"]]
    products = [row for row in operational_rows(conn, org, m.Product, 20) if row["active"]]
    if {row["id"] for row in products} != {p.id for p in body.products}:
        raise StockError("EXPLICIT_FULL_PRODUCT_SCOPE_REQUIRED", 422)
    calendars = {row["id"]: row for row in operational_rows(conn, org, m.SiteCalendar, 100)}
    zones = {calendars[row["current_calendar_id"]]["timezone"] for row in sites}
    if len(zones) != 1:
        raise StockError("SHARED_PLANNING_TIMEZONE_REQUIRED", 422)
    zone = zones.pop()
    first = inputs.data_cutoff_date + timedelta(days=1)
    if first < now.astimezone(ZoneInfo(zone)).date():
        raise StockError("FORECAST_HORIZON_ALREADY_STARTED", 409)
    product_map = {row["id"]: row for row in products}
    for product in body.products:
        if product.unit != product_map[product.id]["base_unit"]:
            raise StockError("PRODUCT_UNIT_MISMATCH", 422)
    source = (
        conn.execute(
            sa.select(m.DataSource.__table__).where(
                m.DataSource.organization_id == org,
                m.DataSource.id == inputs.dataset_id,
            )
        )
        .mappings()
        .one()
    )
    fingerprint = source_fingerprint(conn, org)
    selection_token = operational_hash(
        dict(
            database=fingerprint,
            settings=body.model_dump(mode="python", exclude={"expected_source_revision"}),
        )
    )
    markers = operational_rows(conn, org, m.ReceiptReconciliation, 1000)
    if any(row["needs_reconciliation"] for row in markers):
        raise StockError("RECEIPT_RECONCILIATION_REQUIRED", 409)
    forecasts = []
    by_key = {
        (row.scope.key.site_id, row.scope.key.product_id): row
        for row in output.series
        if row.scope.key.target_type == "DEMAND"
    }
    expected_keys = {
        (site["id"], product.id)
        for site in sites
        if site["role"] == "BENEFICIARY"
        for product in body.products
    }
    if set(by_key) != expected_keys:
        raise StockError("FORECAST_NETWORK_SCOPE_CHANGED", 409)
    for site in sites:
        for product in body.products:
            hub = site["role"] == "HUB"
            result = None if hub else by_key.get((site["id"], product.id))
            if not hub and (result is None or result.status != "AVAILABLE"):
                raise StockError("DEMAND_FORECAST_COVERAGE_INCOMPLETE", 409)
            if not hub and (result.scope.unit != product.unit or result.scope.timezone != zone):
                raise StockError("FORECAST_UNIT_OR_CALENDAR_CHANGED", 409)
            forecasts.append(
                dict(
                    id=uuid5(body.forecast_run_id, f"{site['id']}:{product.id}"),
                    run_id=body.forecast_run_id,
                    source_id=inputs.dataset_id,
                    organization_id=org,
                    site_id=site["id"],
                    product_id=product.id,
                    unit=product.unit,
                    timezone=zone,
                    source_revision=output.input_hash,
                    actual_provider="HUB_ZERO_DEMAND" if hub else result.actual_provider.name,
                    basis="REQUESTED" if hub else result.target_basis,
                    source_classification=source["classification"],
                    estimate_kind="POINT" if hub else result.points[0].estimate_kind,
                    interval_method="NONE" if hub else result.points[0].interval_method,
                    cutoff=inputs.data_cutoff_date,
                    generated_at=output.generated_at,
                    committed=True,
                    planning_ready=True,
                    numeric_conversion="LEGACY_FLOAT_LITERAL",
                    upstream_metadata_json=(
                        '{"basis":"hub zero beneficiary demand"}'
                        if hub
                        else result.model_dump_json()
                    ),
                    days=[
                        dict(
                            day=first + timedelta(days=i),
                            central_literal="0" if hub else str(result.points[i].central_estimate),
                            p10_literal=None
                            if hub or result.points[i].p10 is None
                            else str(result.points[i].p10),
                            p50_literal=None
                            if hub or result.points[i].p50 is None
                            else str(result.points[i].p50),
                            p90_literal=None
                            if hub or result.points[i].p90 is None
                            else str(result.points[i].p90),
                        )
                        for i in range(7)
                    ],
                )
            )
    inventory = []
    balances = dict(
        conn.execute(
            sa.select(m.StockLedgerEntry.lot_id, sa.func.sum(m.StockLedgerEntry.delta))
            .where(m.StockLedgerEntry.organization_id == org)
            .group_by(m.StockLedgerEntry.lot_id)
        ).all()
    )
    for lot in operational_rows(conn, org, m.InventoryLot, 256):
        if balances.get(lot["id"], 0) != lot["on_hand"]:
            raise StockError("LEDGER_BALANCE_MISMATCH", 409)
        if (
            lot["site_id"] not in {row["id"] for row in sites}
            or lot["product_id"] not in product_map
        ):
            raise StockError("EXPLICIT_INVENTORY_SCOPE_REQUIRED", 422)
        eligibility = lot["eligibility"]
        inventory.append(
            dict(
                id=lot["id"],
                site_id=lot["site_id"],
                product_id=lot["product_id"],
                unit=product_map[lot["product_id"]]["base_unit"],
                physical_units=lot["on_hand"],
                free_units=lot["on_hand"] if eligibility == "ELIGIBLE" else 0,
                reserved_units=0,
                committed_units=0,
                held_units=lot["on_hand"] if eligibility != "ELIGIBLE" else 0,
                available_on=lot["received_at"].astimezone(ZoneInfo(zone)).date(),
                expires_on=lot["expires_on"],
                expiry_kind=lot["expiry_kind"],
                eligibility=eligibility if eligibility in {"ELIGIBLE", "HELD"} else "UNKNOWN",
                source_line_id=lot["id"],
                source_revision=str(lot["metadata_version"]),
                dispatchable=True,
                commitment_scope_refs=(),
                commitment_overlaps_demand=False,
            )
        )
    supplies = operational_rows(conn, org, m.ExpectedSupply, 256)
    site_ids = {site["id"] for site in sites}
    if any((row["site_id"] not in site_ids or row["product_id"] not in product_map)
           and row["state"] == "CONFIRMED" and row["outstanding_confirmed_quantity"]
           for row in supplies):
        raise StockError("EXPLICIT_SUPPLY_SCOPE_REQUIRED", 422)
    arrivals = [
        dict(
            id=row["id"],
            source_line_id=row["id"],
            site_id=row["site_id"],
            product_id=row["product_id"],
            unit=product_map[row["product_id"]]["base_unit"],
            units=row["outstanding_confirmed_quantity"],
            available_on=row["expected_arrival_at"].astimezone(ZoneInfo(zone)).date(),
            expires_on=None,
            expiry_kind="UNKNOWN",
            eligibility="UNKNOWN",
            confirmed=True,
            already_posted=False,
            source_revision=str(row["version"]),
        )
        for row in supplies
        if row["state"] == "CONFIRMED" and row["outstanding_confirmed_quantity"]
    ]
    ref = SourceRef(id=org, kind="VP_DATABASE", revision=fingerprint, content_hash=fingerprint)
    return ORInputPackage(
        organization_id=org,
        dataset_id=inputs.dataset_id,
        source_kind="SIMULATED" if source["classification"] == "SIMULATED" else "LIVE",
        source_revision_token=selection_token,
        source_refs=(ref,),
        snapshot_as_of=now,
        operational_timezone=zone,
        first_planning_date=first,
        sites=[
            dict(
                id=row["id"],
                organization_id=org,
                role=row["role"],
                name=row["name"],
                timezone=zone,
                source_revision=str(row["current_calendar_id"]),
            )
            for row in sites
        ],
        products=body.products,
        forecasts=forecasts,
        inventory=inventory,
        confirmed_arrivals=arrivals,
        routes=body.routes,
        capacities=body.capacities,
        reserves=body.reserves,
        vulnerability_attributes=body.vulnerability_attributes,
        source_coverage=dict(
            required_complete=True,
            excluded_series=(),
            partial_scope=False,
            forecast_handoff_hash=output.input_hash,
        ),
        source_manifest_hash=operational_hash((ref,)),
        provenance_warnings=(
            "VP_OPERATIONAL_SNAPSHOT",
            "CONFIRMED_SUPPLY_EXPIRY_UNKNOWN",
            "FIXED_LOADING_ORDER_RESTRICTS_FEASIBLE_SET",
        ),
        decision_ids=DECISION_IDS,
    )
