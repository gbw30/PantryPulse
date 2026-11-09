"""The fictional Pantry sample: 1 hub + 8 pantries in North Central Florida, 6 products,
90 days of demand (W3-P01). It extends the `data/demo/forecasting-v1.json` style: the hub only
sends and has no demand, a few unknown days stay blank (never zero), and donation reports
include genuine zero days."""

import random
from datetime import date, timedelta
from functools import partial

from app.services.samples.network import HISTORY_DAYS, NO_STREET, SampleNetwork, batch, to_csv

# Batches: at least 2 days to expiry; received in the last 3 weeks.
_batch = partial(batch, soonest=2, received_within=21)
SEED = 20261104
NAME = "Sample Pantry Network (North Central Florida)"
HUB = ("H01", "Gainesville", "32601", "29.65", "-82.32")
# id, city, zip, lat, lon (city centers, 2 decimals), poverty rate, SNAP rate (sample values),
# receiving capacity per day (handling units; blank = no limit), size (demand multiplier)
PANTRIES = (
    ("P01", "Ocala", "34471", "29.19", "-82.14", "0.17", "0.19", 240, 1.3),
    ("P02", "Lake City", "32055", "30.19", "-82.64", "0.24", "0.27", None, 1.0),
    ("P03", "Palatka", "32177", "29.65", "-81.64", "0.31", "0.33", 160, 0.9),
    ("P04", "Starke", "32091", "29.94", "-82.11", "0.22", "0.24", None, 0.7),
    ("P05", "Live Oak", "32064", "30.29", "-82.98", "0.27", "0.30", 120, 0.8),
    ("P06", "Chiefland", "32626", "29.47", "-82.86", "0.25", "0.26", None, 0.6),
    ("P07", "Williston", "32696", "29.39", "-82.45", "0.20", "0.22", 100, 0.6),
    ("P08", "High Springs", "32643", "29.83", "-82.60", "0.13", "0.12", None, 0.7),
)
# id, name, unit, unit value (USD), handling units per unit, daily demand at size 1,
# shelf life in days (None = non-expiring)
PRODUCTS = (
    ("RICE", "Rice, 2 lb bags", "case", "18.00", 2, 6, 365),
    ("BEANS", "Canned beans", "case", "21.00", 2, 5, 540),
    ("MILK", "Shelf-stable milk", "case", "24.00", 2, 4, 120),
    ("PNUTB", "Peanut butter", "case", "30.00", 1, 3, 270),
    ("WATER", "Bottled water, 24-pack", "case", "5.00", 2, 7, None),
    ("PRODUCE", "Fresh produce box", "box", "15.00", 1, 8, 6),
)
WEEKDAY = (1.15, 1.0, 0.95, 1.05, 1.2, 1.3, 0.35)  # Mon..Sun; most pantries close Sundays
DONATED = (("H01", "RICE"), ("H01", "BEANS"), ("H01", "PRODUCE"), ("P03", "PRODUCE"))
DONORS = ("Sample food drive (fictional)", "Sample grocery partner (fictional)")


def pantry_sample(today: date, seed: int = SEED) -> SampleNetwork:
    """History ends yesterday; the inventory describes `today` (the as-of date)."""
    rng = random.Random(seed)
    days = [today - timedelta(days=HISTORY_DAYS - i) for i in range(HISTORY_DAYS)]

    def on(offset: int) -> str:
        return (today + timedelta(days=offset)).isoformat()

    locations = [dict(location_id=HUB[0], name=f"Sample Hub — {HUB[1]}", type="hub",
                      street=NO_STREET, city=HUB[1], state="FL", zip=HUB[2],
                      latitude=HUB[3], longitude=HUB[4])]
    locations += [dict(location_id=p, name=f"Sample Pantry — {city}", type="pantry",
                       street=NO_STREET, city=city, state="FL", zip=zip_code, latitude=lat,
                       longitude=lon, receiving_capacity_per_day=capacity, poverty_rate=poverty,
                       snap_rate=snap)
                  for p, city, zip_code, lat, lon, poverty, snap, capacity, _ in PANTRIES]
    products = [dict(product_id=p, name=name, unit=unit, unit_value_usd=value,
                     handling_units_per_unit=handling)
                for p, name, unit, value, handling, _, _ in PRODUCTS]

    demand = []
    for pantry, *_, size in PANTRIES:
        for product, *_, base, _ in PRODUCTS:
            for day in days:
                level = base * size * WEEKDAY[day.weekday()] * max(0.0, rng.gauss(1, 0.18))
                unknown = rng.random() < 0.012  # a day nobody reported
                demand.append(dict(location_id=pantry, product_id=product, date=day.isoformat(),
                                   quantity="" if unknown else round(level), basis="demand"))

    network_size = sum(p[-1] for p in PANTRIES)
    inventory = []
    for product, *_, base, shelf in PRODUCTS:
        # The hub holds 1-2 weeks of network demand, in batches that expire at different times.
        for n, share in enumerate((0.25, 0.6, 0.95), 1):
            quantity = round(base * network_size * rng.uniform(3, 5))
            inventory.append(_batch(HUB[0], product, f"B{n}", quantity, shelf, share, rng, on))
        for pantry, *_, size in PANTRIES:  # some pantries run short within days, some don't
            quantity = round(base * size * rng.uniform(0.5, 6))
            inventory.append(_batch(pantry, product, "B1", quantity, shelf, rng.uniform(0.3, 0.9),
                                    rng, on))

    inbound = [
        dict(location_id="H01", product_id="RICE", quantity=180, arrival_date=on(2),
             expiry_date=on(330), source="supplier", reference="Sample PO A"),
        dict(location_id="H01", product_id="BEANS", quantity=120, arrival_date=on(4),
             expiry_date=on(500), source="donation", reference="Sample food drive"),
        dict(location_id="H01", product_id="WATER", quantity=200, arrival_date=on(5),
             non_expiring="true", source="supplier", reference="Sample PO B"),
        dict(location_id="P02", product_id="PRODUCE", quantity=30, arrival_date=on(1),
             expiry_date=on(6), source="donation", reference="Sample farm share"),
    ]

    donations = []
    for location, product in DONATED:
        for i, day in enumerate(days):
            reported = rng.random() < 0.8
            quantity = round(rng.uniform(5, 40)) if reported else 0  # 0 = nothing received
            donations.append(dict(location_id=location, product_id=product,
                                  date=day.isoformat(),
                                  quantity="" if i == 40 else quantity,  # one unknown day
                                  donor=rng.choice(DONORS)))

    routes = [dict(from_location_id=HUB[0], to_location_id=p,
                   cost_per_handling_unit=f"{rng.uniform(0.3, 1.2):.2f}",
                   capacity_per_batch=300 if p == "P05" else None)
              for p, *_ in PANTRIES]
    routes.append(dict(from_location_id="P01", to_location_id="P07", disabled="true"))

    return SampleNetwork(name=NAME, mode="PANTRY", as_of_date=today, files={
        "locations": to_csv("locations", locations),
        "products": to_csv("products", products),
        "inventory": to_csv("inventory", inventory),
        "demand_history": to_csv("demand_history", demand),
        "routes": to_csv("routes", routes),
        "inbound": to_csv("inbound", inbound),
        "donation_history": to_csv("donation_history", donations),
    })
