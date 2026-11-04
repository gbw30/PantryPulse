"""v1 bring-your-own networks (W0-07, migration ppv1_0008). Importing never connects.

One organization per network (docs/plans/v1/decisions/W0-network-model.md), so every tenant table
below carries ``organization_id`` with composite tenant foreign keys, like operational-v1.
History tables are LIST-partitioned by dataset version: the import job loads each version into its
own partition and attaches it after load (S4: 4.5 M rows in ~5 s, all-or-nothing).
``install_metadata`` holds install-wide tables; no read model selects ``local_secrets``.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.operational import Base, OwnedIdentity, check, fk, instant, owned, uid

MODES = ("pantry", "retail")
ROLES = ("hub", "pantry", "distribution_center", "store")
FILES = ("locations", "products", "inventory", "demand_history", "routes", "inbound",
         "donation_history")
IMPORT_PHASES = ("uploading", "staging", "validating", "committing", "done", "failed")
ERROR_CODES = ("MALFORMED", "DUPLICATE", "NEGATIVE", "FRACTIONAL", "UNKNOWN_ID", "MISSING_EXPIRY",
               "AFTER_AS_OF_DATE", "OVER_ENVELOPE")
BASES = ("demand", "sales")
ROUTE_METHODS = ("straight_line", "google", "user")
INBOUND_SOURCES = ("dc_delivery", "supplier", "donation", "other")
SERIES_KINDS = ("demand", "donation")
STAGING_COLUMNS = 12  # widest template (locations.csv) has 12 columns


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _expiry_xor(prefix=""):
    return (f"({prefix}expiry_date IS NOT NULL AND NOT {prefix}non_expiring) OR "
            f"({prefix}expiry_date IS NULL AND {prefix}non_expiring)")


class Network(OwnedIdentity, Base):
    __tablename__ = "networks"
    name = sa.Column(sa.Text, nullable=False)
    mode = sa.Column(sa.Text, nullable=False)  # immutable (trigger)
    timezone = sa.Column(sa.Text, nullable=False)
    is_sample = sa.Column(sa.Boolean, nullable=False, server_default=sa.false())
    __table_args__ = owned(
        sa.UniqueConstraint("organization_id"), check(_in("mode", MODES), "mode"),
    )


class ImportRun(OwnedIdentity, Base):
    """One import attempt; the durable import.v1 job reports its phase and progress here."""

    __tablename__ = "import_runs"
    network_id = uid(nullable=False)
    job_id = uid()
    phase = sa.Column(sa.Text, nullable=False)
    files = sa.Column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    progress = sa.Column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    error_count = sa.Column(sa.Integer, nullable=False, server_default="0")
    errors_truncated = sa.Column(sa.Boolean, nullable=False, server_default=sa.false())
    updated_at = instant(nullable=False, server_default=sa.func.clock_timestamp())
    __table_args__ = owned(
        fk(["network_id"], "networks", ["id"]),
        check(_in("phase", IMPORT_PHASES), "phase"),
        check("error_count >= 0", "error_count"),
    )


class DatasetVersion(OwnedIdentity, Base):
    """Immutable (trigger): scenarios keep the version they used after a re-import."""

    __tablename__ = "dataset_versions"
    network_id = uid(nullable=False)
    import_run_id = uid(nullable=False)
    as_of_date = sa.Column(sa.Date, nullable=False)
    input_sha256 = sa.Column(sa.String(64), nullable=False)
    __table_args__ = owned(
        fk(["network_id"], "networks", ["id"]),
        fk(["import_run_id"], "import_runs", ["id"]),
        sa.UniqueConstraint("import_run_id"),
        check("input_sha256 ~ '^[0-9a-f]{64}$'", "hash"),
    )


class ImportEvent(OwnedIdentity, Base):
    """The one audited event recording a dataset version's opening snapshot (immutable)."""

    __tablename__ = "import_events"
    dataset_version_id = uid(nullable=False)
    import_run_id = uid(nullable=False)
    actor = sa.Column(sa.String(200), nullable=False)
    files = sa.Column(JSONB, nullable=False)
    __table_args__ = owned(
        fk(["dataset_version_id"], "dataset_versions", ["id"]),
        fk(["import_run_id"], "import_runs", ["id"]),
        sa.UniqueConstraint("dataset_version_id"),
    )


class ImportErrorRow(OwnedIdentity, Base):
    """File/line/column/reason for a rejected import; the job stores at most the first 1,000."""

    __tablename__ = "import_errors"
    import_run_id = uid(nullable=False)
    file = sa.Column(sa.Text, nullable=False)
    line_no = sa.Column(sa.BigInteger, nullable=False)  # 1 = header; row-level errors name a line
    column_name = sa.Column(sa.Text)  # NULL for row-level errors
    code = sa.Column(sa.Text, nullable=False)
    reason = sa.Column(sa.Text, nullable=False)
    value = sa.Column(sa.Text)
    __table_args__ = owned(
        fk(["import_run_id"], "import_runs", ["id"]),
        check(_in("file", FILES), "file"),
        check(_in("code", ERROR_CODES), "code"),
        check("line_no >= 1", "line_no"),
        sa.Index("ix_import_errors_run_file_line", "import_run_id", "file", "line_no"),
    )


class Location(OwnedIdentity, Base):
    __tablename__ = "net_locations"
    dataset_version_id = uid(nullable=False)
    external_id = sa.Column(sa.Text, nullable=False)
    name = sa.Column(sa.Text, nullable=False)
    role = sa.Column(sa.Text, nullable=False)
    street = sa.Column(sa.Text, nullable=False)
    city = sa.Column(sa.Text, nullable=False)
    state = sa.Column(sa.Text, nullable=False)
    zip = sa.Column(sa.Text, nullable=False)
    latitude = sa.Column(sa.Numeric(9, 6))
    longitude = sa.Column(sa.Numeric(9, 6))
    coordinates_source = sa.Column(sa.Text)  # 'user' (template) or 'census_geocoder'
    receiving_capacity_per_day = sa.Column(sa.Numeric(14, 3))  # handling units; NULL = no limit
    tract_geoid = sa.Column(sa.Text)
    poverty_rate = sa.Column(sa.Numeric(6, 5))
    snap_rate = sa.Column(sa.Numeric(6, 5))
    acs_source = sa.Column(sa.Text)  # ACS table ids, e.g. 'ACS5 S1701,S2201'
    acs_year = sa.Column(sa.Integer)
    acs_fetched_at = instant()
    manual_poverty_rate = sa.Column(sa.Numeric(6, 5))  # template override of the lookup
    manual_snap_rate = sa.Column(sa.Numeric(6, 5))
    excluded = sa.Column(sa.Boolean, nullable=False, server_default=sa.false())
    exclusion_reason = sa.Column(sa.Text)
    __table_args__ = owned(
        fk(["dataset_version_id"], "dataset_versions", ["id"]),
        sa.UniqueConstraint("organization_id", "dataset_version_id", "id"),
        sa.UniqueConstraint("dataset_version_id", "external_id"),
        check(_in("role", ROLES), "role"),
        check("coordinates_source IS NULL OR coordinates_source IN ('user', 'census_geocoder')",
              "coordinates_source"),
        check("(latitude IS NULL) = (longitude IS NULL)", "coordinates_pair"),
        check("receiving_capacity_per_day IS NULL OR receiving_capacity_per_day >= 0", "capacity"),
        *(check(f"{c} IS NULL OR {c} BETWEEN 0 AND 1", c)
          for c in ("poverty_rate", "snap_rate", "manual_poverty_rate", "manual_snap_rate")),
        check("(poverty_rate IS NULL AND snap_rate IS NULL) OR (acs_source IS NOT NULL AND "
              "acs_year IS NOT NULL AND acs_fetched_at IS NOT NULL)", "acs_provenance"),
        check("NOT excluded OR exclusion_reason IS NOT NULL", "exclusion_reason"),
    )


class Product(OwnedIdentity, Base):
    __tablename__ = "net_products"
    dataset_version_id = uid(nullable=False)
    external_id = sa.Column(sa.Text, nullable=False)
    name = sa.Column(sa.Text, nullable=False)
    unit = sa.Column(sa.Text, nullable=False)
    unit_value_usd = sa.Column(sa.Numeric(14, 4))  # NULL: Retail $ results unavailable
    handling_units_per_unit = sa.Column(sa.Numeric(14, 6), nullable=False, server_default="1")
    __table_args__ = owned(
        fk(["dataset_version_id"], "dataset_versions", ["id"]),
        sa.UniqueConstraint("organization_id", "dataset_version_id", "id"),
        sa.UniqueConstraint("dataset_version_id", "external_id"),
        check("unit_value_usd IS NULL OR unit_value_usd >= 0", "unit_value"),
        check("handling_units_per_unit > 0", "handling_units"),
    )


def _version_fks():
    return (
        fk(["dataset_version_id", "location_id"], "net_locations", ["dataset_version_id", "id"]),
        fk(["dataset_version_id", "product_id"], "net_products", ["dataset_version_id", "id"]),
    )


class Batch(OwnedIdentity, Base):
    """Opening snapshot lot (inventory.csv). Usable through expiry_date (V5 BD-43)."""

    __tablename__ = "net_batches"
    dataset_version_id = uid(nullable=False)
    location_id = uid(nullable=False)
    product_id = uid(nullable=False)
    external_id = sa.Column(sa.Text, nullable=False)
    quantity = sa.Column(sa.BigInteger, nullable=False)
    expiry_date = sa.Column(sa.Date)
    non_expiring = sa.Column(sa.Boolean, nullable=False)
    received_date = sa.Column(sa.Date)
    __table_args__ = owned(
        fk(["dataset_version_id"], "dataset_versions", ["id"]),
        *_version_fks(),
        sa.UniqueConstraint("dataset_version_id", "location_id", "product_id", "external_id"),
        check("quantity >= 0", "quantity"),
        check(_expiry_xor(), "expiry_xor_non_expiring"),
    )


def _history(name, *extra_columns, extra_checks=()):
    """Partitioned by dataset_version_id; the PK leads with the partition key (PG requirement)."""
    return sa.Table(
        name, Base.metadata,
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("quantity", sa.BigInteger),  # NULL = unknown day, never zero
        *extra_columns,
        sa.PrimaryKeyConstraint("dataset_version_id", "location_id", "product_id", "day"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        *_version_fks(),
        check("quantity IS NULL OR quantity >= 0", "quantity"),
        *extra_checks,
        postgresql_partition_by="LIST (dataset_version_id)",
    )


demand_history = _history(
    "net_demand_history",
    sa.Column("basis", sa.Text, nullable=False),
    extra_checks=(check(_in("basis", BASES), "basis"),),
)
donation_history = _history("net_donation_history", sa.Column("donor", sa.Text))


class Inbound(OwnedIdentity, Base):
    """Confirmed arrivals (inbound.csv); rows outside the 7-day horizon are kept and listed."""

    __tablename__ = "net_inbound"
    dataset_version_id = uid(nullable=False)
    location_id = uid(nullable=False)
    product_id = uid(nullable=False)
    line_no = sa.Column(sa.BigInteger, nullable=False)
    quantity = sa.Column(sa.BigInteger, nullable=False)
    arrival_date = sa.Column(sa.Date, nullable=False)
    expiry_date = sa.Column(sa.Date)
    non_expiring = sa.Column(sa.Boolean, nullable=False)
    source = sa.Column(sa.Text)
    reference = sa.Column(sa.Text)
    within_horizon = sa.Column(sa.Boolean, nullable=False)
    __table_args__ = owned(
        fk(["dataset_version_id"], "dataset_versions", ["id"]),
        *_version_fks(),
        sa.UniqueConstraint("dataset_version_id", "line_no"),
        check("quantity > 0", "quantity"),
        check(_expiry_xor(), "expiry_xor_non_expiring"),
        check(f"source IS NULL OR {_in('source', INBOUND_SOURCES)}", "source"),
    )


class Route(OwnedIdentity, Base):
    """Directed route; `routes.csv` rows (is_override) win over straight-line or Google values."""

    __tablename__ = "net_routes"
    dataset_version_id = uid(nullable=False)
    from_location_id = uid(nullable=False)
    to_location_id = uid(nullable=False)
    method = sa.Column(sa.Text, nullable=False)
    distance_miles = sa.Column(sa.Numeric(10, 3))
    road_hours = sa.Column(sa.Numeric(10, 3))
    travel_days = sa.Column(sa.Integer, nullable=False)
    cost_per_handling_unit = sa.Column(sa.Numeric(14, 4))
    capacity_per_batch = sa.Column(sa.Numeric(14, 3))  # NULL = no limit
    is_override = sa.Column(sa.Boolean, nullable=False, server_default=sa.false())
    disabled = sa.Column(sa.Boolean, nullable=False, server_default=sa.false())
    fetched_at = instant()
    __table_args__ = owned(
        fk(["dataset_version_id"], "dataset_versions", ["id"]),
        *(fk(["dataset_version_id", end], "net_locations", ["dataset_version_id", "id"])
          for end in ("from_location_id", "to_location_id")),
        sa.UniqueConstraint("dataset_version_id", "from_location_id", "to_location_id"),
        check("from_location_id <> to_location_id", "distinct_ends"),
        check(_in("method", ROUTE_METHODS), "method"),
        check("travel_days >= 1", "travel_days"),
        check("method <> 'google' OR fetched_at IS NOT NULL", "google_fetched_at"),
        check("distance_miles IS NULL OR distance_miles >= 0", "distance"),
        check("road_hours IS NULL OR road_hours >= 0", "road_hours"),
        check("cost_per_handling_unit IS NULL OR cost_per_handling_unit >= 0", "cost"),
        check("capacity_per_batch IS NULL OR capacity_per_batch >= 0", "capacity"),
    )


class BacktestScore(OwnedIdentity, Base):
    """WAPE/bias on the user's own history; NULL scores with evaluated=false under 35 days."""

    __tablename__ = "backtest_scores"
    dataset_version_id = uid(nullable=False)
    location_id = uid(nullable=False)
    product_id = uid(nullable=False)
    series_kind = sa.Column(sa.Text, nullable=False)
    method = sa.Column(sa.Text, nullable=False)
    evaluated = sa.Column(sa.Boolean, nullable=False)
    scored_points = sa.Column(sa.Integer, nullable=False)
    wape = sa.Column(sa.Numeric(12, 6))
    bias = sa.Column(sa.Numeric(12, 6))
    __table_args__ = owned(
        fk(["dataset_version_id"], "dataset_versions", ["id"]),
        *_version_fks(),
        sa.UniqueConstraint("dataset_version_id", "location_id", "product_id", "series_kind",
                            "method"),
        check(_in("series_kind", SERIES_KINDS), "series_kind"),
        check("scored_points >= 0", "scored_points"),
        check("evaluated OR (wape IS NULL AND bias IS NULL)", "not_evaluated_has_no_score"),
    )


# Install-wide tables: no tenant. Kept out of Base.metadata so the tenant boundary test holds.
install_metadata = sa.MetaData(naming_convention=Base.metadata.naming_convention)

import_staging = sa.Table(
    # Raw CSV text; the job creates one UNLOGGED partition per import run and drops it after
    # commit or abort. No foreign keys, so COPY stays fast (S4); ownership is via import_runs.
    "import_staging", install_metadata,
    sa.Column("import_run_id", UUID(as_uuid=True), nullable=False),
    sa.Column("file", sa.Text, nullable=False),
    sa.Column("line_no", sa.BigInteger, nullable=False),
    sa.Column("ncols", sa.Integer, nullable=False),
    *(sa.Column(f"c{i:02d}", sa.Text) for i in range(1, STAGING_COLUMNS + 1)),
    postgresql_partition_by="LIST (import_run_id)",
)

google_distance_cache = sa.Table(
    "google_distance_cache", install_metadata,
    sa.Column("origin_lat", sa.Numeric(9, 6), nullable=False),
    sa.Column("origin_lon", sa.Numeric(9, 6), nullable=False),
    sa.Column("dest_lat", sa.Numeric(9, 6), nullable=False),
    sa.Column("dest_lon", sa.Numeric(9, 6), nullable=False),
    sa.Column("distance_meters", sa.Integer, nullable=False),
    sa.Column("duration_seconds", sa.Integer, nullable=False),
    sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("origin_lat", "origin_lon", "dest_lat", "dest_lon"),
    sa.CheckConstraint("distance_meters >= 0 AND duration_seconds >= 0", name="nonnegative"),
)

local_secrets = sa.Table(
    # e.g. the bring-your-own Google key. Never selected by a read model or returned by the API.
    "local_secrets", install_metadata,
    sa.Column("name", sa.Text, primary_key=True),
    sa.Column("value", sa.Text, nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
              server_default=sa.func.clock_timestamp()),
    sa.CheckConstraint("name IN ('google_maps_api_key')", name="name"),
)

local_logins = sa.Table(
    # The generated local login: scrypt hash only (W0-05); the password lives in .pantrypulse/.
    "local_logins", install_metadata,
    sa.Column("username", sa.Text, primary_key=True),
    sa.Column("password_hash", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
              server_default=sa.func.clock_timestamp()),
    sa.CheckConstraint("password_hash LIKE 'scrypt$%'", name="scrypt"),
)
