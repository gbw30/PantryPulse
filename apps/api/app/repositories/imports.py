"""Import runs: creation, uploaded-file records, phase/progress and the error report (W1-D04)."""

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from app.schemas.v1_imports import NewNetwork, OutsideHorizonInbound, RowError
from app.services.presenter_access import AccessError


@dataclass(frozen=True, slots=True)
class Run:
    id: UUID
    organization_id: UUID
    network_id: UUID | None
    new_network: dict[str, Any] | None  # {name, mode, timezone} until a first import succeeds
    job_id: UUID | None
    phase: str
    files: list[dict[str, Any]]
    progress: dict[str, Any]
    error_count: int
    errors_truncated: bool


_COLUMNS = ("id, organization_id, network_id, new_network, job_id, phase, files, progress, "
            "error_count, errors_truncated")


def create_run(conn: sa.Connection, network: NewNetwork | None, network_id: UUID | None) -> Run:
    """A new network gets its own organization now; its networks row waits for the commit."""
    if network is not None:
        organization_id = uuid.uuid4()
        conn.execute(sa.text("INSERT INTO organizations (id, name, is_demo) "
                             "VALUES (:id, :name, false)"),
                     {"id": organization_id, "name": network.name})
        new_network = json.dumps(network.model_dump(mode="json"))
    else:
        organization_id = conn.scalar(sa.text(
            "SELECT organization_id FROM networks WHERE id = :id"), {"id": network_id})
        if organization_id is None:
            raise AccessError("NETWORK_NOT_FOUND", 404)
        new_network = None
    run_id = uuid.uuid4()
    conn.execute(sa.text(
        "INSERT INTO import_runs (id, organization_id, network_id, new_network, phase) "
        "VALUES (:id, :org, :net, CAST(:new AS jsonb), 'uploading')"),
        {"id": run_id, "org": organization_id, "net": network_id, "new": new_network})
    return get_run(conn, run_id)


def get_run(conn: sa.Connection, run_id: UUID, *, lock: bool = False) -> Run:
    row = conn.execute(sa.text(
        f"SELECT {_COLUMNS} FROM import_runs WHERE id = :id" + (" FOR UPDATE" if lock else "")),
        {"id": run_id}).one_or_none()
    if row is None:
        raise AccessError("IMPORT_NOT_FOUND", 404)
    return Run(*row)


def record_file(conn: sa.Connection, run_id: UUID, name: str, size: int, sha256: str) -> None:
    """Add or replace the entry for `name` (re-posting a file replaces it)."""
    conn.execute(sa.text(
        "UPDATE import_runs SET files = COALESCE((SELECT jsonb_agg(f) FROM jsonb_array_elements("
        "files) f WHERE f->>'name' <> :name), '[]'::jsonb) || jsonb_build_array(jsonb_build_object("
        "'name', CAST(:name AS text), 'bytes', CAST(:size AS bigint), "
        "'sha256', CAST(:sha AS text))), updated_at = clock_timestamp() WHERE id = :id"),
        {"id": run_id, "name": name, "size": size, "sha": sha256})


def set_phase(conn: sa.Connection, run_id: UUID, phase: str, *, job_id: UUID | None = None,
              progress: dict[str, Any] | None = None) -> None:
    conn.execute(sa.text(
        "UPDATE import_runs SET phase = :phase, job_id = COALESCE(:job, job_id), "
        "progress = COALESCE(CAST(:progress AS jsonb), progress), updated_at = clock_timestamp() "
        "WHERE id = :id"),
        {"id": run_id, "phase": phase, "job": job_id,
         "progress": None if progress is None else json.dumps(progress)})


def set_progress(conn: sa.Connection, run_id: UUID, unit: str, done: int,
                 total: int | None) -> None:
    conn.execute(sa.text(
        "UPDATE import_runs SET progress = CAST(:p AS jsonb), updated_at = clock_timestamp() "
        "WHERE id = :id"),
        {"id": run_id, "p": json.dumps({"unit": unit, "done": done, "total": total})})


def fail_run(conn: sa.Connection, run: Run, errors: Sequence[RowError], error_count: int) -> None:
    """Keep the report (first errors, with their fix) and mark the run failed; nothing else."""
    if errors:
        conn.execute(sa.text(
            "INSERT INTO import_errors (id, organization_id, import_run_id, file, line_no, "
            "column_name, code, reason, fix, value) VALUES (:id, :org, :run, :file, :line, "
            ":column, :code, :reason, :fix, :value)"),
            [{"id": uuid.uuid4(), "org": run.organization_id, "run": run.id, "file": e.file,
              "line": e.line, "column": e.column, "code": e.code, "reason": e.reason,
              "fix": e.fix, "value": e.value} for e in errors])
    conn.execute(sa.text(
        "UPDATE import_runs SET phase = 'failed', error_count = :count, "
        "errors_truncated = :truncated, updated_at = clock_timestamp() WHERE id = :id"),
        {"id": run.id, "count": error_count, "truncated": error_count > len(errors)})


def stored_errors(conn: sa.Connection, run_id: UUID) -> list[RowError]:
    rows = conn.execute(sa.text(
        "SELECT file, line_no, column_name, code, reason, fix, value FROM import_errors "
        "WHERE import_run_id = :id ORDER BY file, line_no, id"), {"id": run_id}).all()
    return [RowError(file=r.file, line=r.line_no, column=r.column_name, code=r.code,
                     reason=r.reason, fix=r.fix, value=r.value) for r in rows]


def outside_horizon(conn: sa.Connection, version_id: UUID) -> list[OutsideHorizonInbound]:
    """Inbound rows arriving after the seven-day horizon: kept, not counted, listed."""
    rows = conn.execute(sa.text(
        "SELECT i.line_no, l.external_id, p.external_id, i.quantity, i.arrival_date "
        "FROM net_inbound i JOIN net_locations l ON l.id = i.location_id "
        "JOIN net_products p ON p.id = i.product_id "
        "WHERE i.dataset_version_id = :v AND NOT i.within_horizon ORDER BY i.line_no"),
        {"v": version_id}).all()
    return [OutsideHorizonInbound(line=r[0], location_id=r[1], product_id=r[2], quantity=r[3],
                                  arrival_date=r[4]) for r in rows]
