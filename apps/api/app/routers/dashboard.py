"""Saved dashboard and current physical-stock shortage reads; no model or solver."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from fastapi import APIRouter

from app.models import operational as m
from app.models.forecasts import ForecastRun
from app.repositories.forecast_results import read_committed_forecast_connection
from app.repositories.inventory import build_snapshot, operational_rows
from app.repositories.operations_api import wire
from app.routers.forecasts import PRESENTER, RUNTIME
from app.schemas.dashboard_api import DashboardSummary, ShortageProjection
from app.schemas.forecast_api import ErrorEnvelope
from app.services.demand_targets import round_daily_targets
from app.services.inventory.stock import StockError
from app.services.optimization.kernel import KernelLot, project_kernel

router = APIRouter(
    prefix="/api/v1",
    tags=["dashboard"],
    responses={code: {"model": ErrorEnvelope} for code in (401, 403, 404, 409, 422, 503)},
)


@router.get("/dashboard/summary", response_model=DashboardSummary)
def summary(rt=RUNTIME, scope=PRESENTER):
    with rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            conn.execute(sa.text("SET LOCAL statement_timeout = '10000ms'"))
            now = conn.scalar(sa.select(sa.func.clock_timestamp()))
            sites = [
                row
                for row in operational_rows(conn, scope.organization_id, m.Site, 14)
                if row["active"]
            ]
            products = [
                row
                for row in operational_rows(conn, scope.organization_id, m.Product, 20)
                if row["active"]
            ]
            calendars = {
                row["id"]: row
                for row in operational_rows(conn, scope.organization_id, m.SiteCalendar)
            }
            versions = {
                (row["site_id"], row["product_id"]): row["version"]
                for row in operational_rows(conn, scope.organization_id, m.InventoryVersion, 280)
            }
            lots = defaultdict(list)
            for row in operational_rows(conn, scope.organization_id, m.InventoryLot, 1000):
                if row["on_hand"]:
                    lots[row["site_id"], row["product_id"]].append(row)
            rows = []
            for site in sites:
                calendar = calendars.get(site["current_calendar_id"])
                if calendar is None:
                    raise StockError("SITE_CALENDAR_UNAVAILABLE", 503)
                for product in products:
                    key = site["id"], product["id"]
                    rows.append(
                        build_snapshot(
                            site={**site, "timezone": calendar["timezone"]},
                            product=product,
                            version=versions.get(key),
                            lots=lots[key],
                            now=now,
                        )
                    )
            run = (
                conn.execute(
                    sa.select(
                        ForecastRun.id,
                        ForecastRun.job_id,
                        ForecastRun.planning_ready,
                        ForecastRun.recorded_at,
                    )
                    .where(
                        ForecastRun.organization_id == scope.organization_id,
                    )
                    .order_by(ForecastRun.recorded_at.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            return dict(
                observed_at=now, inventory=rows, latest_forecast=wire(dict(run)) if run else None
            )


@router.get("/shortages/{forecast_run_id}", response_model=ShortageProjection)
def shortages(forecast_run_id: UUID, rt=RUNTIME, scope=PRESENTER):
    with rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            conn.execute(sa.text("SET LOCAL statement_timeout = '10000ms'"))
            inputs, output = read_committed_forecast_connection(
                conn, scope.organization_id, forecast_run_id
            )
            lots = operational_rows(conn, scope.organization_id, m.InventoryLot, 1000)
            products = {
                row["id"]: row
                for row in operational_rows(conn, scope.organization_id, m.Product, 20)
            }
            sites = {
                row["id"]: row for row in operational_rows(conn, scope.organization_id, m.Site, 14)
            }
            calendars = {
                row["id"]: row
                for row in operational_rows(conn, scope.organization_id, m.SiteCalendar)
            }
            now = conn.scalar(sa.select(sa.func.clock_timestamp()))
            series = []
            for result in output.series:
                if result.scope.key.target_type != "DEMAND":
                    continue
                if result.status != "AVAILABLE":
                    raise StockError("DEMAND_FORECAST_UNAVAILABLE", 409)
                key = result.scope.key
                product, site = products.get(key.product_id), sites.get(key.site_id)
                if product is None or site is None or not product["active"] or not site["active"]:
                    raise StockError("FORECAST_NETWORK_SCOPE_CHANGED", 409)
                calendar = calendars.get(site["current_calendar_id"])
                if (
                    calendar is None
                    or calendar["timezone"] != result.scope.timezone
                    or str(calendar["id"]) != result.scope.calendar_version
                    or product["base_unit"] != result.scope.unit
                ):
                    raise StockError("FORECAST_UNIT_OR_CALENDAR_CHANGED", 409)
                first = inputs.data_cutoff_date + timedelta(days=1)
                if first < now.astimezone(ZoneInfo(result.scope.timezone)).date():
                    raise StockError("FORECAST_HORIZON_ALREADY_STARTED", 409)
                targets = round_daily_targets(
                    [(p.day, Decimal(str(p.central_estimate))) for p in result.points]
                )
                eligible = [
                    row
                    for row in lots
                    if (row["site_id"], row["product_id"]) == (key.site_id, key.product_id)
                    and row["eligibility"] == "ELIGIBLE"
                    and row["expiry_kind"] != "UNKNOWN"
                ]
                modeled = tuple(
                    KernelLot(
                        str(row["id"]),
                        row["on_hand"],
                        row["received_at"].astimezone(ZoneInfo(result.scope.timezone)).date(),
                        row["expires_on"],
                        False,
                    )
                    for row in eligible
                )
                days, _ = project_kernel(tuple((p.day, p.target) for p in targets.points), modeled)
                series.append(
                    dict(
                        site_id=str(key.site_id),
                        product_id=str(key.product_id),
                        base_unit=result.scope.unit,
                        actual_provider=result.actual_provider.name,
                        fallback_used=result.fallback_used,
                        fallback_reason=result.fallback_reason,
                        days=[
                            dict(
                                day=day.day.isoformat(),
                                demand=str(day.demand),
                                served=str(day.served),
                                unmet=str(day.unmet),
                                eligible_end=str(day.on_hand),
                            )
                            for day in days
                        ],
                    )
                )
            return dict(
                forecast_run_id=str(forecast_run_id),
                observed_at=now,
                series=series,
                warnings=[
                    "Physical stock only; confirmed supply lacks expiry declarations",
                    "No proposed transfers or P1 reservations included",
                ],
            )
