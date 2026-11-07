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
    "planning_scenarios_v3", "planning_comparisons_v3",
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


def _network(conn, mode="PANTRY"):
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
        assert conn.scalar(sa.text("SELECT version_num FROM alembic_version")) == "ppv1_0012"


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


def test_downgrade_refuses_to_drop_imported_networks():
    url = database_url()
    schema = "v1_schema_downgrade_refusal_test"
    reset_schema(url, schema)
    eng = create_queue_engine(url, schema=schema)
    try:
        with eng.begin() as conn:
            command.upgrade(alembic_config(conn), "head")
            _network(conn)
        with pytest.raises(Exception, match="V1_DATA_PRESENT"), eng.begin() as conn:
            command.downgrade(alembic_config(conn), "ppvp_0007")
        with eng.connect() as conn:
            assert "networks" in _tables_in(conn, schema)
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
    _fails(engine, "UPDATE networks SET mode = 'RETAIL' WHERE id = :net")
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


NEW_RUN = ("INSERT INTO import_runs (id, organization_id, network_id, new_network, phase) "
           "VALUES (:run2, :org2, :network_id, CAST(:new_network AS jsonb), :phase)")


def _org(conn):
    org = uuid.uuid4()
    conn.execute(sa.text("INSERT INTO organizations (id, name, is_demo) VALUES (:o, 'n', false)"),
                 {"o": org})
    return org


def test_new_network_import_run_exists_without_a_network(engine):
    # Atomic import (Gabriel, 2026-11-06): the network row is created only by a successful commit.
    with engine.begin() as conn:
        org = _org(conn)
        conn.execute(sa.text(NEW_RUN), {"run2": uuid.uuid4(), "org2": org, "network_id": None,
                                        "new_network": '{"name": "N", "mode": "PANTRY"}',
                                        "phase": "failed"})
        assert conn.scalar(sa.text("SELECT count(*) FROM networks WHERE organization_id = :o"),
                           {"o": org}) == 0


@pytest.mark.parametrize(("network", "new_network", "phase", "check"), [
    (False, None, "uploading", "network_or_new"),  # neither an existing nor a pending network
    (False, '{"name": "N"}', "done", "done_has_network"),  # a finished import has its network
])
def test_import_run_network_rules(engine, network, new_network, phase, check):
    with pytest.raises(DBAPIError, match=f"ck_import_runs_{check}"), engine.begin() as conn:
        ids = _network(conn) if network else {"org": _org(conn)}
        conn.execute(sa.text(NEW_RUN), {"run2": uuid.uuid4(), "org2": ids["org"],
                                        "network_id": None, "new_network": new_network,
                                        "phase": phase})



ERROR_ROW = ("INSERT INTO import_errors (id, organization_id, import_run_id, file, line_no, code, "
             "reason, fix) VALUES (:e, :org, :run, 'inventory', 2, 'NEGATIVE', 'below 0', :fix)")


def test_import_errors_store_the_fix(engine):
    # GET /imports/{id} rebuilds RowError, whose fix is required, from these rows.
    with engine.begin() as conn:
        ids = _network(conn)
        conn.execute(sa.text(ERROR_ROW), {**ids, "e": uuid.uuid4(), "fix": "Enter 0 or more."})
    for fix in (None, "  "):
        with pytest.raises(DBAPIError), engine.begin() as conn:
            ids = _network(conn)
            conn.execute(sa.text(ERROR_ROW), {**ids, "e": uuid.uuid4(), "fix": fix})


def test_network_mode_uses_the_api_spelling(engine):
    # The frozen API's NetworkMode is stored as is; a lowercase mode is rejected (ppv1_0010).
    from typing import get_args

    from app.models.networks import MODES
    from app.schemas.v1_planning import NetworkMode

    assert set(MODES) == set(get_args(NetworkMode))
    with pytest.raises(DBAPIError, match="ck_networks_mode"):
        with engine.begin() as conn:
            _network(conn, mode="pantry")


# CR-w1-solver-3 (Gabriel, 2026-11-07): v1 scenarios and comparison results get their own tables.
def _scenario_v3(conn, ids, **overrides):
    row = {"id": uuid.uuid4(), "org": ids["org"], "net": ids["net"], "ver": ids["ver"],
           "run": uuid.uuid4(), "hash": "b" * 64, **overrides}
    conn.execute(sa.text(
        "INSERT INTO planning_scenarios_v3 (id, organization_id, network_id, dataset_version_id, "
        "forecast_run_id, content_hash, payload) VALUES (:id, :org, :net, :ver, :run, :hash, "
        "'{}'::jsonb)"), row)
    return row["id"]


def test_v3_scenarios_are_immutable(engine):
    with engine.begin() as conn:
        ids = _network(conn)
        scenario = _scenario_v3(conn, ids)
    for sql in ("UPDATE planning_scenarios_v3 SET payload = '[]'::jsonb WHERE id = :s",
                "DELETE FROM planning_scenarios_v3 WHERE id = :s"):
        with pytest.raises(DBAPIError, match="immutable"), engine.begin() as conn:
            conn.execute(sa.text(sql), {"s": scenario})


@pytest.mark.parametrize(("overrides", "violation"), [
    ({"hash": "B" * 64}, "check constraint"), ({"hash": "b" * 63}, "check constraint"),
    ({"ver": uuid.uuid4()}, "foreign key constraint"),
    ({"net": uuid.uuid4()}, "foreign key constraint"),
])
def test_v3_scenario_rows_are_checked(engine, overrides, violation):
    with pytest.raises(DBAPIError, match=violation), engine.begin() as conn:
        _scenario_v3(conn, _network(conn), **overrides)


def test_v3_comparisons_link_scenario_job_and_attempt(engine):
    with engine.connect() as conn:
        inspector = sa.inspect(conn)
        targets = {fk["referred_table"] for fk in
                   inspector.get_foreign_keys("planning_comparisons_v3", schema=SCHEMA)}
        unique = {tuple(u["column_names"]) for u in
                  inspector.get_unique_constraints("planning_comparisons_v3", schema=SCHEMA)}
        checks = " ".join(c["sqltext"] for c in
                          inspector.get_check_constraints("planning_comparisons_v3", schema=SCHEMA))
        triggers = conn.execute(sa.text(
            "SELECT count(*) FROM information_schema.triggers WHERE event_object_schema = :s "
            "AND event_object_table = 'planning_comparisons_v3' AND trigger_name = "
            "'ppv1_immutable'"), {"s": SCHEMA}).scalar()
    assert {"planning_scenarios_v3", "compute_jobs", "compute_attempts", "networks"} <= targets
    assert {("job_id",), ("attempt_id",)} <= unique
    assert "UNITS" in checks and "USD" in checks
    assert triggers == 2  # UPDATE and DELETE


def test_downgrade_refuses_to_drop_saved_scenarios():
    url = database_url()
    schema = "v1_schema_v3_refusal_test"
    reset_schema(url, schema)
    eng = create_queue_engine(url, schema=schema)
    try:
        with eng.begin() as conn:
            command.upgrade(alembic_config(conn), "head")
            _scenario_v3(conn, _network(conn))
        with pytest.raises(Exception, match="V1_DATA_PRESENT"), eng.begin() as conn:
            command.downgrade(alembic_config(conn), "ppv1_0010")
        with eng.connect() as conn:
            assert "planning_scenarios_v3" in _tables_in(conn, schema)
    finally:
        eng.dispose()
        reset_schema(url, schema)


def test_handling_units_given_defaults_true_and_is_required(engine):
    """CR-w1-data-6: the flag says whether the file gave handling units (blank → 1, listed)."""
    with engine.begin() as conn:
        ids = _network(conn)
        assert conn.scalar(sa.text("SELECT handling_units_given FROM net_products "
                                   "WHERE id = :prod"), ids) is True
    _fails(engine, "INSERT INTO net_products (id, organization_id, dataset_version_id, "
                   "external_id, name, unit, handling_units_given) VALUES "
                   "(gen_random_uuid(), :org, :ver, 'P-NULL', 'x', 'case', NULL)")


def test_downgrade_refuses_to_lose_a_defaulted_handling_unit():
    url = database_url()
    schema = "v1_schema_handling_refusal_test"
    reset_schema(url, schema)
    eng = create_queue_engine(url, schema=schema)
    try:
        with eng.begin() as conn:
            command.upgrade(alembic_config(conn), "head")
            ids = _network(conn)
            conn.execute(sa.text("INSERT INTO net_products (id, organization_id, "
                                 "dataset_version_id, external_id, name, unit, "
                                 "handling_units_given) VALUES (gen_random_uuid(), :org, :ver, "
                                 "'P-BLANK', 'x', 'case', false)"), ids)
        with pytest.raises(Exception, match="V1_DATA_PRESENT"), eng.begin() as conn:
            command.downgrade(alembic_config(conn), "ppv1_0011")
    finally:
        eng.dispose()
        reset_schema(url, schema)
