# covers: V1-A07, V1-A08, V1-A10, V1-A11, V1-A23
"""W0-07: ppv1_0008 network schema on an isolated PostgreSQL schema (never skipped in CI)."""

import uuid
from datetime import date

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.exc import DBAPIError
from wq_support import alembic_config, database_url, reset_schema

from app.repositories.jobs import create_queue_engine

pytestmark = pytest.mark.integration

SCHEMA = "v1_schema_test"
V1_TABLES = {
    "networks", "dataset_versions", "import_runs", "import_events", "import_errors",
    "import_staging", "net_locations", "net_products", "net_batches", "net_demand_history",
    "net_donation_history", "net_inbound", "net_routes", "google_distance_cache",
    "local_secrets", "local_logins", "backtest_scores",
}


@pytest.fixture(scope="module")
def engine():
    url = database_url()
    reset_schema(url, SCHEMA)
    eng = create_queue_engine(url, schema=SCHEMA)
    with eng.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    yield eng
    eng.dispose()
    reset_schema(url, SCHEMA)


def _tables(conn):
    return set(sa.inspect(conn).get_table_names(schema=SCHEMA))


def _network(conn, mode="pantry"):
    """Create organization → network → dataset version → one location and one product."""
    ids = {k: uuid.uuid4() for k in ("org", "net", "ver", "run", "loc", "prod")}
    q = lambda sql, **kw: conn.execute(sa.text(sql), {**{k: v for k, v in ids.items()}, **kw})  # noqa: E731
    q("INSERT INTO organizations (id, name, is_demo) VALUES (:org, 'n', false)")
    q("INSERT INTO networks (id, organization_id, name, mode, timezone) "
      "VALUES (:net, :org, 'n', :mode, 'America/New_York')", mode=mode)
    q("INSERT INTO import_runs (id, organization_id, network_id, phase) "
      "VALUES (:run, :org, :net, 'committing')")
    q("INSERT INTO dataset_versions (id, organization_id, network_id, import_run_id, as_of_date, "
      "input_sha256) VALUES (:ver, :org, :net, :run, '2026-11-03', repeat('a', 64))")
    q("INSERT INTO net_locations (id, organization_id, dataset_version_id, external_id, name, "
      "role, street, city, state, zip) VALUES (:loc, :org, :ver, 'L1', 'Loc', 'pantry', '1 Main', "
      "'Gainesville', 'FL', '32601')")
    q("INSERT INTO net_products (id, organization_id, dataset_version_id, external_id, name, unit) "
      "VALUES (:prod, :org, :ver, 'P1', 'Rice', 'case')")
    for table in ("net_demand_history", "net_donation_history"):
        part = f"{table}_{ids['ver'].hex}"
        conn.execute(sa.text(f"CREATE TABLE {part} PARTITION OF {table} "
                             f"FOR VALUES IN ('{ids['ver']}')"))
    return ids


def _fails(engine, sql, **params):
    with pytest.raises(DBAPIError):
        with engine.begin() as conn:
            ids = _network(conn)
            conn.execute(sa.text(sql), {**ids, **params})


def test_upgrade_head_on_fresh_database(engine):
    with engine.connect() as conn:
        assert V1_TABLES <= _tables(conn)
        assert conn.scalar(sa.text("SELECT version_num FROM alembic_version")) == "ppv1_0009"


def test_downgrade_to_ppvp_0007_and_up_again():
    url = database_url()
    schema = "v1_schema_downgrade_test"
    reset_schema(url, schema)
    eng = create_queue_engine(url, schema=schema)
    try:
        with eng.begin() as conn:
            command.upgrade(alembic_config(conn), "head")
        with eng.begin() as conn:
            command.downgrade(alembic_config(conn), "ppvp_0007")
        with eng.connect() as conn:
            assert not (V1_TABLES & _tables_in(conn, schema))
            assert "planning_plans" in _tables_in(conn, schema)
        with eng.begin() as conn:
            command.upgrade(alembic_config(conn), "head")
        with eng.connect() as conn:
            assert V1_TABLES <= _tables_in(conn, schema)
    finally:
        eng.dispose()
        reset_schema(url, schema)


def _tables_in(conn, schema):
    return set(sa.inspect(conn).get_table_names(schema=schema))


BATCH = ("INSERT INTO net_batches (id, organization_id, dataset_version_id, location_id, "
         "product_id, external_id, quantity, expiry_date, non_expiring) "
         "VALUES (gen_random_uuid(), :org, :ver, :loc, :prod, 'B1', "
         "CAST(:qty AS text)::bigint, CAST(:exp AS date), :ne)")


def test_batch_quantity_nonnegative_integer(engine):
    _fails(engine, BATCH, qty="-1", exp="2026-11-10", ne=False)
    _fails(engine, BATCH, qty="1.5", exp="2026-11-10", ne=False)
    with engine.begin() as conn:
        ids = _network(conn)
        conn.execute(sa.text(BATCH), {**ids, "qty": "0", "exp": "2026-11-10", "ne": False})


def test_expiry_xor_non_expiring(engine):
    _fails(engine, BATCH, qty="5", exp="2026-11-10", ne=True)
    _fails(engine, BATCH, qty="5", exp=None, ne=False)
    with engine.begin() as conn:
        ids = _network(conn)
        conn.execute(sa.text(BATCH), {**ids, "qty": "5", "exp": None, "ne": True})


DEMAND = ("INSERT INTO net_demand_history (organization_id, dataset_version_id, location_id, "
          "product_id, day, quantity, basis) VALUES (:org, :ver, :loc, :prod, :day, :qty, :basis)")


def test_demand_quantity_nullable_and_basis_checked(engine):
    _fails(engine, DEMAND, day=date(2026, 11, 1), qty=3, basis="forecast")
    _fails(engine, DEMAND, day=date(2026, 11, 1), qty=-1, basis="demand")
    with engine.begin() as conn:
        ids = _network(conn)
        params = {**ids, "day": date(2026, 11, 1), "qty": None, "basis": "sales"}
        conn.execute(sa.text(DEMAND), params)
        row = conn.execute(sa.text("SELECT quantity, basis FROM net_demand_history "
                                   "WHERE dataset_version_id = :ver"), ids).one()
        assert row == (None, "sales")


def test_donation_zero_distinct_from_null(engine):
    with engine.begin() as conn:
        ids = _network(conn)
        for day, qty in ((date(2026, 11, 1), 0), (date(2026, 11, 2), None)):
            conn.execute(sa.text(
                "INSERT INTO net_donation_history (organization_id, dataset_version_id, "
                "location_id, product_id, day, quantity) "
                "VALUES (:org, :ver, :loc, :prod, :day, :qty)"
            ), {**ids, "day": day, "qty": qty})
        rows = conn.execute(sa.text("SELECT day, quantity FROM net_donation_history "
                                    "WHERE dataset_version_id = :ver ORDER BY day"), ids).all()
        assert [r.quantity for r in rows] == [0, None]


def test_network_mode_immutable(engine):
    _fails(engine, "UPDATE networks SET mode = 'retail' WHERE id = :net")
    with engine.begin() as conn:
        ids = _network(conn)
        conn.execute(sa.text("UPDATE networks SET name = 'renamed' WHERE id = :net"), ids)


def test_dataset_version_immutable(engine):
    _fails(engine, "UPDATE dataset_versions SET as_of_date = '2026-11-04' WHERE id = :ver")
    _fails(engine, "DELETE FROM dataset_versions WHERE id = :ver")


def _kinds(conn, schema):
    return conn.scalar(sa.text(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
        "JOIN pg_namespace n ON n.oid = c.connamespace "
        "WHERE n.nspname = :schema AND c.conname = 'compute_jobs_operation_kind_check'"
    ), {"schema": schema})


def test_ppv1_0009_adds_import_and_enrichment_job_kinds():
    url = database_url()
    schema = "v1_job_kinds_test"
    reset_schema(url, schema)
    eng = create_queue_engine(url, schema=schema)
    try:
        with eng.begin() as conn:
            command.upgrade(alembic_config(conn), "head")
        with eng.connect() as conn:
            definition = _kinds(conn, schema)
            assert all(f"'{k}'" in definition for k in ("FORECAST", "IMPORT", "ENRICHMENT"))
        with eng.begin() as conn:
            command.downgrade(alembic_config(conn), "ppv1_0008")
        with eng.connect() as conn:
            assert "IMPORT" not in _kinds(conn, schema)
    finally:
        eng.dispose()
        reset_schema(url, schema)
