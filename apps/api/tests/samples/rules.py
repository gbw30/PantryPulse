"""Shared checks for the sample networks: the W1 import rules every sample must pass
(wave-3.md, lane w3-samples; decisions W0-08 §7–§8 and W2-06)."""

import csv
import io
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from app.schemas.v1_imports import ImportSettings
from app.services.enrichment.distance import haversine_miles
from app.services.imports.validate import validate_files

README = Path(__file__).resolve().parents[4] / "data" / "samples" / "README.md"
SENDERS = ("hub", "distribution_center")
QUANTITY_FILES = ("inventory", "demand_history", "inbound", "donation_history")


def rows(sample, name: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(sample.files[name])))


def validate(sample):
    settings = ImportSettings(mode=sample.mode, timezone=sample.timezone,
                              as_of_date=sample.as_of_date)
    return validate_files({n: io.BytesIO(t.encode()) for n, t in sample.files.items()}, settings)


def assert_w1_rules(sample) -> None:
    locations = rows(sample, "locations")
    products = rows(sample, "products")
    senders = [loc for loc in locations if loc["type"] in SENDERS]
    receivers = [loc for loc in locations if loc["type"] not in SENDERS]
    assert len(senders) == 1 and receivers

    # Given coordinates skip geocoding, so nothing fills a missing rate later.
    assert all(loc["latitude"] and loc["longitude"] for loc in locations)
    for loc in receivers:
        if loc["type"] == "pantry":
            assert loc["poverty_rate"] and loc["snap_rate"], loc

    hub = senders[0]
    for loc in receivers:
        miles = haversine_miles(Decimal(hub["latitude"]), Decimal(hub["longitude"]),
                                Decimal(loc["latitude"]), Decimal(loc["longitude"]))
        assert miles <= 150, (loc["location_id"], miles)

    demand = rows(sample, "demand_history")
    for product in products:  # EGP's singleton rule: at least 2 receivers per product
        with_demand = {d["location_id"] for d in demand
                       if d["product_id"] == product["product_id"] and d["quantity"]}
        assert len(with_demand) >= 2, product["product_id"]

    for product in products:
        assert Decimal(product["handling_units_per_unit"] or "1") % 1 == 0, product
        if sample.mode == "RETAIL":
            assert product["unit_value_usd"], product

    for name in QUANTITY_FILES:
        for row in rows(sample, name):
            assert row["quantity"] == "" or 0 <= int(row["quantity"]) <= 100_000, (name, row)

    as_of = sample.as_of_date
    history = [r["date"] for name in ("demand_history", "donation_history")
               for r in rows(sample, name)]
    assert max(history) <= as_of.isoformat()
    assert min(history) >= (as_of - timedelta(days=90)).isoformat()
    assert all(r["arrival_date"] > as_of.isoformat() for r in rows(sample, "inbound"))

    for batch in rows(sample, "inventory"):  # short ids stay readable in frozen batch ids
        assert "/" not in batch["batch_id"] and len(batch["batch_id"]) <= 16, batch
