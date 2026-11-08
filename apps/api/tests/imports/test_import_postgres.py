# covers: V1-A07, V1-A08, V1-A23
"""Staging and the all-or-nothing commit on real PostgreSQL (W1-D04). Never skipped in CI."""

import asyncio
import hashlib
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command

from app.repositories import imports as repo
from app.repositories.jobs import create_queue_engine
from app.schemas.v1_imports import NewNetwork
from app.services.imports import api
from app.services.imports.staging import (
    drop_staged,
    job_input,
    load_staged,
    publish_staged,
    run_import,
    stage_table,
    upload_path,
    write_load_files,
    write_upload,
)
from tests.integration.wq_support import alembic_config, database_url, reset_schema

pytestmark = pytest.mark.integration
SCHEMA = "w1_data_import_test"
AS_OF = date(2026, 11, 4)
NETWORK_TABLES = (
    "networks", "dataset_versions", "import_events", "net_locations", "net_products",
    "net_batches", "net_demand_history", "net_donation_history", "net_inbound", "net_routes",
)
STOCK_TABLES = (
    "stock_ledger", "stock_commands", "inventory_lots", "receipts", "receipt_lines",
    "receipt_postings", "supply_receipts",
)
FILES = {
    "locations": "location_id,name,type,street,city,state,zip\n"
                 "H1,North Hub,hub,301 S Monroe St,Tallahassee,FL,32301\n"
                 "P1,Pantry One,pantry,201 E University Ave,Gainesville,FL,32601\n",
    "products": "product_id,name,unit\nRICE,Rice,case\nBEANS,Beans,case\n",
    "inventory": "location_id,product_id,batch_id,quantity,expiry_date,non_expiring,received_date\n"
                 "H1,RICE,B1,40,2026-12-01,,2026-10-01\n"
                 "H1,RICE,B2,100000,2026-11-05,,\n"
                 "P1,BEANS,B1,0,,true,\n",
    "demand_history": "location_id,product_id,date,quantity,basis\n"
                      "P1,RICE,2026-11-01,3,demand\n"
                      "P1,RICE,2026-11-02,,demand\n"
                      "P1,BEANS,2026-11-03,0,sales\n",
}
NEW = NewNetwork(name="Leon Pantries", mode="PANTRY", timezone="America/New_York")


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


def _counts(engine, tables) -> dict[str, int]:
    with engine.connect() as conn:
        return {t: conn.scalar(sa.text(f"SELECT count(*) FROM {t}")) for t in tables}


def _import(engine, tmp_path: Path, files: dict[str, str], network=NEW, as_of=AS_OF):
    with engine.begin() as conn:
        run = repo.create_run(conn, network if isinstance(network, NewNetwork) else None,
                              network if isinstance(network, uuid.UUID) else None)
    _write(engine, tmp_path, run.id, files)
    return run_import(engine, run.id, as_of, tmp_path, actor="local")


def _write(engine, base: Path, run_id: uuid.UUID, files: dict[str, str]) -> None:
    """Upload each file as the API does: stream to the imports folder, then record it."""
    async def chunks(text):
        yield text.encode()

    for name, text in files.items():
        size, sha = asyncio.run(write_upload(base, run_id, name, chunks(text)))
        with engine.begin() as conn:
            repo.record_file(conn, run_id, name, size, sha)


def test_clean_import_commits_everything(engine, tmp_path):
    outcome = _import(engine, tmp_path, FILES)
    assert outcome.ok, outcome.errors
    with engine.connect() as conn:
        version = conn.execute(sa.text(
            "SELECT network_id, as_of_date FROM dataset_versions WHERE id = :v"),
            {"v": outcome.dataset_version_id}).one()
        assert version == (outcome.network_id, AS_OF)
        counts = {t: conn.scalar(sa.text(
            f"SELECT count(*) FROM {t} WHERE dataset_version_id = :v"),
            {"v": outcome.dataset_version_id})
            for t in ("net_locations", "net_products", "net_batches", "net_demand_history")}
    assert counts == {"net_locations": 2, "net_products": 2, "net_batches": 3,
                      "net_demand_history": 3}


def test_products_record_whether_handling_units_were_given(engine, tmp_path):
    """A blank handling_units_per_unit is stored as 1 and flagged, so the scenario can list
    the assumption (CR-w1-data-6)."""
    products = ("product_id,name,unit,handling_units_per_unit\n"
                "RICE,Rice,case,2\nBEANS,Beans,case,\n")
    outcome = _import(engine, tmp_path, {**FILES, "products": products})
    assert outcome.ok, outcome.errors
    with engine.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT external_id, handling_units_per_unit, handling_units_given FROM net_products "
            "WHERE dataset_version_id = :v"), {"v": outcome.dataset_version_id}).all()
    assert {r[0]: (r[1], r[2]) for r in rows} == {"RICE": (2, True), "BEANS": (1, False)}

def test_fractional_handling_units_fail_the_import_and_save_nothing(engine, tmp_path):
    before = _counts(engine, NETWORK_TABLES)
    products = ("product_id,name,unit,handling_units_per_unit\n"
                "RICE,Rice,case,2.5\nBEANS,Beans,case,\n")
    outcome = _import(engine, tmp_path, {**FILES, "products": products})
    assert not outcome.ok and outcome.network_id is None
    assert [(e.file, e.line, e.column, e.code) for e in outcome.errors] == [
        ("products", 2, "handling_units_per_unit", "FRACTIONAL")]
    assert _counts(engine, NETWORK_TABLES) == before


@pytest.mark.parametrize("raw", ["1001", "100000000", "1e9"])
def test_handling_units_over_the_freeze_limit_are_row_errors(engine, tmp_path, raw):
    """However large, it is the 1-1000 row error, so the summary is ROW_ERRORS, never the
    envelope's "reduce the data" (W2-06 A5)."""
    products = ("product_id,name,unit,handling_units_per_unit\n"
                f"RICE,Rice,case,{raw}\nBEANS,Beans,case,\n")
    outcome = _import(engine, tmp_path, {**FILES, "products": products})
    assert not outcome.ok
    assert [(e.line, e.column, e.code, e.fix) for e in outcome.errors] == [
        (2, "handling_units_per_unit", "MALFORMED",
         "Enter a whole number from 1 to 1000, or leave it blank to assume 1")]
    status = api.import_status(SimpleNamespace(engine=engine), None, outcome.import_id)
    assert (status.phase, status.failure.kind) == ("failed", "ROW_ERRORS")


def test_any_error_saves_nothing(engine, tmp_path):
    first = _import(engine, tmp_path / "a", FILES)
    assert first.ok
    before = _counts(engine, NETWORK_TABLES)
    bad = {**FILES, "demand_history": FILES["demand_history"] + "P1,RICE,2026-11-03,-1,demand\n"}
    outcome = _import(engine, tmp_path / "b", bad, network=first.network_id)
    assert not outcome.ok
    assert [(e.file, e.line, e.code) for e in outcome.errors] == [
        ("demand_history", 5, "NEGATIVE")]
    assert _counts(engine, NETWORK_TABLES) == before
    with engine.connect() as conn:
        stored = conn.execute(sa.text(
            "SELECT file, line_no, column_name, code, fix FROM import_errors "
            "WHERE import_run_id = :r"), {"r": outcome.import_id}).all()
        run = conn.execute(sa.text(
            "SELECT phase, error_count, errors_truncated FROM import_runs WHERE id = :r"),
            {"r": outcome.import_id}).one()
    assert [row[:4] for row in stored] == [("demand_history", 5, "quantity", "NEGATIVE")]
    assert stored[0].fix.strip()
    assert tuple(run) == ("failed", 1, False)


def test_batches_round_trip_exact(engine, tmp_path):
    outcome = _import(engine, tmp_path, FILES)
    with engine.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT l.external_id, p.external_id, b.external_id, b.quantity, b.expiry_date, "
            "b.non_expiring, b.received_date FROM net_batches b "
            "JOIN net_locations l ON l.id = b.location_id "
            "JOIN net_products p ON p.id = b.product_id "
            "WHERE b.dataset_version_id = :v ORDER BY 1, 2, 3"),
            {"v": outcome.dataset_version_id}).all()
    assert [tuple(r) for r in rows] == [
        ("H1", "RICE", "B1", 40, date(2026, 12, 1), False, date(2026, 10, 1)),
        ("H1", "RICE", "B2", 100000, date(2026, 11, 5), False, None),
        ("P1", "BEANS", "B1", 0, None, True, None),
    ]


def _prepared(engine, base: Path):
    """A new network's run through the job's `validate` step and `prepare`."""
    with engine.begin() as conn:
        run = repo.create_run(conn, NEW, None)
    _write(engine, base, run.id, FILES)
    with engine.connect() as conn:
        job = job_input(conn, repo.get_run(conn, run.id), AS_OF, base, "local")
    attempt = uuid.uuid4()
    step = write_load_files(job, attempt)
    load_staged(engine, attempt, job, step)
    return run, attempt, job, step


def _batch_partitions(conn) -> list[tuple[str, str]]:
    return [tuple(r) for r in conn.execute(sa.text(
        "SELECT c.relname, pg_get_expr(c.relpartbound, c.oid) FROM pg_inherits i "
        "JOIN pg_class c ON c.oid = i.inhrelid "
        "WHERE i.inhparent = to_regclass('net_batches') ORDER BY 1"))]


def test_publish_attaches_the_batches_partition_prepare_built(engine, tmp_path):
    """W2-06: net_batches is LIST-partitioned by version like the history. Publish ATTACHes the
    very table prepare loaded, so no batch row is inserted under the queue lock."""
    run, attempt, job, step = _prepared(engine, tmp_path)
    with engine.connect() as conn:
        loaded = conn.scalar(sa.text("SELECT to_regclass(CAST(:t AS text))::oid"),
                             {"t": stage_table(attempt, "batches")})
    with engine.begin() as conn:
        publish_staged(conn, run.organization_id, attempt, job, step)
    version = uuid.UUID(step["dataset_version_id"])
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT pg_get_partkeydef(to_regclass('net_batches'))")) == (
            "LIST (dataset_version_id)")
        home = conn.execute(sa.text(
            "SELECT c.relname, pg_get_expr(c.relpartbound, c.oid) FROM pg_inherits i "
            "JOIN pg_class c ON c.oid = i.inhrelid "
            "WHERE i.inhparent = to_regclass('net_batches') AND i.inhrelid = :oid"),
            {"oid": loaded}).one()
        assert tuple(home) == (f"net_batches_{version.hex}", f"FOR VALUES IN ('{version}')")
        assert conn.scalar(sa.text(f"SELECT count(*) FROM net_batches_{version.hex}")) == 3
        assert conn.scalar(sa.text(
            "SELECT count(*) FROM pg_constraint WHERE contype = 'f' AND conrelid = :oid"),
            {"oid": loaded}) == 4  # organization, version, location, product: the parent's


PARTITIONED = ("net_batches", "net_demand_history", "net_donation_history")


def _foreign_keys(conn, table: str) -> list[str]:
    return sorted(conn.scalars(sa.text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE contype = 'f' "
        "AND conrelid = to_regclass(CAST(:t AS text))"), {"t": table}))


@pytest.mark.parametrize("referenced", [
    "dataset_versions", "net_locations", "net_products", "organizations"])
def test_publish_does_not_wait_for_readers_of_referenced_tables(engine, tmp_path, referenced):
    """Lead review F1: a reader idle in a transaction on a table the partitions reference must
    not block publish. Merging a partition's own FK at ATTACH drops its triggers on the
    referenced table under an ACCESS EXCLUSIVE lock; cloning the parent's FK does not."""
    run, attempt, job, step = _prepared(engine, tmp_path)
    with engine.connect() as reader, reader.begin():
        reader.execute(sa.text(f"SELECT count(*) FROM {referenced}"))
        with engine.begin() as conn:
            conn.execute(sa.text("SET LOCAL lock_timeout = '1s'"))
            assert publish_staged(conn, run.organization_id, attempt, job, step)["ok"]
    version = uuid.UUID(step["dataset_version_id"])
    with engine.connect() as conn:
        for table in PARTITIONED:  # exactly the parent's FKs, none duplicated
            assert _foreign_keys(conn, f"{table}_{version.hex}") == _foreign_keys(conn, table)


def test_attached_partitions_refuse_rows_their_fks_forbid(engine, tmp_path):
    outcome = _import(engine, tmp_path, FILES)
    version = outcome.dataset_version_id
    with engine.connect() as conn:
        loc, prod = conn.execute(sa.text(
            "SELECT l.id, p.id FROM net_locations l JOIN net_products p USING "
            "(dataset_version_id) WHERE l.dataset_version_id = :v LIMIT 1"), {"v": version}).one()
    key = {"org": _run_org(engine, outcome.import_id), "v": version, "l": loc, "p": prod}
    batch = ("INSERT INTO net_batches (id, organization_id, dataset_version_id, location_id, "
             "product_id, external_id, quantity, non_expiring) "
             "VALUES (gen_random_uuid(), :org, :v, :l, :p, 'NEW', 1, true)")
    demand = ("INSERT INTO net_demand_history (organization_id, dataset_version_id, location_id, "
              "product_id, day, quantity, basis) VALUES (:org, :v, :l, :p, '2026-10-01', 1, "
              "'demand')")
    for sql, change in ((batch, {"l": uuid.uuid4()}), (batch, {"p": uuid.uuid4()}),
                        (batch, {"org": uuid.uuid4()}), (demand, {"l": uuid.uuid4()}),
                        (demand, {"p": uuid.uuid4()})):
        with pytest.raises(sa.exc.IntegrityError, match="foreign key"), engine.begin() as conn:
            conn.execute(sa.text(sql), {**key, **change})
    with pytest.raises(sa.exc.IntegrityError, match="foreign key"), engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM net_products WHERE id = :p"), key)  # ON DELETE RESTRICT


def _run_org(engine, import_id: uuid.UUID) -> uuid.UUID:
    with engine.connect() as conn:
        return conn.scalar(sa.text("SELECT organization_id FROM import_runs WHERE id = :r"),
                           {"r": import_id})


def test_a_publish_rolled_back_leaves_no_batches_partition(engine, tmp_path):
    """All or nothing: a publication that does not commit attaches nothing; discard then drops
    the attempt's tables."""
    run, attempt, job, step = _prepared(engine, tmp_path)
    with engine.connect() as conn:
        before = _batch_partitions(conn)
    with pytest.raises(RuntimeError, match="lost the lock"), engine.begin() as conn:
        publish_staged(conn, run.organization_id, attempt, job, step)
        raise RuntimeError("lost the lock")
    drop_staged(engine, attempt)
    with engine.connect() as conn:
        assert _batch_partitions(conn) == before
        assert conn.scalar(sa.text("SELECT count(*) FROM net_batches WHERE dataset_version_id = "
                                   ":v"), {"v": step["dataset_version_id"]}) == 0
        assert conn.scalar(sa.text(
            "SELECT count(*) FROM pg_tables WHERE schemaname = current_schema() "
            "AND tablename LIKE 'pp\\_stage\\_%'")) == 0


def test_blank_demand_stays_null_in_database(engine, tmp_path):
    outcome = _import(engine, tmp_path, FILES)
    with engine.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT p.external_id, h.day, h.quantity, h.basis FROM net_demand_history h "
            "JOIN net_products p ON p.id = h.product_id "
            "WHERE h.dataset_version_id = :v ORDER BY h.day"),
            {"v": outcome.dataset_version_id}).all()
    assert [tuple(r) for r in rows] == [
        ("RICE", date(2026, 11, 1), 3, "demand"),
        ("RICE", date(2026, 11, 2), None, "demand"),
        ("BEANS", date(2026, 11, 3), 0, "sales"),
    ]


def test_donations_summed_and_unknown_kept_null(engine, tmp_path):
    donations = ("location_id,product_id,date,quantity,donor\n"
                 "P1,RICE,2026-10-30,5,Church\nP1,RICE,2026-10-30,,Club\n"
                 "P1,RICE,2026-11-01,2,Church\nP1,RICE,2026-11-01,3,Club\n"
                 "P1,RICE,2026-11-02,0,\nP1,RICE,2026-11-03,,\n")
    outcome = _import(engine, tmp_path, {**FILES, "donation_history": donations})
    assert outcome.ok, outcome.errors
    with engine.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT day, quantity, donor FROM net_donation_history "
            "WHERE dataset_version_id = :v ORDER BY day"),
            {"v": outcome.dataset_version_id}).all()
    assert [tuple(r) for r in rows] == [
        (date(2026, 10, 30), None, "Church; Club"),  # one blank row: the day stays unknown
        (date(2026, 11, 1), 5, "Church; Club"), (date(2026, 11, 2), 0, None),
        (date(2026, 11, 3), None, None)]


def test_one_audited_import_event(engine, tmp_path):
    outcome = _import(engine, tmp_path, FILES)
    with engine.connect() as conn:
        events = conn.execute(sa.text(
            "SELECT import_run_id, actor, files FROM import_events "
            "WHERE dataset_version_id = :v"), {"v": outcome.dataset_version_id}).all()
    assert len(events) == 1
    assert events[0].import_run_id == outcome.import_id and events[0].actor == "local"
    assert sorted(f["name"] for f in events[0].files) == sorted(FILES)
    assert all(len(f["sha256"]) == 64 and f["bytes"] > 0 for f in events[0].files)


def test_new_network_row_created_only_by_successful_commit(engine, tmp_path):
    named = NewNetwork(name=f"Atomic {uuid.uuid4().hex[:8]}", mode="PANTRY",
                       timezone="America/New_York")

    def networks_named():
        with engine.connect() as conn:
            return conn.scalar(sa.text("SELECT count(*) FROM networks WHERE name = :n"),
                               {"n": named.name})

    bad = {**FILES, "inventory": FILES["inventory"] + "X9,RICE,B9,1,2026-12-01,,\n"}
    failed = _import(engine, tmp_path / "a", bad, network=named)
    assert not failed.ok and failed.network_id is None
    assert networks_named() == 0
    with engine.connect() as conn:
        assert conn.scalar(sa.text(
            "SELECT count(*) FROM dataset_versions WHERE import_run_id = :r"),
            {"r": failed.import_id}) == 0

    fixed = _import(engine, tmp_path / "b", FILES, network=named)
    assert fixed.ok and fixed.network_id is not None
    assert networks_named() == 1
    with engine.connect() as conn:
        network = conn.execute(sa.text(
            "SELECT n.mode, n.timezone, r.network_id, r.phase FROM networks n "
            "JOIN import_runs r ON r.network_id = n.id WHERE r.id = :r"),
            {"r": fixed.import_id}).one()
    assert tuple(network) == ("PANTRY", "America/New_York", fixed.network_id, "done")


def test_import_writes_no_stock_ledger_or_receipt_rows(engine, tmp_path):
    before = _counts(engine, STOCK_TABLES)
    assert _import(engine, tmp_path, FILES).ok
    assert _counts(engine, STOCK_TABLES) == before


def test_inbound_outside_horizon_kept_and_listed(engine, tmp_path):
    inbound = ("location_id,product_id,quantity,arrival_date,expiry_date,non_expiring,source\n"
               "P1,RICE,4,2026-11-06,2026-12-01,,dc_delivery\n"
               "P1,RICE,6,2026-11-20,,true,\n")
    outcome = _import(engine, tmp_path, {**FILES, "inbound": inbound})
    assert outcome.ok, outcome.errors
    assert [(r.line, r.quantity, r.arrival_date) for r in outcome.outside_horizon_inbound] == [
        (3, 6, date(2026, 11, 20))]
    with engine.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT line_no, quantity, within_horizon, source FROM net_inbound "
            "WHERE dataset_version_id = :v ORDER BY line_no"),
            {"v": outcome.dataset_version_id}).all()
    assert [tuple(r) for r in rows] == [(2, 4, True, "dc_delivery"), (3, 6, False, None)]


def test_staging_dropped_and_files_kept_only_after_failure(engine, tmp_path):
    # W0-08 §4: a failed import keeps its run, errors and uploaded files; success deletes them.
    good = _import(engine, tmp_path / "a", FILES)
    bad = _import(engine, tmp_path / "b",
                  {**FILES, "products": "product_id,name,unit\nRICE,Rice,case\nRICE,Again,case\n"})
    assert good.ok and not bad.ok
    with engine.connect() as conn:
        parts = conn.scalar(sa.text(
            "SELECT count(*) FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid "
            "JOIN pg_class p ON p.oid = i.inhparent WHERE p.relname = 'import_staging'"))
    assert parts == 0
    assert not list((tmp_path / "a").rglob("*.csv"))
    assert sorted(p.name for p in (tmp_path / "b").rglob("*.csv")) == sorted(
        f"{name}.csv" for name in FILES)


def test_upload_over_cap_is_413_and_partial_file_deleted(engine, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.routers import v1_imports
    from app.routers.forecasts import presenter, runtime

    with engine.begin() as conn:
        run = repo.create_run(conn, NEW, None)
    monkeypatch.setattr(v1_imports, "UPLOAD_CAP_BYTES", 1000)
    monkeypatch.setenv("PP_IMPORT_DIR", str(tmp_path))
    app = create_app()
    app.dependency_overrides[runtime] = lambda: SimpleNamespace(engine=engine)
    app.dependency_overrides[presenter] = lambda: SimpleNamespace(
        organization_id=uuid.UUID(int=1), actor="local")
    client = TestClient(app)

    monkeypatch.setattr(v1_imports, "UPLOAD_CAP_BYTES", 100_000)
    past_boundary = client.post(f"/api/v1/imports/{run.id}/files/routes", content=b"a" * 70_000,
                                headers={"Content-Type": "text/csv"})
    assert past_boundary.status_code == 200, past_boundary.text  # not the 64 KB RequestBoundary
    assert past_boundary.json()["bytes"] == 70_000
    monkeypatch.setattr(v1_imports, "UPLOAD_CAP_BYTES", 1000)

    small = client.post(f"/api/v1/imports/{run.id}/files/products",
                        content=FILES["products"].encode(), headers={"Content-Type": "text/csv"})
    assert small.status_code == 200, small.text
    assert small.json()["bytes"] == len(FILES["products"])

    def body():
        for _ in range(10):
            yield b"x" * 500

    big = client.post(f"/api/v1/imports/{run.id}/files/demand_history", content=body(),
                      headers={"Content-Type": "text/csv"})
    assert big.status_code == 413
    assert big.json()["error"]["code"] == "INPUT_TOO_LARGE"
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == [
        "products.csv", "routes.csv"]
    with engine.connect() as conn:
        files = conn.scalar(sa.text("SELECT files FROM import_runs WHERE id = :r"), {"r": run.id})
    assert [f["name"] for f in files] == ["routes", "products"]


def test_upload_after_commit_started_is_409(engine, tmp_path, monkeypatch):
    with engine.begin() as conn:
        run = repo.create_run(conn, NEW, None)
        repo.set_phase(conn, run.id, "staging")

    async def chunks():
        yield b"product_id,name,unit\n"

    from app.services.imports.api import store_import_file
    from app.services.presenter_access import AccessError

    monkeypatch.setenv("PP_IMPORT_DIR", str(tmp_path))
    with pytest.raises(AccessError) as raised:
        asyncio.run(store_import_file(SimpleNamespace(engine=engine), None, run.id,
                                      "products", chunks()))
    assert raised.value.status == 409


def _on_disk_matches_record(engine, base: Path, run_id: uuid.UUID, name: str) -> bool:
    with engine.connect() as conn:
        files = conn.scalar(sa.text("SELECT files FROM import_runs WHERE id = :r"), {"r": run_id})
    recorded = next(f["sha256"] for f in files if f["name"] == name)
    on_disk = hashlib.sha256(upload_path(base, run_id, name).read_bytes()).hexdigest()
    return recorded == on_disk


def test_an_upload_refused_mid_stream_leaves_the_recorded_file_in_place(
        engine, tmp_path, monkeypatch):
    """The commit lands while a re-upload streams: the job must read the bytes it recorded."""
    from app.services.imports.api import store_import_file
    from app.services.presenter_access import AccessError

    monkeypatch.setenv("PP_IMPORT_DIR", str(tmp_path))
    with engine.begin() as conn:
        run = repo.create_run(conn, NEW, None)
    rt = SimpleNamespace(engine=engine)

    async def first():
        yield b"product_id,name,unit\nRICE,Rice,case\n"

    async def replacement():
        yield b"product_id,name,unit\n"
        with engine.begin() as conn:  # the commit, between the two checks
            repo.set_phase(conn, run.id, "staging")
        yield b"BEANS,Beans,case\n"

    asyncio.run(store_import_file(rt, None, run.id, "products", first()))
    with pytest.raises(AccessError):
        asyncio.run(store_import_file(rt, None, run.id, "products", replacement()))
    assert _on_disk_matches_record(engine, tmp_path, run.id, "products")
    assert not list(upload_path(tmp_path, run.id, "products").parent.glob("*.part"))


def test_overlapping_uploads_of_one_file_keep_disk_and_record_in_step(
        engine, tmp_path, monkeypatch):
    """A client retry while the first upload still streams: whichever wins, the file on disk
    is the one recorded."""
    from app.services.imports.api import store_import_file

    monkeypatch.setenv("PP_IMPORT_DIR", str(tmp_path))
    with engine.begin() as conn:
        run = repo.create_run(conn, NEW, None)
    rt = SimpleNamespace(engine=engine)

    async def both():
        retried = asyncio.Event()

        async def slow():
            yield b"product_id,name,unit\n"
            await retried.wait()
            yield b"RICE,Rice,case\n"

        async def fast():
            yield b"product_id,name,unit\nBEANS,Beans,case\n"

        async def retry():
            await store_import_file(rt, None, run.id, "products", fast())
            retried.set()

        return await asyncio.gather(
            store_import_file(rt, None, run.id, "products", slow()), retry(),
            return_exceptions=True)

    asyncio.run(both())
    assert _on_disk_matches_record(engine, tmp_path, run.id, "products")
