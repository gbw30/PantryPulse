"""Template columns: the single list the validator, blank templates and guide share (W1-D02)."""

from app.schemas.v1_networks import TemplateName

# (column, required in the header). Order is the blank template's header order.
COLUMNS: dict[TemplateName, tuple[tuple[str, bool], ...]] = {
    "locations": (
        ("location_id", True), ("name", True), ("type", True), ("street", True),
        ("city", True), ("state", True), ("zip", True), ("latitude", False),
        ("longitude", False), ("receiving_capacity_per_day", False),
        ("poverty_rate", False), ("snap_rate", False),
    ),
    "products": (
        ("product_id", True), ("name", True), ("unit", True), ("unit_value_usd", False),
        ("handling_units_per_unit", False),
    ),
    # expiry_date / non_expiring: each row needs exactly one, so neither column is required alone.
    "inventory": (
        ("location_id", True), ("product_id", True), ("batch_id", True), ("quantity", True),
        ("expiry_date", False), ("non_expiring", False), ("received_date", False),
    ),
    "demand_history": (
        ("location_id", True), ("product_id", True), ("date", True), ("quantity", True),
        ("basis", True),
    ),
    "routes": (
        ("from_location_id", True), ("to_location_id", True), ("travel_days", False),
        ("cost_per_handling_unit", False), ("capacity_per_batch", False), ("disabled", False),
    ),
    "inbound": (
        ("location_id", True), ("product_id", True), ("quantity", True), ("arrival_date", True),
        ("expiry_date", False), ("non_expiring", False), ("source", False), ("reference", False),
    ),
    "donation_history": (
        ("location_id", True), ("product_id", True), ("date", True), ("quantity", True),
        ("donor", False),
    ),
}


def header(name: TemplateName) -> str:
    return ",".join(column for column, _ in COLUMNS[name])
