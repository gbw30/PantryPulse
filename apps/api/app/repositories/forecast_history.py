"""Read one source, revision-aware history, inside a repeatable-read snapshot.

Database identities and clocks are authoritative. A source is the initial dataset
boundary; callers cannot mix source feeds or provide tenant/provider metadata.
"""

from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from app.models import operational as m
from app.schemas.forecast_api import ForecastRequest
from app.services.forecasting.preparation import prepare
from app.services.forecasting.schemas import HistoryBundle

MAX_FACTS = 30_000


class HistoryRejected(ValueError):
    def __init__(self, code: str, status: int = 422):
        super().__init__(code)
        self.code, self.status = code, status


def exact_float(value):
    if value is None:
        return None
    if abs(value) > 2**53:
        raise HistoryRejected("HISTORY_QUANTITY_NOT_EXACT")
    return float(value)


def _rows(conn, model, org, *conditions):
    rows = (
        conn.execute(
            sa.select(model.__table__)
            .where(model.organization_id == org, *conditions)
            .limit(MAX_FACTS + 1)
        )
        .mappings()
        .all()
    )
    if len(rows) > MAX_FACTS:
        raise HistoryRejected("HISTORY_TOO_LARGE")
    return rows


def load_input(engine, org: UUID, request: ForecastRequest):
    """Freeze catalog and facts atomically; no model, stock mutation or hidden write."""
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            conn.execute(sa.text("SET LOCAL statement_timeout = '10000ms'"))
            now = conn.scalar(sa.text("SELECT clock_timestamp()"))
            if request.snapshot_as_of > now:
                raise HistoryRejected("FUTURE_SNAPSHOT")
            source = (
                conn.execute(
                    sa.select(m.DataSource.__table__).where(
                        m.DataSource.organization_id == org, m.DataSource.id == request.source_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if source is None:
                raise HistoryRejected("SOURCE_NOT_FOUND", 404)
            if source["recorded_at"] > request.snapshot_as_of:
                raise HistoryRejected("SOURCE_NOT_VISIBLE")
            sites = _rows(conn, m.Site, org, m.Site.active.is_(True))
            products = _rows(conn, m.Product, org, m.Product.active.is_(True))
            categories = {r["id"]: r for r in _rows(conn, m.Category, org)}
            products = [p for p in products if categories[p["category_id"]]["active"]]
            # Full configured network is intentional; partial scope cannot quietly look ready.
            if (
                not 1 <= sum(s["role"] == "HUB" for s in sites) <= 2
                or not (6 <= sum(s["role"] == "BENEFICIARY" for s in sites) <= 18)
                or len(sites) > 20
                or not 1 <= len(products) <= 20
            ):
                raise HistoryRejected("NETWORK_SCOPE_INCOMPLETE")
            for row in (*sites, *products, *(categories[p["category_id"]] for p in products)):
                if row["recorded_at"] > request.snapshot_as_of:
                    raise HistoryRejected("CATALOG_NOT_VISIBLE")
            calendars = {r["id"]: r for r in _rows(conn, m.SiteCalendar, org)}
            site_by_id = {s["id"]: s for s in sites}
            product_by_id = {p["id"]: p for p in products}
            selected_calendars = {}
            for site in sites:
                cal = calendars.get(site["current_calendar_id"])
                if cal is None or cal["recorded_at"] > request.snapshot_as_of:
                    raise HistoryRejected("CALENDAR_NOT_VISIBLE")
                if request.data_cutoff_date >= now.astimezone(ZoneInfo(cal["timezone"])).date():
                    raise HistoryRejected("CUTOFF_NOT_COMPLETE")
                if (
                    request.data_cutoff_date
                    >= request.snapshot_as_of.astimezone(ZoneInfo(cal["timezone"])).date()
                ):
                    raise HistoryRejected("CUTOFF_NOT_VISIBLE")
                selected_calendars[site["id"]] = cal

            def key(site, product, target):
                return dict(
                    organization_id=org, site_id=site, product_id=product, target_type=target
                )

            scope = [
                dict(
                    key=key(s["id"], p["id"], target),
                    unit=p["base_unit"],
                    timezone=selected_calendars[s["id"]]["timezone"],
                    calendar_version=str(selected_calendars[s["id"]]["id"]),
                    unit_version="operational-base-unit-v1",
                    required=True,
                )
                for s in sites
                for p in products
                for target in (
                    ("DEMAND", "DONATION") if s["role"] == "BENEFICIARY" else ("DONATION",)
                )
            ]

            def source_ref(row, logical):
                return dict(
                    organization_id=org,
                    dataset_id=source["id"],
                    logical_key=logical,
                    revision_id=row["id"],
                    revision=row["revision"],
                    recorded_at=row["recorded_at"],
                )

            def visible(row):
                return row["recorded_at"] <= request.snapshot_as_of

            def calendar_matches(row, site):
                cal = calendars[row["calendar_version_id"]]
                if cal["timezone"] != selected_calendars[site]["timezone"] or not visible(cal):
                    raise HistoryRejected("HISTORY_CALENDAR_CONFLICT")

            classification = source["classification"]
            records = {
                r["id"]: r
                for r in _rows(
                    conn,
                    m.DemandRecord,
                    org,
                    m.DemandRecord.source_id == source["id"],
                    m.DemandRecord.site_id.in_(site_by_id),
                    m.DemandRecord.product_id.in_(product_by_id),
                    m.DemandRecord.local_day.between(
                        request.history_start_date, request.data_cutoff_date
                    ),
                )
            }
            demand = []
            for r in _rows(
                conn,
                m.DemandRevision,
                org,
                m.DemandRevision.record_id.in_(records),
                m.DemandRevision.recorded_at <= request.snapshot_as_of,
            ):
                fact = records[r["record_id"]]
                if not visible(fact):
                    raise HistoryRejected("HISTORY_RECORD_NOT_VISIBLE")
                calendar_matches(r, fact["site_id"])
                demand.append(
                    dict(
                        source=source_ref(r, f"demand:{fact['id']}"),
                        key=key(fact["site_id"], fact["product_id"], "DEMAND"),
                        day=fact["local_day"],
                        requested_units=exact_float(r["requested"]),
                        fulfilled_units=exact_float(r["fulfilled"]),
                        unmet_units=exact_float(r["unmet"]),
                        source_classification=classification,
                    )
                )
            receipts = {
                r["id"]: r for r in _rows(conn, m.Receipt, org, m.Receipt.source_id == source["id"])
            }
            # Select latest visible COMPLETE receipt before filtering its corrected date/site.
            # Filtering first would resurrect superseded revisions after moves or cancellation.
            latest = {}
            for r in _rows(
                conn,
                m.ReceiptRevision,
                org,
                m.ReceiptRevision.receipt_id.in_(receipts),
                m.ReceiptRevision.recorded_at <= request.snapshot_as_of,
            ):
                prior = latest.get(r["receipt_id"])
                if prior is None or r["revision"] > prior["revision"]:
                    latest[r["receipt_id"]] = r
            selected = [
                r
                for r in latest.values()
                if r["receiving_site_id"] in site_by_id
                and request.history_start_date <= r["local_day"] <= request.data_cutoff_date
            ]
            lines = {}
            for line in _rows(
                conn,
                m.ReceiptLine,
                org,
                m.ReceiptLine.receipt_revision_id.in_([r["id"] for r in selected]),
            ):
                lines.setdefault(line["receipt_revision_id"], []).append(line)
            events = []
            day_totals = {}
            for r in selected:
                calendar_matches(r, r["receiving_site_id"])
                if not visible(receipts[r["receipt_id"]]):
                    raise HistoryRejected("HISTORY_RECORD_NOT_VISIBLE")
                items = lines.get(r["id"], [])
                for line in items:
                    group = (r["receiving_site_id"], r["local_day"], line["product_id"])
                    day_totals[group] = day_totals.get(group, 0) + line["received_quantity"]
                    exact_float(day_totals[group])
                # Preserve the whole receipt, including currently inactive products, for identity.
                all_products = (
                    {p["id"]: p for p in _rows(conn, m.Product, org)}
                    if any(line["product_id"] not in product_by_id for line in items)
                    else product_by_id
                )
                events.append(
                    dict(
                        source=source_ref(r, f"receipt:{r['receipt_id']}"),
                        donor_id=r["donor_id"],
                        receiving_site_id=r["receiving_site_id"],
                        received_at=r["received_at"],
                        local_day=r["local_day"],
                        timezone=calendars[r["calendar_version_id"]]["timezone"],
                        is_void=r["is_void"],
                        source_classification=classification,
                        lines=[
                            dict(
                                line_id=line["id"],
                                product_id=line["product_id"],
                                unit=all_products[line["product_id"]]["base_unit"],
                                received_units=exact_float(line["received_quantity"]),
                            )
                            for line in items
                        ],
                    )
                )
            coverage = []
            for r in _rows(
                conn,
                m.DonationCoverageRevision,
                org,
                m.DonationCoverageRevision.source_id == source["id"],
                m.DonationCoverageRevision.site_id.in_(site_by_id),
                m.DonationCoverageRevision.product_id.in_(product_by_id),
                m.DonationCoverageRevision.local_day.between(
                    request.history_start_date, request.data_cutoff_date
                ),
                m.DonationCoverageRevision.recorded_at <= request.snapshot_as_of,
            ):
                calendar_matches(r, r["site_id"])
                logical = f"coverage:{r['site_id']}:{r['product_id']}:{r['local_day']}"
                coverage.append(
                    dict(
                        source=source_ref(r, logical),
                        key=key(r["site_id"], r["product_id"], "DONATION"),
                        day=r["local_day"],
                        complete=r["complete"],
                        source_classification=classification,
                    )
                )
            if len(demand) + len(events) + len(coverage) > MAX_FACTS:
                raise HistoryRejected("HISTORY_TOO_LARGE")
            history = HistoryBundle(
                organization_id=org,
                dataset_id=source["id"],
                scope=scope,
                demand=demand,
                receipts=events,
                coverage=coverage,
            )
            return prepare(
                history,
                data_cutoff_date=request.data_cutoff_date,
                snapshot_as_of=request.snapshot_as_of,
                policy=request.policy,
            )
