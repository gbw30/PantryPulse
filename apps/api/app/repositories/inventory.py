"""Bounded, tenant-scoped, repeatable-read physical inventory snapshots."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa

from app.models import operational as m
from app.schemas.inventory_api import InventoryLotView, InventorySnapshot

MAX_LOTS = 500
REASONS = ("HELD", "INELIGIBLE", "UNKNOWN_ELIGIBILITY", "UNKNOWN_EXPIRY", "EXPIRED")


class InventoryError(ValueError):
    def __init__(self, code, status=422):
        super().__init__(code)
        self.code, self.status = code, status


def build_snapshot(*, site, product, version, lots, now):
    try:
        today = now.astimezone(ZoneInfo(site["timezone"])).date()
    except (ZoneInfoNotFoundError, ValueError):
        raise InventoryError("SITE_CALENDAR_UNAVAILABLE", 503) from None
    excluded = dict.fromkeys(REASONS, 0)
    views = []
    on_hand = usable = 0
    for lot in lots:
        reason = None
        if lot["eligibility"] != "ELIGIBLE":
            reason = ("UNKNOWN_ELIGIBILITY" if lot["eligibility"] == "UNKNOWN"
                      else lot["eligibility"])
        elif lot["expiry_kind"] == "UNKNOWN":
            reason = "UNKNOWN_EXPIRY"
        elif lot["expiry_kind"] == "DATED" and lot["expires_on"] < today:
            reason = "EXPIRED"
        quantity = lot["on_hand"]
        on_hand += quantity
        if reason:
            excluded[reason] += quantity
        else:
            usable += quantity
        views.append(InventoryLotView(
            lot_id=lot["id"], batch_key=lot["batch_key"], on_hand_quantity=quantity,
            eligibility=lot["eligibility"], expiry_kind=lot["expiry_kind"],
            expires_on=lot["expires_on"], metadata_version=lot["metadata_version"],
            usable=reason is None, exclusion_reason=reason,
        ))
    return InventorySnapshot(
        site_id=site["id"], site_name=site["name"], product_id=product["id"],
        product_name=product["name"], base_unit=product["base_unit"],
        timezone=site["timezone"], local_date=today, observed_at=now,
        inventory_version=version, on_hand_quantity=on_hand, usable_quantity=usable,
        excluded_quantity=on_hand - usable, excluded_quantities=excluded, lots=tuple(views),
    )


def load_inventory(engine, organization_id, site_id, product_id):
    """No insert, inference, reservation, future arrival or worker call on this path."""
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            conn.execute(sa.text("SET LOCAL statement_timeout = '10000ms'"))
            now = conn.scalar(sa.text("SELECT transaction_timestamp()"))

            def owned(model, identity):
                return conn.execute(sa.select(model.__table__).where(
                    model.organization_id == organization_id, model.id == identity,
                )).mappings().one_or_none()

            site = owned(m.Site, site_id)
            product = owned(m.Product, product_id)
            if site is None or product is None:
                raise InventoryError("NOT_FOUND", 404)
            calendar = owned(m.SiteCalendar, site["current_calendar_id"])
            if calendar is None:
                raise InventoryError("SITE_CALENDAR_UNAVAILABLE", 503)
            version = conn.scalar(sa.select(m.InventoryVersion.version).where(
                m.InventoryVersion.organization_id == organization_id,
                m.InventoryVersion.site_id == site_id,
                m.InventoryVersion.product_id == product_id,
            ))
            lots = conn.execute(sa.select(m.InventoryLot.__table__).where(
                m.InventoryLot.organization_id == organization_id,
                m.InventoryLot.site_id == site_id, m.InventoryLot.product_id == product_id,
                m.InventoryLot.on_hand > 0,
            ).order_by(m.InventoryLot.expires_on.asc().nulls_last(), m.InventoryLot.id)
                .limit(MAX_LOTS + 1)).mappings().all()
            if len(lots) > MAX_LOTS:
                raise InventoryError("INVENTORY_TOO_LARGE")
            return build_snapshot(
                site={**site, "timezone": calendar["timezone"]}, product=product,
                version=version, lots=lots, now=now,
            )
