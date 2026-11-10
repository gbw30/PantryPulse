"""Blank templates, the column guide (W1-D03) and examples (W3-P03)."""

from datetime import date
from functools import cache
from typing import Literal

from app.schemas.v1_networks import (
    REQUIRED_TEMPLATES,
    Template,
    TemplateCatalog,
    TemplateColumn,
    TemplateName,
)
from app.schemas.v1_planning import ROLES_BY_MODE, NetworkMode
from app.services.imports.columns import COLUMNS, header
from app.services.presenter_access import AccessError
from app.services.samples.pantry import pantry_sample

EXAMPLE_AS_OF = date(2026, 11, 4)  # the examples' as-of date; their history ends the day before
NO_LIMIT = "capacity not provided — no limit assumed"
SALES_LABEL = "sales (undercounts demand when shelves were empty)"
BLANK_UNKNOWN = "Leave blank if unknown: a blank cell is kept as unknown, never as 0."

DESCRIPTIONS: dict[TemplateName, str] = {
    "locations": "Every hub/pantry (Pantry mode) or distribution center/store (Retail mode).",
    "products": "Every product you track, with the unit its quantities are counted in.",
    "inventory": "Stock on hand on the as-of date, one row per batch.",
    "demand_history": "Daily demand or sales per location and product, up to 90 days.",
    "routes": "Optional. Overrides or disables the estimated routes between locations.",
    "inbound": "Optional. Confirmed future arrivals in the seven days after the as-of date.",
    "donation_history": "Optional. Donations received per location, product and day.",
}

# column -> (unit, meaning, effect on the plan); shared names are overridden per template below.
GUIDE: dict[str, tuple[str | None, str, str]] = {
    "location_id": (None, "Your ID for the location, unique in the file. Case-sensitive; "
                    "spaces around it are ignored.",
                    "Links inventory, history and routes to this location."),
    "product_id": (None, "Your ID for the product, unique in the file. Case-sensitive; spaces "
                   "around it are ignored.", "Links inventory and history to this product."),
    "name": (None, "A readable name.", "Shown in the app and exports; no effect on the plan."),
    "type": (None, "The location's role in this network's mode.",
             "Hubs and distribution centers only send; pantries and stores receive (and may "
             "send surplus, depending on the transfer mode you pick)."),
    "street": (None, "Street address (US only).", "Used to geocode the location."),
    "city": (None, "City.", "Used to geocode the location."),
    "state": (None, "Two-letter US state code, e.g. FL.", "Used to geocode the location; "
              "addresses outside the US are rejected."),
    "zip": (None, "5-digit ZIP code (or ZIP+4).", "Used to geocode the location."),
    "latitude": ("degrees", "Optional. Give with longitude to skip geocoding.",
                 "Sets the location's position for distance estimates."),
    "longitude": ("degrees", "Optional. Give with latitude to skip geocoding.",
                  "Sets the location's position for distance estimates."),
    "receiving_capacity_per_day": (
        "handling units per day", f"Optional. How much the location can receive in a day. "
        f"Blank means {NO_LIMIT}.",
        "Caps transfers into this location per day; blank sets no cap."),
    "poverty_rate": (
        "fraction 0–1", "Optional. Share of residents below the poverty line in the area the "
        "location serves, e.g. 0.125. Overrides the Census tract value.",
        "One of two vulnerability attributes the EGP_PI_INSPIRED method uses to set priority. "
        "Other methods ignore it."),
    "snap_rate": (
        "fraction 0–1", "Optional. Share of households receiving SNAP in the area the location "
        "serves, e.g. 0.18. Overrides the Census tract value.",
        "One of two vulnerability attributes the EGP_PI_INSPIRED method uses to set priority. "
        "Other methods ignore it."),
    "unit": (None, "The unit every quantity of this product is counted in, e.g. case, each, lb.",
             "Quantities of different products are never added together."),
    "unit_value_usd": ("USD per unit", "Optional. Value of one unit.",
                       "Needed for every included product to show Retail results in USD."),
    "handling_units_per_unit": (
        "handling units per unit", "Optional. How much capacity one unit uses. Blank means 1, "
        "shown as an assumption.", "Converts quantities for capacity limits."),
    "batch_id": (None, "Your ID for the batch, unique per location and product.",
                 "Each batch keeps its own expiry date (first-expiring stock is used first)."),
    "quantity": ("product units", "Whole number of units, 0 or more, in the product's unit.",
                 "The stock or amount the plan works with."),
    "expiry_date": ("date (YYYY-MM-DD)", "Last day the batch can be used. Give this or "
                    "non_expiring=true on every row.",
                    "Stock is usable through this day; expiring stock is moved or used first."),
    "non_expiring": (None, "true for items that don't expire; otherwise give expiry_date.",
                     "Non-expiring stock is never counted as expired."),
    "received_date": ("date (YYYY-MM-DD)", "Optional. When the batch arrived.",
                      "Kept for reference; no effect on the plan."),
    "date": ("date (YYYY-MM-DD)", "The day the row describes, on or before the as-of date.",
             "History dated after the as-of date is rejected (no future data)."),
    "basis": (None, f"demand (requests or need) or sales. Rows with sales are labeled "
              f"\"{SALES_LABEL}\" everywhere.",
              "Forecasts are built from this history; sales can understate demand."),
    "from_location_id": (None, "The sending location.", "The route starts here."),
    "to_location_id": (None, "The receiving location (a pantry or store).",
                       "The route ends here. Hubs and distribution centers never receive."),
    "travel_days": ("days", "Optional. Whole days from shipping to arrival, at least 1.",
                    "Overrides the straight-line estimate for this route."),
    "cost_per_handling_unit": ("USD per handling unit", "Optional. Cost to move one handling "
                               "unit on this route.", "Counts against a cost budget, if you "
                               "set one (off by default)."),
    "capacity_per_batch": ("handling units per shipment", f"Optional. Blank means {NO_LIMIT}.",
                           "Caps one shipment on this route."),
    "disabled": (None, "Optional. true removes this route.",
                 "No transfers are planned on a disabled route."),
    "arrival_date": ("date (YYYY-MM-DD)", "Confirmed arrival day, in the seven days after the "
                     "as-of date. Later rows are kept and listed as outside the horizon.",
                     "The arrival enters stock on this day, once (never also as on-hand)."),
    "source": (None, "Optional. dc_delivery, supplier, donation or other.",
               "Shown with the arrival; no effect on the plan."),
    "reference": (None, "Optional. Your reference, e.g. a delivery note number.",
                  "Shown with the arrival; no effect on the plan."),
    "donor": (None, "Optional. Free text, kept separate from the receiving location.",
              "Shown with donation history; no effect on the plan."),
}
OVERRIDES: dict[tuple[TemplateName, str], tuple[str | None, str, str]] = {
    ("demand_history", "quantity"): (
        "product units", f"Units requested (demand) or sold (sales) that day. {BLANK_UNKNOWN}",
        "Forecasts are built from this history."),
    ("donation_history", "quantity"): (
        "product units", f"Units received that day; 0 means nothing was received. "
        f"{BLANK_UNKNOWN} Several rows for one day are added up.",
        "Shown as expected donations (forecast, not confirmed); never counted as supply."),
    ("donation_history", "location_id"): (
        None, "The receiving location.", "Links the donation to this location."),
    ("inbound", "quantity"): ("product units", "Whole number of units arriving, at least 1.",
                              "Added to the receiving location's stock on the arrival date."),
}
NOTES = (
    "Each network uses one timezone for every location, chosen at import; per-location "
    "timezones aren't supported in v1.",
    f"A blank capacity means {NO_LIMIT}.",
    "The as-of date is the date the inventory describes. It defaults to the day after the last "
    "history date; planning starts the day after it.",
    "Files must be UTF-8 CSV (\"CSV UTF-8\" in Excel). Nothing is saved unless every file "
    "passes; up to 1,000 errors are listed with file, line, column and what to change.",
    "If no inbound.csv is given, results show \"no scheduled deliveries provided\".",
)


def template_catalog(mode: NetworkMode | None) -> TemplateCatalog:
    roles = ROLES_BY_MODE[mode] if mode else ROLES_BY_MODE["PANTRY"] + ROLES_BY_MODE["RETAIL"]
    templates = []
    for name, columns in COLUMNS.items():
        entries = []
        for column, required in columns:
            unit, meaning, effect = OVERRIDES.get((name, column), GUIDE[column])
            entries.append(TemplateColumn(
                name=column, required=required, unit=unit, meaning=meaning,
                effect_on_plan=effect, allowed_values=roles if column == "type" else ()))
        templates.append(Template(name=name, required=name in REQUIRED_TEMPLATES,
                                  description=DESCRIPTIONS[name], columns=tuple(entries),
                                  # shortcut: the examples are the Pantry sample, so only Pantry
                                  # offers them until the samples lane adds Retail ones
                                  # (CR-w3-samples-3).
                                  example_available=mode == "PANTRY"))
    return TemplateCatalog(mode=mode, templates=tuple(templates), notes=NOTES)


def template_csv(name: TemplateName, kind: Literal["blank", "example"],
                 mode: NetworkMode | None = None) -> str:
    if kind == "example":
        if mode == "RETAIL":
            # shortcut: no Retail examples yet; the samples lane adds them (CR-w3-samples-3).
            raise AccessError("TEMPLATE_EXAMPLE_UNAVAILABLE", 404)
        return _examples()[name]
    return header(name) + "\n"


@cache
def _examples() -> dict[TemplateName, str]:
    """The Pantry sample on a fixed date, so the download matches the committed files in
    data/templates/examples (written by scripts/generate_samples.py) and the sample itself."""
    return pantry_sample(EXAMPLE_AS_OF).files
