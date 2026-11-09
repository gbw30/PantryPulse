"""The fictional Retail sample: one distribution center + 20 stores of an invented chain in
Central Florida, 50 generic priced products, 90 days of sales and batches with varied expiry
(W3-P02). Product names are generic descriptions, never brands (anti-impersonation)."""

import random
from datetime import date, timedelta
from functools import partial

from app.services.samples.network import HISTORY_DAYS, NO_STREET, SampleNetwork, batch, to_csv

# Batches: at least 1 day to expiry; received in the last 10 days.
_batch = partial(batch, soonest=1, received_within=10)
SEED = 20261105
CHAIN = "Heronfield Market"
NAME = f"{CHAIN} — sample retail network"
DC = ("DC1", "Orlando", "32801", "28.54", "-81.38")
# id, city, zip, lat, lon (city centers, 2 decimals), receiving capacity per day
# (handling units; blank = no limit), size (sales multiplier)
STORES = (
    ("S01", "Kissimmee", "34741", "28.29", "-81.41", 900, 1.2),
    ("S02", "Sanford", "32771", "28.80", "-81.27", None, 1.0),
    ("S03", "Winter Park", "32789", "28.60", "-81.34", 700, 1.1),
    ("S04", "Apopka", "32703", "28.68", "-81.51", None, 0.9),
    ("S05", "Clermont", "34711", "28.55", "-81.77", None, 0.9),
    ("S06", "Leesburg", "34748", "28.81", "-81.88", 500, 0.7),
    ("S07", "DeLand", "32720", "29.03", "-81.30", None, 0.8),
    ("S08", "Daytona Beach", "32114", "29.21", "-81.02", 800, 1.3),
    ("S09", "Titusville", "32780", "28.61", "-80.81", None, 0.7),
    ("S10", "Cocoa", "32922", "28.39", "-80.74", None, 0.6),
    ("S11", "Melbourne", "32901", "28.08", "-80.61", 800, 1.2),
    ("S12", "Palm Bay", "32905", "28.03", "-80.59", None, 0.9),
    ("S13", "Lakeland", "33801", "28.04", "-81.95", 800, 1.2),
    ("S14", "Winter Haven", "33880", "28.02", "-81.73", None, 0.8),
    ("S15", "Ocala", "34471", "29.19", "-82.14", None, 1.0),
    ("S16", "St. Cloud", "34769", "28.25", "-81.28", None, 0.7),
    ("S17", "Haines City", "33844", "28.11", "-81.62", 400, 0.6),
    ("S18", "New Smyrna Beach", "32168", "29.03", "-80.93", None, 0.7),
    ("S19", "Tampa", "33602", "27.95", "-82.46", 1000, 1.4),
    ("S20", "Sebring", "33870", "27.50", "-81.44", None, 0.6),
)
# id, name, unit, unit value (USD), handling units per unit, daily sales at size 1,
# shelf life in days (None = non-expiring)
PRODUCTS = (
    ("MILK-WH", "Whole milk, 1 gal", "each", "4.29", 1, 12, 14),
    ("MILK-2P", "Reduced-fat milk, 1 gal", "each", "4.19", 1, 10, 14),
    ("EGGS-12", "Large eggs, dozen", "each", "3.49", 1, 14, 28),
    ("YOG-GRK", "Plain Greek yogurt, 32 oz", "each", "5.99", 1, 4, 21),
    ("YOG-CUP", "Fruit yogurt cup, 6 oz", "each", "0.99", 1, 15, 21),
    ("CHS-CHD", "Cheddar cheese, 8 oz", "each", "3.79", 1, 6, 45),
    ("BUTTER", "Salted butter, 1 lb", "each", "4.99", 1, 5, 60),
    ("SOURCRM", "Sour cream, 16 oz", "each", "2.49", 1, 4, 21),
    ("OJ-52", "Orange juice, 52 oz", "each", "4.49", 1, 7, 10),
    ("BRD-WHT", "Sliced white bread", "each", "2.79", 1, 12, 6),
    ("BRD-WW", "Whole wheat bread", "each", "3.29", 1, 8, 6),
    ("BAGEL-6", "Plain bagels, 6 count", "each", "3.99", 1, 4, 5),
    ("TORT-10", "Flour tortillas, 10 count", "each", "2.99", 1, 5, 14),
    ("MUFFIN-4", "Blueberry muffins, 4 count", "each", "4.49", 1, 3, 4),
    ("BANANA", "Bananas", "lb", "0.59", 1, 30, 6),
    ("APPLE", "Gala apples", "lb", "1.49", 1, 12, 21),
    ("STRAWB", "Strawberries, 1 lb", "each", "3.99", 1, 8, 4),
    ("ROMAINE", "Romaine hearts, 3 count", "each", "3.49", 1, 6, 7),
    ("SPINACH", "Baby spinach, 5 oz", "each", "3.29", 1, 5, 6),
    ("TOMATO", "Roma tomatoes", "lb", "1.29", 1, 9, 7),
    ("AVOCADO", "Avocados", "each", "1.25", 1, 10, 5),
    ("ONION-3", "Yellow onions, 3 lb bag", "each", "2.99", 1, 5, 30),
    ("POTATO-5", "Russet potatoes, 5 lb bag", "each", "4.49", 1, 5, 30),
    ("CARROT-2", "Carrots, 2 lb bag", "each", "1.99", 1, 4, 21),
    ("GRAPES", "Red grapes", "lb", "2.49", 1, 6, 7),
    ("ORANGE-4", "Oranges, 4 lb bag", "each", "5.49", 1, 4, 21),
    ("CHKN-BR", "Chicken breast", "lb", "3.99", 1, 10, 4),
    ("BEEF-GR", "Ground beef 80/20", "lb", "5.49", 1, 9, 3),
    ("PORK-CH", "Pork chops", "lb", "4.29", 1, 4, 4),
    ("SALMON", "Salmon fillet", "lb", "9.99", 1, 3, 3),
    ("TURKEY", "Sliced deli turkey, 1 lb", "each", "7.99", 1, 4, 10),
    ("SAUSAGE", "Breakfast sausage, 12 oz", "each", "4.29", 1, 3, 14),
    ("HUMMUS", "Hummus, 10 oz", "each", "3.99", 1, 3, 14),
    ("SALSA", "Fresh salsa, 16 oz", "each", "4.29", 1, 3, 10),
    ("SALADKIT", "Chopped salad kit", "each", "3.99", 1, 5, 5),
    ("FRZ-PIZ", "Frozen cheese pizza", "each", "5.99", 1, 4, None),
    ("FRZ-VEG", "Frozen mixed vegetables, 16 oz", "each", "1.99", 1, 5, None),
    ("ICECRM", "Vanilla ice cream, 48 oz", "each", "4.99", 1, 4, None),
    ("RICE-5", "Long-grain rice, 5 lb", "each", "4.99", 1, 3, 365),
    ("PASTA", "Spaghetti, 1 lb", "each", "1.49", 1, 6, 540),
    ("BEANS", "Black beans, 15 oz can", "each", "1.09", 1, 6, 720),
    ("SOUP", "Chicken noodle soup, can", "each", "1.79", 1, 5, 720),
    ("CEREAL", "Toasted oat cereal, 12 oz", "each", "3.99", 1, 5, 270),
    ("PNUTB", "Peanut butter, 16 oz", "each", "2.99", 1, 4, 270),
    ("COFFEE", "Ground coffee, 12 oz", "each", "7.99", 1, 3, 365),
    ("WATER-24", "Bottled water, 24-pack", "case", "4.99", 2, 8, None),
    ("COLA-12", "Cola, 12-pack cans", "case", "6.49", 2, 5, 270),
    ("JUICE-AP", "Apple juice, 64 oz", "each", "3.29", 1, 4, 120),
    ("TOWEL-6", "Paper towels, 6 rolls", "case", "8.99", 3, 3, None),
    ("TISSUE-12", "Bath tissue, 12 rolls", "case", "9.99", 3, 3, None),
)
WEEKDAY = (0.9, 0.85, 0.9, 1.0, 1.15, 1.35, 1.2)  # Mon..Sun; weekend shopping
DONOR = "Sample vendor promotion (fictional)"


def retail_sample(today: date, seed: int = SEED) -> SampleNetwork:
    """Sales end yesterday; the inventory describes `today` (the as-of date)."""
    rng = random.Random(seed)
    days = [today - timedelta(days=HISTORY_DAYS - i) for i in range(HISTORY_DAYS)]
    shelf = {p[0]: p[-1] for p in PRODUCTS}

    def on(offset: int) -> str:
        return (today + timedelta(days=offset)).isoformat()

    locations = [dict(location_id=DC[0], name=f"Sample {CHAIN} DC — {DC[1]}",
                      type="distribution_center", street=NO_STREET, city=DC[1], state="FL",
                      zip=DC[2], latitude=DC[3], longitude=DC[4])]
    locations += [dict(location_id=s, name=f"Sample {CHAIN} — {city}", type="store",
                       street=NO_STREET, city=city, state="FL", zip=zip_code, latitude=lat,
                       longitude=lon, receiving_capacity_per_day=capacity)
                  for s, city, zip_code, lat, lon, capacity, _ in STORES]
    products = [dict(product_id=p, name=name, unit=unit, unit_value_usd=value,
                     handling_units_per_unit=handling)
                for p, name, unit, value, handling, _, _ in PRODUCTS]

    sales = []
    for store, *_, size in STORES:
        for product, *_, base, _ in PRODUCTS:
            for day in days:
                level = base * size * WEEKDAY[day.weekday()] * max(0.0, rng.gauss(1, 0.2))
                unknown = rng.random() < 0.005  # a day the register export missed
                sales.append(dict(location_id=store, product_id=product, date=day.isoformat(),
                                  quantity="" if unknown else round(level), basis="sales"))

    chain_size = sum(s[-1] for s in STORES)
    inventory = []
    for product, *_, base, life in PRODUCTS:
        for n, share in enumerate((0.4, 0.9), 1):  # the DC's two most recent deliveries
            inventory.append(_batch(DC[0], product, f"B{n}",
                                    round(base * chain_size * rng.uniform(1, 2)), life, share,
                                    rng, on))
        for store, *_, size in STORES:
            # Some stores are overstocked on short-life items (expiry risk), some short.
            for n in range(1, rng.choice((1, 1, 2)) + 1):
                inventory.append(_batch(store, product, f"B{n}",
                                        round(base * size * rng.uniform(0.5, 5)), life,
                                        rng.uniform(0.15, 1.0), rng, on))

    inbound = []
    for i, product in enumerate(("MILK-WH", "EGGS-12", "BRD-WHT", "BANANA", "CHKN-BR",
                                 "PASTA", "WATER-24", "TOWEL-6")):
        arrival = 1 + i % 7
        inbound.append(_arrival(DC[0], product, 400 + 50 * i, arrival, shelf[product], on,
                                "supplier", f"Sample PO {100 + i}"))
    for i, (store, product) in enumerate((("S19", "MILK-WH"), ("S08", "STRAWB"),
                                          ("S11", "SALMON"), ("S01", "AVOCADO"))):
        inbound.append(_arrival(store, product, 40 + 10 * i, 1 + i, shelf[product], on,
                                "dc_delivery", f"Sample transfer {200 + i}"))

    donations = []
    for product in ("CEREAL", "JUICE-AP"):  # weekly vendor promotion stock at the DC
        for day in days[::7]:
            reported = rng.random() < 0.7
            donations.append(dict(location_id=DC[0], product_id=product, date=day.isoformat(),
                                  quantity=round(rng.uniform(20, 120)) if reported else 0,
                                  donor=DONOR))

    return SampleNetwork(name=NAME, mode="RETAIL", as_of_date=today, files={
        "locations": to_csv("locations", locations),
        "products": to_csv("products", products),
        "inventory": to_csv("inventory", inventory),
        "demand_history": to_csv("demand_history", sales),
        "inbound": to_csv("inbound", inbound),
        "donation_history": to_csv("donation_history", donations),
    })



def _arrival(location: str, product: str, quantity: int, day: int, life: int | None, on,
             source: str, reference: str) -> dict[str, object]:
    expiry = {"non_expiring": "true"} if life is None else {"expiry_date": on(day + life)}
    return dict(location_id=location, product_id=product, quantity=quantity,
                arrival_date=on(day), source=source, reference=reference, **expiry)
