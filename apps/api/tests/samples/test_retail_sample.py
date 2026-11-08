# covers: V1-A05
"""The fictional Retail sample: 1 DC + 20 stores, ~50 priced products, varied expiry (W3-P02)."""

import re
from datetime import date, timedelta
from decimal import Decimal

from app.services.samples.retail import CHAIN, retail_sample
from tests.samples.rules import assert_w1_rules, rows, validate

TODAY = date(2026, 11, 8)
# Real US grocery chains and CPG brands (anti-impersonation, V1-SPEC §8). Matched as whole words,
# ignoring case, against every name in the sample.
REAL_BRANDS = (
    "Publix", "Winn-Dixie", "Winn Dixie", "Walmart", "Great Value", "Kroger", "Target", "Costco",
    "Kirkland", "Aldi", "Lidl", "Whole Foods", "Trader Joe", "Safeway", "Albertsons", "Sprouts",
    "Wegmans", "H-E-B", "Food Lion", "Piggly Wiggly", "Save A Lot", "Fresh Market", "Sam's Club",
    "BJ's", "Harris Teeter", "Meijer", "Hy-Vee", "Giant", "Stop & Shop", "Dollar General",
    "Family Dollar", "Coca-Cola", "Coke", "Pepsi", "Sprite", "Dr Pepper", "Kellogg", "Nestle",
    "Nestlé", "Kraft", "Heinz", "General Mills", "Tyson", "Perdue", "Dole", "Chiquita",
    "Del Monte", "Campbell", "Hershey", "Mars", "Frito-Lay", "Lay's", "Doritos", "Cheerios",
    "Oreo", "Nabisco", "Ritz", "Tropicana", "Minute Maid", "Simply", "Florida's Natural",
    "Gatorade", "Dannon", "Danone", "Chobani", "Yoplait", "Land O'Lakes", "Horizon",
    "Organic Valley", "Sara Lee", "Wonder", "Nature's Own", "Pillsbury", "Hormel", "Oscar Mayer",
    "Smithfield", "Jimmy Dean", "Barilla", "Ragu", "Prego", "Quaker", "Post", "Jif", "Skippy",
    "Smucker", "Ben & Jerry", "Breyers", "Blue Bell", "Sunkist", "Green Giant", "Birds Eye",
    "Stouffer", "DiGiorno", "Pringles", "Goldfish", "Keebler", "Starbucks", "Folgers",
    "Maxwell House", "Lipton", "Arizona", "Dasani", "Aquafina", "Poland Spring", "Zephyrhills",
    "Deer Park", "Fiji", "Bounty", "Charmin", "Scott", "Kleenex", "Cottonelle", "Uncle Ben",
    "Mahatma", "Goya", "Bush's", "Hunt's", "Philadelphia", "Sabra", "Tostitos", "Boar's Head",
)


def test_shape_1_dc_20_stores_50_products_with_unit_value_usd():
    sample = retail_sample(TODAY)
    assert sample.mode == "RETAIL"
    types = [loc["type"] for loc in rows(sample, "locations")]
    assert sorted(types) == ["distribution_center"] + ["store"] * 20
    products = rows(sample, "products")
    assert len(products) == 50
    assert all(Decimal(p["unit_value_usd"]) > 0 for p in products)
    assert len({p["unit"] for p in products}) > 1  # each product keeps its own unit
    demand = rows(sample, "demand_history")
    assert len({d["date"] for d in demand}) == 90
    assert max(d["date"] for d in demand) == (TODAY - timedelta(days=1)).isoformat()
    assert {d["basis"] for d in demand} == {"sales"}
    assert sample.as_of_date == TODAY


def test_varied_expiry_including_within_7_days():
    batches = rows(retail_sample(TODAY), "inventory")
    days = sorted((date.fromisoformat(b["expiry_date"]) - TODAY).days
                  for b in batches if b["expiry_date"])
    assert days[0] >= 1  # nothing already expired on the as-of date
    assert sum(d <= 7 for d in days) >= 50  # many batches must sell within a week
    assert any(d <= 2 for d in days) and any(d > 180 for d in days)
    assert any(b["non_expiring"] == "true" for b in batches)
    assert len(set(days)) > 30


def test_fictional_chain_name_no_real_brands():
    sample = retail_sample(TODAY)
    assert CHAIN in sample.name and sample.label == "Sample data — fictional"
    names = [sample.name, CHAIN] + [r["name"] for name in ("locations", "products")
                                    for r in rows(sample, name)]
    names += [r["donor"] for r in rows(sample, "donation_history")]
    names += [r["reference"] for r in rows(sample, "inbound")]
    pattern = re.compile(r"\b(" + "|".join(re.escape(b) for b in REAL_BRANDS) + r")\b",
                         re.IGNORECASE)
    hits = sorted({m.group(0) for text in names for m in pattern.finditer(text)})
    assert not hits, hits
    assert all(loc["name"].startswith("Sample ") for loc in rows(sample, "locations"))


def test_validates_clean():
    sample = retail_sample(TODAY)
    report = validate(sample)
    assert report.ok, report.errors[:5]
    assert report.error_count == 0
    assert_w1_rules(sample)
    assert retail_sample(TODAY).files == sample.files  # deterministic for the seed and date


def test_includes_inbound_and_donation_history_rows():
    sample = retail_sample(TODAY)
    inbound = rows(sample, "inbound")
    assert len(inbound) >= 5
    assert {r["source"] for r in inbound} >= {"supplier", "dc_delivery"}
    assert any(r["location_id"].startswith("S") for r in inbound)  # a DC delivery to a store
    donations = rows(sample, "donation_history")
    assert donations
    assert any(r["quantity"] == "0" for r in donations)  # reported, nothing received
