# covers: V1-A05
"""The fictional Pantry sample: 1 hub + 8 pantries, ~6 products, 90 days (W3-P01)."""

import re
from datetime import date, timedelta

from app.services.samples.pantry import PRODUCTS, pantry_sample
from tests.samples.rules import README, assert_plausible_ages, assert_w1_rules, rows, validate

TODAY = date(2026, 11, 8)


def test_shape_1_hub_8_pantries_6_products_90_days():
    sample = pantry_sample(TODAY)
    assert sample.mode == "PANTRY"
    types = [loc["type"] for loc in rows(sample, "locations")]
    assert sorted(types) == ["hub"] + ["pantry"] * 8
    products = rows(sample, "products")
    assert len(products) == 6
    demand = rows(sample, "demand_history")
    assert len({d["date"] for d in demand}) == 90
    pantries = {loc["location_id"] for loc in rows(sample, "locations") if loc["type"] == "pantry"}
    # every pantry × product has a full 90-day series; the hub has no demand (it only sends)
    assert {(d["location_id"], d["product_id"]) for d in demand} == {
        (p, q["product_id"]) for p in pantries for q in products}
    assert len(demand) == 8 * 6 * 90
    # unknown days stay blank (never zero), as in data/demo/forecasting-v1.json
    assert any(d["quantity"] == "" for d in demand)
    assert all(d["basis"] == "demand" for d in demand)


def test_dates_relative_to_today():
    sample = pantry_sample(TODAY)
    assert sample.as_of_date == TODAY
    dates = sorted({d["date"] for d in rows(sample, "demand_history")})
    assert dates[-1] == (TODAY - timedelta(days=1)).isoformat()
    assert dates[0] == (TODAY - timedelta(days=90)).isoformat()
    expiries = [b["expiry_date"] for b in rows(sample, "inventory") if b["expiry_date"]]
    assert expiries and min(expiries) > TODAY.isoformat()  # no batch is expired on day one
    assert max(expiries) > (TODAY + timedelta(days=30)).isoformat()
    arrivals = [r["arrival_date"] for r in rows(sample, "inbound")]
    assert arrivals and all(TODAY.isoformat() < a <= (TODAY + timedelta(days=7)).isoformat()
                            for a in arrivals)
    later = pantry_sample(TODAY + timedelta(days=10))
    assert later.as_of_date == TODAY + timedelta(days=10)


def test_city_level_coordinates_no_street_addresses():
    locations = rows(pantry_sample(TODAY), "locations")
    for loc in locations:
        assert not re.search(r"\d", loc["street"]), loc  # no house number, no real building
        for column in ("latitude", "longitude"):
            assert re.fullmatch(r"-?\d+\.\d{1,2}", loc[column]), loc  # city level: 2 decimals
    assert len({(loc["latitude"], loc["longitude"]) for loc in locations}) == len(locations)
    assert len({loc["city"] for loc in locations}) == len(locations)


def test_poverty_snap_prefilled_labeled_sample_values():
    # The in-app "sample values" source label is the lead's CR-w3-samples-1 (enrichment).
    sample = pantry_sample(TODAY)
    for loc in rows(sample, "locations"):
        if loc["type"] == "pantry":
            assert 0 < float(loc["poverty_rate"]) < 1 and 0 < float(loc["snap_rate"]) < 1
    assert "sample values" in README.read_text(encoding="utf-8")


def test_validates_clean_through_validate_files():
    sample = pantry_sample(TODAY)
    report = validate(sample)
    assert report.ok, report.errors[:5]
    assert report.error_count == 0
    assert set(sample.files) == {"locations", "products", "inventory", "demand_history",
                                 "routes", "inbound", "donation_history"}
    assert_w1_rules(sample)
    assert_plausible_ages(sample, {p[0]: p[-1] for p in PRODUCTS})


def test_deterministic_for_seed_and_date():
    assert pantry_sample(TODAY).files == pantry_sample(TODAY).files
    assert pantry_sample(TODAY, seed=2).files != pantry_sample(TODAY).files
    shifted = pantry_sample(TODAY + timedelta(days=3))
    # A later date shifts every date (the weekly pattern follows real weekdays).
    assert rows(shifted, "demand_history")[0]["date"] == (
        TODAY - timedelta(days=87)).isoformat()
    assert shifted.files["locations"] == pantry_sample(TODAY).files["locations"]


def test_labeled_sample_data_fictional():
    # In the app the label comes from networks.is_sample (asserted in test_seed.py).
    sample = pantry_sample(TODAY)
    assert "sample" in sample.name.lower()
    assert all(loc["name"].startswith("Sample ") for loc in rows(sample, "locations"))
    assert "Sample data — fictional" in README.read_text(encoding="utf-8")
