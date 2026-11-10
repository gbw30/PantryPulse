"""Uploaded files and the import.v1 commit path (W1-D04, W1-D05, S4, CR-w1-data-2).

The job splits the all-or-nothing commit in three, so nothing slow runs under the queue lock:
- `write_load_files` is the DB-less `validate` step: it streams every file through the W1-D02
  Validator and writes COPY-ready CSVs (rows with their new ids, raw history) to the imports
  volume, in a folder named by the attempt.
- `load_staged` is `prepare`, outside the lock: it drops what crashed attempts left, then
  COPYs those files into tables named by the attempt and builds the version's batches and
  history partitions with their keys (S4 variant e4, without FKs).
- `publish_staged` is `publish`, inside the lock: the error report, or the network (first
  import), the version, the small row inserts from the staged tables, and ATTACH, which clones
  and validates the parent's FKs. No batch row is inserted under the lock (W2-06).
`drop_staged` is `discard`. Any failure before the publication commits saves nothing.
`run_import` runs the same three in one process (tests and the bench).
"""

import csv
import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import IO, Any
from uuid import UUID

import sqlalchemy as sa

from app.repositories import imports as repo
from app.schemas.v1_enrichment import GeoLocation
from app.schemas.v1_imports import ImportSettings, OutsideHorizonInbound, RowError
from app.services.enrichment.distance import route_rows
from app.services.imports.validate import ParsedNetwork, Validator
from app.services.jobs.registry import PublicationRejected

KEY_COLUMNS = "organization_id, dataset_version_id, location_id, product_id, day"
HISTORY_TABLES = {"demand_history": ("net_demand_history", "demand"),
                  "donation_history": ("net_donation_history", "donation")}
STAGE_PREFIX = "pp_stage_"
# File (and staged-table suffix) -> table and COPY columns, in insert order (FKs).
LOAD_FILES = {
    "locations": ("net_locations", "id, organization_id, dataset_version_id, external_id, "
                  "name, role, street, city, state, zip, latitude, longitude, "
                  "coordinates_source, receiving_capacity_per_day, manual_poverty_rate, "
                  "manual_snap_rate"),
    "products": ("net_products", "id, organization_id, dataset_version_id, external_id, name, "
                 "unit, unit_value_usd, handling_units_per_unit, handling_units_given"),
    "batches": ("net_batches", "id, organization_id, dataset_version_id, location_id, "
                "product_id, external_id, quantity, expiry_date, non_expiring, received_date"),
    "routes": ("net_routes", "id, organization_id, dataset_version_id, from_location_id, "
               "to_location_id, method, distance_miles, road_hours, travel_days, "
               "cost_per_handling_unit, capacity_per_batch, is_override, disabled"),
    "inbound": ("net_inbound", "id, organization_id, dataset_version_id, location_id, "
                "product_id, line_no, quantity, arrival_date, expiry_date, non_expiring, "
                "source, reference, within_horizon"),
}
RAW_COLUMNS = "file, line_no, c01, c02, c03, c04, c05"
HISTORY_KEY = "PRIMARY KEY (dataset_version_id, location_id, product_id, day)"
# Version-partitioned tables by staged suffix: table and the keys prepare builds. The FKs are the
# parent's, cloned and validated by ATTACH in publish: a partition's own FK would be merged there,
# which drops its triggers on the referenced table under an ACCESS EXCLUSIVE lock, so any reader
# of dataset_versions, net_locations, net_products or organizations would block publish.
PARTITIONS = {
    "batches": ("net_batches", (
        "PRIMARY KEY (dataset_version_id, id)",
        "UNIQUE (dataset_version_id, location_id, product_id, external_id)",
    )),
    "demand": ("net_demand_history", (HISTORY_KEY,)),
    "donation": ("net_donation_history", (HISTORY_KEY,)),
}


def import_dir() -> Path:
    """The `imports` volume shared by api and worker (compose sets PP_IMPORT_DIR)."""
    # shortcut: outside compose both processes share the host temp dir; set PP_IMPORT_DIR there.
    return Path(os.environ.get("PP_IMPORT_DIR") or Path(tempfile.gettempdir()) / "pp-imports")


def upload_path(base: Path, import_id: UUID, name: str) -> Path:
    return base / str(import_id) / f"{name}.csv"


async def stream_upload(base: Path, import_id: UUID, name: str,
                        chunks: AsyncIterator[bytes]) -> tuple[Path, int, str]:
    """Stream to this upload's own `<name>.csv.<random>.part`; the caller renames it into
    place where it records the file. A failed or over-cap upload leaves nothing."""
    target = upload_path(base, import_id, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f"{target.name}.{uuid.uuid4().hex}.part")
    digest, size = hashlib.sha256(), 0
    try:
        with partial.open("wb") as out:
            async for chunk in chunks:
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return partial, size, digest.hexdigest()


async def write_upload(base: Path, import_id: UUID, name: str,
                       chunks: AsyncIterator[bytes]) -> tuple[int, str]:
    """Stream, then rename into place (tests and the bench; the API renames under its lock)."""
    partial, size, sha256 = await stream_upload(base, import_id, name, chunks)
    os.replace(partial, upload_path(base, import_id, name))
    return size, sha256


@dataclass(frozen=True, slots=True)
class ImportOutcome:
    import_id: UUID
    ok: bool
    network_id: UUID | None
    dataset_version_id: UUID | None
    as_of_date: date | None
    error_count: int
    errors: tuple[RowError, ...]
    outside_horizon_inbound: tuple[OutsideHorizonInbound, ...] = field(default=())


def _finished(conn: sa.Connection, run: repo.Run) -> ImportOutcome:
    version = conn.execute(sa.text(
        "SELECT id, as_of_date FROM dataset_versions WHERE import_run_id = :r"),
        {"r": run.id}).one_or_none()
    errors = tuple(repo.stored_errors(conn, run.id))
    return ImportOutcome(run.id, version is not None, run.network_id,
                         version.id if version else None, version.as_of_date if version else None,
                         run.error_count, errors,
                         tuple(repo.outside_horizon(conn, version.id)) if version else ())


def _network_settings(conn: sa.Connection, run: repo.Run) -> dict[str, Any]:
    if run.new_network is not None:
        return run.new_network
    row = conn.execute(sa.text("SELECT name, mode, timezone FROM networks WHERE id = :id"),
                       {"id": run.network_id}).one()
    return dict(row._mapping)


def _data_lines(path: Path) -> int:
    """Physical lines after the header: the staging total (S4 §6); quoted newlines overcount."""
    lines, last = 0, b"\n"
    with path.open("rb") as f:
        while block := f.read(1 << 20):
            lines += block.count(b"\n")
            last = block[-1:]
    return max(0, lines + (last != b"\n") - 1)


class _Progress:
    """Writes progress on its own short transactions, outside the import transaction."""

    def __init__(self, engine: sa.Engine, import_id: UUID):
        self.engine, self.import_id = engine, import_id

    def phase(self, phase: str, unit: str, done: int, total: int | None) -> None:
        with self.engine.begin() as conn:
            repo.set_phase(conn, self.import_id, phase,
                           progress={"unit": unit, "done": done, "total": total})


def stage_table(attempt_id: UUID, suffix: str) -> str:
    return f"{STAGE_PREFIX}{attempt_id.hex}_{suffix}"


def attempt_dir(base: Path, import_id: UUID, attempt_id: UUID) -> Path:
    return base / str(import_id) / f"attempt-{attempt_id.hex}"


def job_input(conn: sa.Connection, run: repo.Run, as_of_date: date | None, base: Path,
              actor: str) -> dict[str, Any]:
    """The import.v1 payload: everything the DB-less step needs, read at commit. The step
    child's environment has no PP_IMPORT_DIR, so the folder travels in the payload."""
    network = _network_settings(conn, run)
    return {"import_id": str(run.id), "organization_id": str(run.organization_id),
            "as_of_date": None if as_of_date is None else as_of_date.isoformat(),
            "mode": network["mode"], "timezone": network["timezone"],
            "files": sorted(f["name"] for f in run.files),
            "import_dir": str(Path(base).absolute()), "actor": actor}


def run_import(engine: sa.Engine, import_id: UUID, as_of_date: date | None, base: Path,
               actor: str, on_phase: Callable[[str], None] | None = None) -> ImportOutcome:
    """The import.v1 job in one process: the same step, prepare and publish."""
    with engine.connect() as conn:
        run = repo.get_run(conn, import_id)
        if run.phase in ("done", "failed"):  # a retried job never imports twice
            return _finished(conn, run)
        job = job_input(conn, run, as_of_date, base, actor)
    total = sum(_data_lines(upload_path(base, import_id, name)) for name in job["files"])
    _Progress(engine, import_id).phase("staging", "rows", 0, total)
    if on_phase:
        on_phase("staging")
    attempt_id = uuid.uuid4()
    step = write_load_files(job, attempt_id)
    try:
        load_staged(engine, attempt_id, job, step, on_phase=on_phase)
        with engine.begin() as conn:
            publish_staged(conn, run.organization_id, attempt_id, job, step)
    except BaseException:
        drop_staged(engine, attempt_id)
        raise
    if step["ok"]:  # committed: the uploads are no longer needed
        shutil.rmtree(base / str(import_id), ignore_errors=True)
    with engine.connect() as conn:
        return _finished(conn, repo.get_run(conn, import_id))


# --- step: no database ----------------------------------------------------------------------

def _writer(stream: IO[str]):
    """COPY ... (FORMAT csv): None is an unquoted empty field (NULL), '' stays a string."""
    return csv.writer(stream, quoting=csv.QUOTE_STRINGS, lineterminator="\n")


def write_load_files(job: Mapping[str, Any], attempt_id: UUID) -> dict[str, Any]:
    """The `validate` step: check every file and write the load-ready CSVs."""
    base, import_id = Path(job["import_dir"]), UUID(job["import_id"])
    folder = attempt_dir(base, import_id, attempt_id)
    folder.mkdir(parents=True, exist_ok=True)
    paths = {name: upload_path(base, import_id, name) for name in job["files"]}
    as_of = job["as_of_date"] and date.fromisoformat(job["as_of_date"])
    validator = Validator(ImportSettings(mode=job["mode"], timezone=job["timezone"],
                                         as_of_date=as_of))
    with ExitStack() as stack:
        streams = {name: stack.enter_context(path.open("rb")) for name, path in paths.items()}
        history = _writer(stack.enter_context((folder / "history.csv").open("w", newline="")))
        validator.history_sink = lambda name, r: history.writerow((
            name, r.line, r.location_id, r.product_id, r.day, r.quantity,
            r.basis if name == "demand_history" else r.donor))
        report = validator.run(streams)
    output = {"ok": report.ok, "error_count": report.error_count,
              "errors": [e.model_dump(mode="json") for e in report.errors],
              "rows": sum(_data_lines(p) for p in paths.values()),
              "as_of_date": None, "dataset_version_id": None}
    if report.ok:
        version_id = uuid.uuid4()
        _write_rows(folder, UUID(job["organization_id"]), version_id, report.rows)
        output.update(as_of_date=report.rows.as_of_date.isoformat(),
                      dataset_version_id=str(version_id))
    return output


def _write_rows(folder: Path, org: UUID, version_id: UUID, rows: ParsedNetwork) -> None:
    key = (org, version_id)
    locations = {r.location_id: uuid.uuid4() for r in rows.locations}
    products = {p.product_id: uuid.uuid4() for p in rows.products}
    geo = [GeoLocation(id=r.location_id, latitude=r.latitude, longitude=r.longitude,
                       role=r.role) for r in rows.locations if r.latitude is not None]
    tables = {
        "locations": ((locations[r.location_id], *key, r.location_id, r.name, r.role, r.street,
                       r.city, r.state, r.zip, r.latitude, r.longitude,
                       "user" if r.latitude is not None else None,
                       r.receiving_capacity_per_day, r.poverty_rate, r.snap_rate)
                      for r in rows.locations),
        "products": ((products[p.product_id], *key, p.product_id, p.name, p.unit,
                      p.unit_value_usd, p.handling_units_per_unit, p.handling_units_given)
                     for p in rows.products),
        "batches": ((uuid.uuid4(), *key, locations[b.location_id], products[b.product_id],
                     b.batch_id, b.quantity, b.expiry_date, b.non_expiring, b.received_date)
                    for b in rows.batches),
        "routes": ((uuid.uuid4(), *key, locations[r["from"]], locations[r["to"]], r["method"],
                    r["distance_miles"], r["road_hours"], r["travel_days"], r["cost"],
                    r["capacity"], r["is_override"], r["disabled"])
                   for r in route_rows(geo, rows.routes)),
        "inbound": ((uuid.uuid4(), *key, locations[r.location_id], products[r.product_id],
                     r.line, r.quantity, r.arrival_date, r.expiry_date, r.non_expiring,
                     r.source, r.reference, r.within_horizon) for r in rows.inbound),
    }
    for name, values in tables.items():
        with (folder / f"{name}.csv").open("w", newline="") as out:
            _writer(out).writerows(values)


# --- prepare: outside the queue lock ---------------------------------------------------------

def load_staged(engine: sa.Engine, attempt_id: UUID, job: Mapping[str, Any],
                step: Mapping[str, Any], *, timeout_s: float | None = None,
                on_phase: Callable[[str], None] | None = None) -> None:
    base, import_id = Path(job["import_dir"]), UUID(job["import_id"])
    folder = attempt_dir(base, import_id, attempt_id)
    try:
        _sweep(engine, base, attempt_id)
        if not step["ok"]:
            return
        progress = _Progress(engine, import_id)
        checks = len(job["files"])
        for phase, unit, done, total in (("validating", "checks", checks, checks),
                                         ("committing", "rows", 0, step["rows"])):
            progress.phase(phase, unit, done, total)
            if on_phase:
                on_phase(phase)
        org, version_id = UUID(job["organization_id"]), UUID(step["dataset_version_id"])
        with engine.begin() as conn:
            if timeout_s:
                conn.execute(sa.text(f"SET LOCAL statement_timeout = {int(timeout_s * 1000)}"))
            for name, (table, columns) in LOAD_FILES.items():
                staged = stage_table(attempt_id, name)
                if name in PARTITIONS:  # a partition to be: logged, with the parent's CHECKs
                    conn.execute(sa.text(f"CREATE TABLE {staged} (LIKE {table} "
                                         f"INCLUDING DEFAULTS INCLUDING CONSTRAINTS)"))
                else:
                    conn.execute(sa.text(
                        f"CREATE UNLOGGED TABLE {staged} (LIKE {table} INCLUDING DEFAULTS)"))
                _copy(conn, staged, columns, folder / f"{name}.csv")
                if name in PARTITIONS:
                    _partition_keys(conn, staged, name, version_id)
            raw = stage_table(attempt_id, "raw")
            conn.execute(sa.text(f"CREATE UNLOGGED TABLE {raw} (file text, line_no integer, "
                                 "c01 text, c02 text, c03 text, c04 text, c05 text)"))
            _copy(conn, raw, RAW_COLUMNS, folder / "history.csv")
            for name in HISTORY_TABLES:
                _load_history(conn, name, raw, attempt_id, org, version_id)
            conn.execute(sa.text(f"DROP TABLE {raw}"))
            stamp = datetime.now(UTC).isoformat()  # _sweep's age check: when this attempt staged
            for name in _staged_tables(conn):
                if name.startswith(stage_table(attempt_id, "")):
                    conn.execute(sa.text(f"COMMENT ON TABLE {name} IS '{stamp}'"))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _copy(conn: sa.Connection, table: str, columns: str, path: Path) -> None:
    cursor = conn.connection.driver_connection.cursor()
    with cursor.copy(f"COPY {table} ({columns}) FROM STDIN (FORMAT csv)") as copy, \
            path.open("rb") as source:
        while block := source.read(1 << 20):
            copy.write(block)


def _staged_tables(conn: sa.Connection) -> list[str]:
    return list(conn.scalars(sa.text(
        "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
        "AND tablename LIKE 'pp\\_stage\\_%'")))


# An import attempt lives at most import_total_s (300 s); staging older than this is an orphan.
ORPHAN_AGE_S = 3600


def _stamped_before(stamp: str | None, cutoff: float) -> bool:
    try:
        return datetime.fromisoformat(stamp).timestamp() < cutoff  # type: ignore[arg-type]
    except (TypeError, ValueError):  # no stamp: not staged by a load_staged that finished
        return True


def _modified_before(path: Path, cutoff: float) -> bool:
    try:
        return path.stat().st_mtime < cutoff
    except FileNotFoundError:  # its own attempt already removed it
        return False


def _sweep(engine: sa.Engine, base: Path, attempt_id: UUID) -> None:
    """Clear what earlier attempts left: `discard` never runs after an uncertain commit, or
    when a supervisor dies between prepare and publish. The sample seed stages outside the
    queue, beside a live worker (code-review #3), so another attempt's staged table or folder is
    an orphan only once it is older than ORPHAN_AGE_S, or a table carries no staging stamp.
    A done import's uploads are no longer needed."""
    mine, cutoff = stage_table(attempt_id, ""), time.time() - ORPHAN_AGE_S
    with engine.begin() as conn:
        for name, stamp in conn.execute(sa.text(
                "SELECT c.relname, obj_description(c.oid, 'pg_class') FROM pg_class c "
                "WHERE c.relnamespace = current_schema()::regnamespace AND c.relkind = 'r' "
                "AND c.relname LIKE 'pp\\_stage\\_%'")):
            if not name.startswith(mine) and _stamped_before(stamp, cutoff):
                conn.execute(sa.text(f"DROP TABLE IF EXISTS {name}"))
        done = set(conn.scalars(sa.text("SELECT id::text FROM import_runs WHERE phase = 'done'")))
    for folder in base.glob("*/attempt-*"):
        if folder.name != f"attempt-{attempt_id.hex}" and _modified_before(folder, cutoff):
            shutil.rmtree(folder, ignore_errors=True)
    for folder in base.glob("*"):
        if folder.name in done:
            shutil.rmtree(folder, ignore_errors=True)


def _load_history(conn: sa.Connection, name: str, raw: str, attempt_id: UUID, org: UUID,
                  version_id: UUID) -> None:
    """S4 variant e4 up to the FKs: a bare table, bulk INSERT, then its keys."""
    table, suffix = HISTORY_TABLES[name]
    part = stage_table(attempt_id, suffix)
    locations, products = stage_table(attempt_id, "locations"), stage_table(attempt_id, "products")
    if name == "demand_history":
        select = (f"SELECT :org, :ver, l.id, p.id, CAST(s.c03 AS date), CAST(s.c04 AS bigint), "
                  f"s.c05 FROM {raw} s JOIN {locations} l ON l.external_id = s.c01 "
                  f"JOIN {products} p ON p.external_id = s.c02 WHERE s.file = 'demand_history'")
        columns = f"{KEY_COLUMNS}, quantity, basis"
    else:  # summed per receiving location × product × day; donors in first-seen order
        select = (
            f"SELECT :org, :ver, l.id, p.id, CAST(k.c03 AS date), k.quantity, d.donors FROM "
            # one blank row makes the day unknown: sum() would skip it and hide the gap
            f"(SELECT c01, c02, c03, CASE WHEN bool_and(c04 IS NOT NULL) "
            f"THEN sum(CAST(c04 AS bigint)) END AS quantity FROM {raw} "
            f"WHERE file = 'donation_history' GROUP BY c01, c02, c03) k "
            f"LEFT JOIN (SELECT c01, c02, c03, string_agg(c05, '; ' ORDER BY first) AS donors "
            f"FROM (SELECT c01, c02, c03, c05, min(line_no) AS first FROM {raw} "
            f"WHERE file = 'donation_history' AND c05 IS NOT NULL GROUP BY c01, c02, c03, c05) x "
            f"GROUP BY c01, c02, c03) d USING (c01, c02, c03) "
            f"JOIN {locations} l ON l.external_id = k.c01 "
            f"JOIN {products} p ON p.external_id = k.c02")
        columns = f"{KEY_COLUMNS}, quantity, donor"
    for statement in (
        f"CREATE TABLE {part} (LIKE {table} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)",
        f"INSERT INTO {part} ({columns}) {select}",
    ):
        conn.execute(sa.text(statement), {"org": org, "ver": version_id})
    _partition_keys(conn, part, suffix, version_id)


def _partition_keys(conn: sa.Connection, part: str, suffix: str, version_id: UUID) -> None:
    """The keys and the version bound as a CHECK, as on the parent, so ATTACH reuses them instead
    of building its own indexes or scanning to check the bound. No FKs: see PARTITIONS."""
    _, keys = PARTITIONS[suffix]
    for statement in (
        *(f"ALTER TABLE {part} ADD {key}" for key in keys),
        f"ALTER TABLE {part} ADD CHECK (dataset_version_id = '{version_id}')",
    ):
        conn.execute(sa.text(statement))


# --- publish: inside the queue lock -----------------------------------------------------------

def publish_staged(conn: sa.Connection, organization_id: UUID, attempt_id: UUID,
                   job: Mapping[str, Any], step: Mapping[str, Any]) -> dict[str, Any]:
    run = repo.get_run(conn, UUID(job["import_id"]), lock=True)
    if run.organization_id != organization_id:
        raise PublicationRejected("IMPORT_NOT_FOUND")
    if not step["ok"]:
        repo.fail_run(conn, run, [RowError.model_validate(e) for e in step["errors"]],
                      step["error_count"])
        return {"ok": False, "error_count": step["error_count"]}
    network_id, version_id = _commit(conn, run, attempt_id, step, job["actor"])
    return {"ok": True, "network_id": str(network_id), "dataset_version_id": str(version_id)}


def _commit(conn: sa.Connection, run: repo.Run, attempt_id: UUID, step: Mapping[str, Any],
            actor: str) -> tuple[UUID, UUID]:
    org = run.organization_id
    network_id = run.network_id
    if network_id is None:  # atomic import: the network exists only after this commit
        network = _network_settings(conn, run)
        network_id = uuid.uuid4()
        conn.execute(sa.text(
            "INSERT INTO networks (id, organization_id, name, mode, timezone, is_sample) "
            "VALUES (:id, :org, :name, :mode, :tz, :sample)"),
            {"id": network_id, "org": org, "name": network["name"], "mode": network["mode"],
             "tz": network["timezone"], "sample": network.get("is_sample", False)})
    version_id = UUID(step["dataset_version_id"])
    files_hash = hashlib.sha256("".join(
        f"{f['name']}:{f['sha256']}\n" for f in sorted(run.files, key=lambda f: f["name"])
    ).encode()).hexdigest()
    conn.execute(sa.text(
        "INSERT INTO dataset_versions (id, organization_id, network_id, import_run_id, "
        "as_of_date, input_sha256) VALUES (:id, :org, :net, :run, :as_of, :sha)"),
        {"id": version_id, "org": org, "net": network_id, "run": run.id,
         "as_of": date.fromisoformat(step["as_of_date"]), "sha": files_hash})
    for name, (table, _) in LOAD_FILES.items():
        if name in PARTITIONS:
            continue
        staged = stage_table(attempt_id, name)
        conn.execute(sa.text(f"INSERT INTO {table} SELECT * FROM {staged}"))
        conn.execute(sa.text(f"DROP TABLE {staged}"))
    for suffix, (table, _) in PARTITIONS.items():  # ATTACH clones and validates the parent's FKs
        part, final = stage_table(attempt_id, suffix), f"{table}_{version_id.hex}"
        conn.execute(sa.text(f"ALTER TABLE {part} RENAME TO {final}"))
        conn.execute(sa.text(
            f"ALTER TABLE {table} ATTACH PARTITION {final} FOR VALUES IN ('{version_id}')"))
    conn.execute(sa.text(
        "INSERT INTO import_events (id, organization_id, dataset_version_id, import_run_id, "
        "actor, files) VALUES (:id, :org, :ver, :run, :actor, CAST(:files AS jsonb))"),
        {"id": uuid.uuid4(), "org": org, "ver": version_id, "run": run.id, "actor": actor,
         "files": json.dumps(run.files)})
    conn.execute(sa.text(
        "UPDATE import_runs SET network_id = :net, phase = 'done', updated_at = clock_timestamp() "
        "WHERE id = :id"), {"net": network_id, "id": run.id})
    return network_id, version_id


# --- discard --------------------------------------------------------------------------------

def drop_staged(engine: sa.Engine, attempt_id: UUID) -> None:
    """Drop this attempt's staged tables; idempotent."""
    mine = stage_table(attempt_id, "")
    with engine.begin() as conn:
        for name in _staged_tables(conn):
            if name.startswith(mine):
                conn.execute(sa.text(f"DROP TABLE {name}"))
