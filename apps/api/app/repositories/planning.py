"""Tenant-owned, repeatable-read planning snapshots. No source assertions from clients."""

import json
from datetime import timedelta
from uuid import uuid4, uuid5
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from app.models import operational as m
from app.models.forecasts import ForecastRun
from app.models.optimization import PlanningAssumptions, PlanningComparison, PlanningScenario
from app.repositories.forecast_history import HistoryRejected
from app.repositories.forecast_results import read_committed_forecast_connection
from app.repositories.jobs import IdempotencyConflict
from app.schemas.optimization_api import AssumptionsPayload
from app.schemas.or_inputs import ORInputPackage, ORScenarioPayload
from app.services.optimization.canonical import operational_hash
from app.services.optimization.decisions import DECISION_IDS
from app.services.optimization.scenario import freeze_scenario, verify_scenario

SOURCE_MODELS = (
    m.Site,
    m.SiteCalendar,
    m.Product,
    m.Category,
    m.InventoryVersion,
    m.InventoryLot,
    m.ExpectedSupply,
    m.ReceiptReconciliation,
    m.DataSource,
)


def owned_row(conn, model, org, identity):
    row = (
        conn.execute(
            sa.select(model.__table__).where(model.organization_id == org, model.id == identity)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HistoryRejected("PLANNING_RECORD_NOT_FOUND", 404)
    return row


def source_state(conn, org):
    """Fingerprint actual stock, supply, calendars and catalog in one database view."""
    state = {}
    for model in SOURCE_MODELS:
        rows = (
            conn.execute(
                sa.select(model.__table__)
                .where(model.organization_id == org)
                .order_by(model.id)
                .limit(4097)
            )
            .mappings()
            .all()
        )
        if len(rows) > 4096:
            raise HistoryRejected("PLANNING_SOURCE_TOO_LARGE")
        state[model.__tablename__] = [dict(row) for row in rows]
    # These histories are append-only. Their count/latest ingestion instant detects
    # newly committed corrections without copying unbounded history into stock state.
    for model in (m.DemandRevision, m.ReceiptRevision, m.DonationCoverageRevision):
        row = (
            conn.execute(
                sa.select(
                    sa.func.count().label("count"), sa.func.max(model.recorded_at).label("latest")
                ).where(model.organization_id == org)
            )
            .mappings()
            .one()
        )
        state[model.__tablename__] = dict(row)
    return state, operational_hash(state)


def require_demo(conn, org):
    if conn.scalar(sa.select(m.Organization.is_demo).where(m.Organization.id == org)) is not True:
        raise HistoryRejected("SIMULATED_DEMO_REQUIRED", 403)


def read_assumptions(conn, org, identity):
    row = owned_row(conn, PlanningAssumptions, org, identity)
    payload = AssumptionsPayload.model_validate(row["payload"])
    if operational_hash(payload) != row["content_hash"]:
        raise HistoryRejected("ASSUMPTIONS_INTEGRITY_FAILED", 409)
    return row, payload


def save_assumptions(engine, scope, request):
    with engine.begin() as conn:
        require_demo(conn, scope.organization_id)
        read_assumptions(conn, scope.organization_id, request.parent_id)
        if any(
            score.classification != "SIMULATED"
            for site in request.payload.vulnerability_attributes
            for score in site.scores
        ):
            raise HistoryRejected("SIMULATED_ASSUMPTIONS_REQUIRED")
        identity = uuid4()
        conn.execute(
            sa.insert(PlanningAssumptions).values(
                id=identity,
                organization_id=scope.organization_id,
                parent_id=request.parent_id,
                name=request.name,
                payload=request.payload.model_dump(mode="json"),
                content_hash=operational_hash(request.payload),
                actor=scope.actor_ref,
            )
        )
        return dict(owned_row(conn, PlanningAssumptions, scope.organization_id, identity))


def capture_package(conn, org, forecast_id, assumptions, state, revision):
    inputs, output = read_committed_forecast_connection(conn, org, forecast_id)
    source = next((row for row in state["data_sources"] if row["id"] == inputs.dataset_id), None)
    if source is None or source["classification"] != "SIMULATED":
        raise HistoryRejected("SIMULATED_FORECAST_REQUIRED")
    corrections = conn.scalar(
        sa.select(sa.func.count())
        .select_from(
            m.DemandRevision.__table__.join(
                m.DemandRecord.__table__,
                sa.and_(
                    m.DemandRecord.id == m.DemandRevision.record_id,
                    m.DemandRecord.organization_id == m.DemandRevision.organization_id,
                ),
            )
        )
        .where(
            m.DemandRevision.organization_id == org,
            m.DemandRecord.source_id == inputs.dataset_id,
            m.DemandRecord.local_day <= inputs.data_cutoff_date,
            m.DemandRevision.recorded_at > inputs.snapshot_as_of,
        )
    )
    if corrections:
        raise HistoryRejected("FORECAST_HISTORY_STALE", 409)
    sites = [row for row in state["sites"] if row["active"]]
    categories = {row["id"] for row in state["categories"] if row["active"]}
    products = [
        row for row in state["products"] if row["active"] and row["category_id"] in categories
    ]
    if (
        not 2 <= sum(row["role"] == "BENEFICIARY" for row in sites) <= 12
        or not 1 <= sum(row["role"] == "HUB" for row in sites) <= 2
        or not 1 <= len(products) <= 2
    ):
        raise HistoryRejected("UNSUPPORTED_PLANNING_SCOPE")
    calendars = {row["id"]: row for row in state["site_calendars"]}
    timezones = {calendars[row["current_calendar_id"]]["timezone"] for row in sites}
    if len(timezones) != 1:
        raise HistoryRejected("MIXED_PLANNING_TIMEZONES_UNSUPPORTED")
    zone = next(iter(timezones))
    now = conn.scalar(sa.text("SELECT clock_timestamp()"))
    first = inputs.data_cutoff_date + timedelta(days=1)
    if first != now.astimezone(ZoneInfo(zone)).date():
        raise HistoryRejected("FORECAST_PLANNING_DATE_STALE", 409)
    if any(row["needs_reconciliation"] for row in state["receipt_reconciliations"]):
        raise HistoryRejected("STOCK_RECONCILIATION_REQUIRED", 409)
    # The stock schema does not declare expiry for unposted supplies. Reject rather
    # than assume they are dated, usable, or non-expiring. Predictions are not supply.
    if any(row["outstanding_confirmed_quantity"] for row in state["expected_supplies"]):
        raise HistoryRejected("SUPPLY_EXPIRY_UNSUPPORTED")
    by_product = {row["id"]: row for row in products}
    handling = {row.product_id: row.coefficient for row in assumptions.handling}
    if len(handling) != len(assumptions.handling) or set(handling) != set(by_product):
        raise HistoryRejected("HANDLING_PRODUCT_COVERAGE")
    demand = {
        (row.scope.key.site_id, row.scope.key.product_id): row
        for row in output.series
        if row.scope.key.target_type == "DEMAND"
    }
    prepared = {
        (row.scope.key.site_id, row.scope.key.product_id): row
        for row in inputs.series
        if row.scope.key.target_type == "DEMAND"
    }
    required = {(s["id"], p["id"]) for s in sites if s["role"] == "BENEFICIARY" for p in products}
    if set(demand) != required:
        raise HistoryRejected("FORECAST_NETWORK_CHANGED", 409)
    forecasts = []
    for site in sites:
        for product in products:
            key = site["id"], product["id"]
            row = demand.get(key)
            if row is not None:
                scope = row.scope
                if (
                    row.status != "AVAILABLE"
                    or scope.unit != product["base_unit"]
                    or scope.timezone != zone
                    or scope.calendar_version != str(site["current_calendar_id"])
                ):
                    raise HistoryRejected("FORECAST_SCOPE_STALE", 409)
                classifications = {
                    c for p in prepared[key].observations for c in p.source_classifications
                }
                if classifications != {"SIMULATED"}:
                    raise HistoryRejected("SIMULATED_FORECAST_REQUIRED")
                days = [
                    dict(
                        day=p.day,
                        central_literal=str(p.central_estimate),
                        p10_literal=None if p.p10 is None else str(p.p10),
                        p50_literal=None if p.p50 is None else str(p.p50),
                        p90_literal=None if p.p90 is None else str(p.p90),
                    )
                    for p in row.points
                ]
                metadata = dict(
                    forecast_input_hash=inputs.input_hash, result=row.model_dump(mode="json")
                )
            else:
                days = [
                    dict(
                        day=first + timedelta(days=i),
                        central_literal="0",
                        p10_literal=None,
                        p50_literal=None,
                        p90_literal=None,
                    )
                    for i in range(7)
                ]
                metadata = dict(
                    derivation="HUB_HAS_NO_BENEFICIARY_DEMAND",
                    forecast_input_hash=inputs.input_hash,
                    run_id=str(forecast_id),
                )
            forecasts.append(
                dict(
                    id=row.result_id
                    if row
                    else uuid5(forecast_id, f"hub-zero:{site['id']}:{product['id']}"),
                    run_id=forecast_id,
                    source_id=inputs.dataset_id,
                    organization_id=org,
                    site_id=site["id"],
                    product_id=product["id"],
                    unit=product["base_unit"],
                    timezone=zone,
                    source_revision=inputs.input_hash,
                    actual_provider=row.actual_provider.name if row else "DERIVED_HUB_ZERO_DEMAND",
                    basis=row.target_basis if row else "REQUESTED",
                    source_classification="SIMULATED",
                    estimate_kind=row.points[0].estimate_kind if row else "POINT",
                    interval_method=row.points[0].interval_method if row else "NONE",
                    cutoff=inputs.data_cutoff_date,
                    generated_at=output.generated_at,
                    committed=True,
                    planning_ready=True,
                    numeric_conversion="LEGACY_FLOAT_LITERAL" if row else "EXACT_LITERAL",
                    upstream_metadata_json=json.dumps(
                        metadata, sort_keys=True, separators=(",", ":")
                    ),
                    days=days,
                )
            )
    inventory = []
    ledger = dict(
        conn.execute(
            sa.select(m.StockLedgerEntry.lot_id, sa.func.sum(m.StockLedgerEntry.delta))
            .where(m.StockLedgerEntry.organization_id == org)
            .group_by(m.StockLedgerEntry.lot_id)
        ).all()
    )
    selected_sites = {row["id"] for row in sites}
    for lot in state["inventory_lots"]:
        if lot["site_id"] not in selected_sites or lot["product_id"] not in by_product:
            continue
        if ledger.get(lot["id"], 0) != lot["on_hand"]:
            raise HistoryRejected("STOCK_LEDGER_MISMATCH", 409)
        inventory.append(
            dict(
                id=lot["id"],
                site_id=lot["site_id"],
                product_id=lot["product_id"],
                unit=by_product[lot["product_id"]]["base_unit"],
                physical_units=lot["on_hand"],
                free_units=lot["on_hand"],
                reserved_units=0,
                committed_units=0,
                held_units=0,
                available_on=lot["received_at"].astimezone(ZoneInfo(zone)).date(),
                expires_on=lot["expires_on"],
                expiry_kind=lot["expiry_kind"],
                eligibility="HELD" if lot["eligibility"] == "INELIGIBLE" else lot["eligibility"],
                source_line_id=lot["id"],
                source_revision=operational_hash(lot),
                dispatchable=True,
                commitment_scope_refs=(),
                commitment_overlaps_demand=False,
            )
        )
    refs = [
        dict(
            id=forecast_id,
            kind="COMMITTED_FORECAST",
            revision=inputs.input_hash,
            content_hash=operational_hash({"input_hash": inputs.input_hash, "run_id": forecast_id}),
        ),
        dict(
            id=uuid5(org, "planning-stock-snapshot"),
            kind="DATABASE_STOCK_SNAPSHOT",
            revision=revision,
            content_hash=revision,
        ),
    ]
    for table, kind in (
        ("inventory_versions", "INVENTORY_VERSION"),
        ("expected_supplies", "SUPPLY_REVISION"),
    ):
        for row in state[table]:
            refs.append(
                dict(
                    id=row["id"],
                    kind=kind,
                    revision=str(row.get("version", row.get("revision", operational_hash(row)))),
                    content_hash=operational_hash(row),
                )
            )
    return ORInputPackage(
        organization_id=org,
        dataset_id=inputs.dataset_id,
        source_kind="SIMULATED",
        source_revision_token=revision,
        source_refs=refs,
        source_manifest_hash=operational_hash(refs),
        snapshot_as_of=now,
        operational_timezone=zone,
        first_planning_date=first,
        sites=[
            dict(
                id=s["id"],
                organization_id=org,
                role=s["role"],
                name=s["name"],
                timezone=zone,
                source_revision=operational_hash(s),
            )
            for s in sites
        ],
        products=[
            dict(
                id=p["id"],
                unit=p["base_unit"],
                handling_coefficient=handling[p["id"]],
                source_revision=operational_hash(p),
            )
            for p in products
        ],
        forecasts=forecasts,
        inventory=inventory,
        confirmed_arrivals=(),
        routes=assumptions.routes,
        capacities=assumptions.capacities,
        reserves=assumptions.reserves,
        vulnerability_attributes=assumptions.vulnerability_attributes,
        source_coverage=dict(
            required_complete=True,
            excluded_series=(),
            partial_scope=False,
            forecast_handoff_hash=None,
        ),
        provenance_warnings=(
            "SIMULATED_POLICY_NOT_VALIDATED_FOR_REAL_WORLD_USE",
            "DONATION_PREDICTIONS_NOT_STOCK",
            "DERIVED_HUB_ZERO_DEMAND",
        ),
        decision_ids=DECISION_IDS,
    )


def save_scenario(engine, scope, request, key):
    # REPEATABLE READ keeps the source coherent. Concurrent identical commands may
    # take their snapshots before the advisory lock is acquired; retry that snapshot
    # on serialization/unique-key contention, then return the immutable prior row.
    for _ in range(3):
        try:
            return _save_scenario_once(engine, scope, request, key)
        except sa.exc.DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) not in {"40001", "23505"}:
                raise
    raise HistoryRejected("PLANNING_SNAPSHOT_CONTENTION", 409)


def _save_scenario_once(engine, scope, request, key):
    org = scope.organization_id
    request_hash = operational_hash(request)
    with (
        engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
    ):
        conn.execute(sa.text("SET LOCAL statement_timeout = '10000ms'"))
        require_demo(conn, org)
        # Serialize this command's insertion; preserve the repeatable-read source view.
        conn.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"scenario:{org}:{key}"},
        )
        existing = (
            conn.execute(
                sa.select(PlanningScenario.__table__).where(
                    PlanningScenario.organization_id == org, PlanningScenario.request_key == key
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing:
            if existing["request_hash"] != request_hash:
                raise IdempotencyConflict("Scenario command was reused")
            return existing["id"]
        _, assumptions = read_assumptions(conn, org, request.assumptions_id)
        if request.parent_id:
            owned_row(conn, PlanningScenario, org, request.parent_id)
        state, revision = source_state(conn, org)
        if revision != request.expected_source_revision:
            raise HistoryRejected("STALE_PLANNING_SOURCE", 409)
        try:
            package = capture_package(
                conn, org, request.forecast_run_id, assumptions, state, revision
            )
            snapshot = freeze_scenario(
                package,
                assumptions.policy,
                transfer_mode=request.transfer_mode,
                planning_days=request.planning_days,
                modifiers=request.modifiers,
                intent="CURRENT",
                expected_source_revision=revision,
            )
        except ValueError as exc:
            if isinstance(exc, HistoryRejected):
                raise
            raise HistoryRejected("UNSUPPORTED_PLANNING_INPUT") from exc
        identity = uuid4()
        conn.execute(
            sa.insert(PlanningScenario).values(
                id=identity,
                organization_id=org,
                parent_id=request.parent_id,
                forecast_run_id=request.forecast_run_id,
                assumptions_id=request.assumptions_id,
                request_key=key,
                request_hash=request_hash,
                operational_hash=snapshot.operational_hash,
                source_revision=revision,
                payload=snapshot.model_dump(mode="json"),
                actor=scope.actor_ref,
            )
        )
        return identity


def read_scenario(conn, org, identity):
    row = owned_row(conn, PlanningScenario, org, identity)
    snapshot = ORScenarioPayload.model_validate(row["payload"])
    verify_scenario(snapshot)
    if (
        snapshot.package.organization_id != org
        or snapshot.operational_hash != row["operational_hash"]
    ):
        raise HistoryRejected("SCENARIO_INTEGRITY_FAILED", 409)
    _, revision = source_state(conn, org)
    now = conn.scalar(sa.text("SELECT clock_timestamp()"))
    return dict(
        id=row["id"],
        parent_id=row["parent_id"],
        forecast_run_id=row["forecast_run_id"],
        assumptions_id=row["assumptions_id"],
        recorded_at=row["recorded_at"],
        payload=snapshot,
        stale=revision != row["source_revision"],
        historical=snapshot.package.first_planning_date
        != now.astimezone(ZoneInfo(snapshot.package.operational_timezone)).date(),
    )


def catalog(conn, org, before=None, before_id=None):
    _, revision = source_state(conn, org)
    result = dict(source_revision=revision)
    oldest = []
    for name, model, label in (
        ("assumptions", PlanningAssumptions, PlanningAssumptions.name),
        ("forecasts", ForecastRun, ForecastRun.input_hash),
        ("scenarios", PlanningScenario, PlanningScenario.operational_hash),
        ("comparisons", PlanningComparison, PlanningComparison.outcome),
    ):
        query = sa.select(model.id, model.recorded_at, label.label("label")).where(
            model.organization_id == org
        )
        if model is ForecastRun:
            query = query.where(ForecastRun.planning_ready.is_(True))
        if before:
            query = query.where(
                sa.tuple_(model.recorded_at, model.id) < sa.tuple_(before, before_id)
                if before_id
                else model.recorded_at < before
            )
        rows = (
            conn.execute(query.order_by(model.recorded_at.desc(), model.id.desc()).limit(51))
            .mappings()
            .all()
        )
        result[name] = rows[:50]
        if len(rows) > 50:
            oldest.append((rows[49]["recorded_at"], rows[49]["id"]))
    cursor = max(oldest) if oldest else (None, None)
    result["next_before"], result["next_before_id"] = cursor
    return result
