"""Uploaded files, staging with PostgreSQL COPY and the all-or-nothing commit (W1-D04, S4).

`run_import` does everything in ONE transaction: it creates the run's UNLOGGED staging
partition, streams every file through the W1-D02 Validator while COPYing clean history rows
into staging, then (only with zero errors) inserts the network (first import), the dataset
version, every data row and one import event, loads each history file into its own
per-version partition (S4 variant e4) and drops staging. Any error rolls the whole transaction
back, so nothing is saved; the error report is then written in its own transaction.
Progress goes through a second connection so readers see it while the transaction runs.
"""

import hashlib
import json
import os
import tempfile
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from app.repositories import imports as repo
from app.schemas.v1_imports import ImportSettings, OutsideHorizonInbound, RowError
from app.schemas.v1_networks import TemplateName
from app.services.imports.validate import HistoryRow, ParsedNetwork, Validator

PROGRESS_EVERY_ROWS = 100_000
KEY_COLUMNS = "organization_id, dataset_version_id, location_id, product_id, day"
HISTORY_TABLES = {"demand_history": "net_demand_history",
                  "donation_history": "net_donation_history"}


def import_dir() -> Path:
    """The `imports` volume shared by api and worker (compose sets PP_IMPORT_DIR)."""
    # shortcut: outside compose both processes share the host temp dir; set PP_IMPORT_DIR there.
    return Path(os.environ.get("PP_IMPORT_DIR") or Path(tempfile.gettempdir()) / "pp-imports")


def upload_path(base: Path, import_id: UUID, name: str) -> Path:
    return base / str(import_id) / f"{name}.csv"


async def write_upload(base: Path, import_id: UUID, name: str,
                       chunks: AsyncIterator[bytes]) -> tuple[int, str]:
    """Stream to `<name>.csv.part`, then rename; a failed or over-cap upload leaves nothing."""
    target = upload_path(base, import_id, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".csv.part")
    digest, size = hashlib.sha256(), 0
    try:
        with partial.open("wb") as out:
            async for chunk in chunks:
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        os.replace(partial, target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return size, digest.hexdigest()


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


class _Rejected(Exception):
    """Validation found errors: roll back the import transaction."""


def run_import(engine: sa.Engine, import_id: UUID, as_of_date: date | None, base: Path,
               actor: str, on_phase: Callable[[str], None] | None = None) -> ImportOutcome:
    with engine.connect() as conn:
        run = repo.get_run(conn, import_id)
        network = _network_settings(conn, run)
    settings = ImportSettings(mode=network["mode"], timezone=network["timezone"],
                              as_of_date=as_of_date)
    paths = {f["name"]: upload_path(base, import_id, f["name"]) for f in run.files}
    total_rows = sum(_data_lines(p) for p in paths.values())
    progress = _Progress(engine, import_id)
    progress.phase("staging", "rows", 0, total_rows)
    if on_phase:
        on_phase("staging")
    validator = Validator(settings)
    validator.on_row = progress.row
    staging = f"import_staging_{import_id.hex}"
    try:
        with engine.begin() as conn, ExitStack() as files:
            conn.execute(sa.text(
                f"CREATE UNLOGGED TABLE {staging} PARTITION OF import_staging "
                f"FOR VALUES IN ('{import_id}')"))
            streams = {name: files.enter_context(path.open("rb")) for name, path in paths.items()}
            cursor = conn.connection.driver_connection.cursor()
            with cursor.copy(f"COPY {staging} (import_run_id, file, line_no, ncols, c01, c02, "
                             "c03, c04, c05) FROM STDIN") as copy:
                validator.history_sink = _stage(copy, import_id)
                report = validator.run(streams)
            progress.phase("validating", "checks", len(paths), len(paths))
            if on_phase:
                on_phase("validating")
            if not report.ok:
                raise _Rejected
            rows = report.rows
            progress.phase("committing", "rows", 0, total_rows)
            if on_phase:
                on_phase("committing")
            network_id, version_id = _commit(conn, run, network, rows, staging, run.files, actor)
            conn.execute(sa.text(f"DROP TABLE {staging}"))
    except _Rejected:
        with engine.begin() as conn:
            repo.fail_run(conn, run, report.errors, report.error_count)
        return ImportOutcome(import_id, False, run.network_id, None, None, report.error_count,
                             tuple(report.errors))
    for path in paths.values():
        path.unlink(missing_ok=True)
    return ImportOutcome(
        import_id, True, network_id, version_id, rows.as_of_date, 0, (),
        tuple(OutsideHorizonInbound(line=r.line, location_id=r.location_id,
                                    product_id=r.product_id, quantity=r.quantity,
                                    arrival_date=r.arrival_date)
              for r in rows.inbound if not r.within_horizon))


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
        self.engine, self.import_id, self.rows, self.total = engine, import_id, 0, None

    def phase(self, phase: str, unit: str, done: int, total: int | None) -> None:
        self.rows, self.total = done, total
        with self.engine.begin() as conn:
            repo.set_phase(conn, self.import_id, phase,
                           progress={"unit": unit, "done": done, "total": total})

    def row(self, _name: TemplateName, _line: int) -> None:
        self.rows += 1
        if self.rows % PROGRESS_EVERY_ROWS == 0:
            done = self.rows if self.total is None else min(self.rows, self.total)
            with self.engine.begin() as conn:
                repo.set_progress(conn, self.import_id, "rows", done, self.total)


def _stage(copy, import_id: UUID) -> Callable[[TemplateName, HistoryRow], None]:
    def sink(name: TemplateName, row: HistoryRow) -> None:
        last = row.basis if name == "demand_history" else row.donor
        copy.write_row((import_id, name, row.line, 5, row.location_id, row.product_id,
                        row.day.isoformat(), None if row.quantity is None else str(row.quantity),
                        last))
    return sink


def _commit(conn: sa.Connection, run: repo.Run, network: dict[str, Any], rows: ParsedNetwork,
            staging: str, files: list[dict[str, Any]], actor: str) -> tuple[UUID, UUID]:
    org = run.organization_id
    network_id = run.network_id
    if network_id is None:  # atomic import: the network exists only after this commit
        network_id = uuid.uuid4()
        conn.execute(sa.text(
            "INSERT INTO networks (id, organization_id, name, mode, timezone) "
            "VALUES (:id, :org, :name, :mode, :tz)"),
            {"id": network_id, "org": org, "name": network["name"], "mode": network["mode"],
             "tz": network["timezone"]})
    version_id = uuid.uuid4()
    files_hash = hashlib.sha256("".join(
        f"{f['name']}:{f['sha256']}\n" for f in sorted(files, key=lambda f: f["name"])
    ).encode()).hexdigest()
    conn.execute(sa.text(
        "INSERT INTO dataset_versions (id, organization_id, network_id, import_run_id, "
        "as_of_date, input_sha256) VALUES (:id, :org, :net, :run, :as_of, :sha)"),
        {"id": version_id, "org": org, "net": network_id, "run": run.id,
         "as_of": rows.as_of_date, "sha": files_hash})
    base = {"org": org, "ver": version_id}
    locations = {loc.location_id: uuid.uuid4() for loc in rows.locations}
    products = {p.product_id: uuid.uuid4() for p in rows.products}
    conn.execute(sa.text(
        "INSERT INTO net_locations (id, organization_id, dataset_version_id, external_id, name, "
        "role, street, city, state, zip, latitude, longitude, coordinates_source, "
        "receiving_capacity_per_day, manual_poverty_rate, manual_snap_rate) VALUES (:id, :org, "
        ":ver, :ext, :name, :role, :street, :city, :state, :zip, :lat, :lon, :src, :cap, "
        ":poverty, :snap)"),
        [{**base, "id": locations[r.location_id], "ext": r.location_id, "name": r.name,
          "role": r.role, "street": r.street, "city": r.city, "state": r.state, "zip": r.zip,
          "lat": r.latitude, "lon": r.longitude,
          "src": "user" if r.latitude is not None else None,
          "cap": r.receiving_capacity_per_day, "poverty": r.poverty_rate, "snap": r.snap_rate}
         for r in rows.locations])
    conn.execute(sa.text(
        "INSERT INTO net_products (id, organization_id, dataset_version_id, external_id, name, "
        "unit, unit_value_usd, handling_units_per_unit) VALUES (:id, :org, :ver, :ext, :name, "
        ":unit, :value, :handling)"),
        [{**base, "id": products[p.product_id], "ext": p.product_id, "name": p.name,
          "unit": p.unit, "value": p.unit_value_usd, "handling": p.handling_units_per_unit}
         for p in rows.products])
    cursor = conn.connection.driver_connection.cursor()
    with cursor.copy("COPY net_batches (id, organization_id, dataset_version_id, location_id, "
                     "product_id, external_id, quantity, expiry_date, non_expiring, "
                     "received_date) FROM STDIN") as copy:
        for b in rows.batches:
            copy.write_row((uuid.uuid4(), org, version_id, locations[b.location_id],
                            products[b.product_id], b.batch_id, b.quantity, b.expiry_date,
                            b.non_expiring, b.received_date))
    if rows.inbound:
        conn.execute(sa.text(
            "INSERT INTO net_inbound (id, organization_id, dataset_version_id, location_id, "
            "product_id, line_no, quantity, arrival_date, expiry_date, non_expiring, source, "
            "reference, within_horizon) VALUES (:id, :org, :ver, :loc, :prod, :line, :qty, "
            ":arrival, :expiry, :non_expiring, :source, :ref, :within)"),
            [{**base, "id": uuid.uuid4(), "loc": locations[r.location_id],
              "prod": products[r.product_id], "line": r.line, "qty": r.quantity,
              "arrival": r.arrival_date, "expiry": r.expiry_date,
              "non_expiring": r.non_expiring, "source": r.source, "ref": r.reference,
              "within": r.within_horizon} for r in rows.inbound])
    for name, table in HISTORY_TABLES.items():
        _load_history(conn, name, table, staging, org, version_id)
    conn.execute(sa.text(
        "INSERT INTO import_events (id, organization_id, dataset_version_id, import_run_id, "
        "actor, files) VALUES (:id, :org, :ver, :run, :actor, CAST(:files AS jsonb))"),
        {**base, "id": uuid.uuid4(), "run": run.id, "actor": actor, "files": json.dumps(files)})
    conn.execute(sa.text(
        "UPDATE import_runs SET network_id = :net, phase = 'done', updated_at = clock_timestamp() "
        "WHERE id = :id"), {"net": network_id, "id": run.id})
    return network_id, version_id


def _load_history(conn: sa.Connection, name: str, table: str, staging: str, org: UUID,
                  version_id: UUID) -> None:
    """S4 variant e4: a bare per-version table, bulk INSERT, keys, CHECK, then ATTACH."""
    part = f"{table}_{version_id.hex}"
    joins = ("JOIN net_locations l ON l.dataset_version_id = :ver AND l.external_id = s.c01 "
             "JOIN net_products p ON p.dataset_version_id = :ver AND p.external_id = s.c02")
    if name == "demand_history":
        select = (f"SELECT :org, :ver, l.id, p.id, CAST(s.c03 AS date), CAST(s.c04 AS bigint), "
                  f"s.c05 FROM {staging} s {joins} WHERE s.file = 'demand_history'")
        columns = f"{KEY_COLUMNS}, quantity, basis"
    else:  # summed per receiving location × product × day; donors in first-seen order
        select = (
            f"SELECT :org, :ver, l.id, p.id, CAST(k.c03 AS date), k.quantity, d.donors FROM "
            f"(SELECT c01, c02, c03, sum(CAST(c04 AS bigint)) AS quantity FROM {staging} "
            f"WHERE file = 'donation_history' GROUP BY c01, c02, c03) k "
            f"LEFT JOIN (SELECT c01, c02, c03, string_agg(c05, '; ' ORDER BY first) AS donors "
            f"FROM (SELECT c01, c02, c03, c05, min(line_no) AS first FROM {staging} "
            f"WHERE file = 'donation_history' AND c05 IS NOT NULL GROUP BY c01, c02, c03, c05) x "
            f"GROUP BY c01, c02, c03) d USING (c01, c02, c03) "
            f"JOIN net_locations l ON l.dataset_version_id = :ver AND l.external_id = k.c01 "
            f"JOIN net_products p ON p.dataset_version_id = :ver AND p.external_id = k.c02")
        columns = f"{KEY_COLUMNS}, quantity, donor"
    for statement in (
        f"CREATE TABLE {part} (LIKE {table} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)",
        f"INSERT INTO {part} ({columns}) {select}",
        f"ALTER TABLE {part} ADD PRIMARY KEY (dataset_version_id, location_id, product_id, day)",
        f"ALTER TABLE {part} ADD FOREIGN KEY (organization_id) REFERENCES organizations (id)",
        f"ALTER TABLE {part} ADD FOREIGN KEY (organization_id, dataset_version_id, location_id) "
        f"REFERENCES net_locations (organization_id, dataset_version_id, id)",
        f"ALTER TABLE {part} ADD FOREIGN KEY (organization_id, dataset_version_id, product_id) "
        f"REFERENCES net_products (organization_id, dataset_version_id, id)",
        f"ALTER TABLE {part} ADD CHECK (dataset_version_id = '{version_id}')",
        f"ALTER TABLE {table} ATTACH PARTITION {part} FOR VALUES IN ('{version_id}')",
    ):
        conn.execute(sa.text(statement), {"org": org, "ver": version_id})
