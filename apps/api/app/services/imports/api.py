"""Import lifecycle: create, store each file, commit as import.v1, status (W1-D04/D05).

The local session may use every import and network of the install (W0-network-model §2):
each call checks the run or network it names exists, and jobs run under the network's own
organization, never one sent by the client.
"""

from collections.abc import AsyncIterator
from uuid import UUID

import sqlalchemy as sa

from app.repositories import imports as repo
from app.repositories.jobs import TrustedScope
from app.schemas.v1_imports import (
    ImportAccepted,
    ImportCommit,
    ImportCreate,
    ImportCreated,
    ImportFailure,
    ImportFile,
    ImportProgress,
    ImportStatus,
    RowError,
)
from app.schemas.v1_networks import REQUIRED_TEMPLATES, TemplateName
from app.services.imports import staging
from app.services.jobs.contracts import AttemptState
from app.services.jobs.registry import InputRejected
from app.services.presenter_access import AccessError

CONTRACT = "import.v1"
RUNNING_PHASES = ("staging", "validating", "committing")
FAILED_JOBS = frozenset({AttemptState.FAILED, AttemptState.TIMED_OUT, AttemptState.INTERRUPTED,
                         AttemptState.CANCELLED, AttemptState.EXPIRED})
FAILED_MESSAGE = "Import failed — nothing was saved."


def create_import(rt, scope, request: ImportCreate) -> ImportCreated:
    with rt.engine.begin() as conn:
        run = repo.create_run(conn, request.network, request.network_id)
    return ImportCreated(import_id=run.id, network_id=run.network_id)


async def store_import_file(
    rt, scope, import_id: UUID, name: TemplateName, chunks: AsyncIterator[bytes]
) -> ImportFile:
    """`chunks` is already capped at UPLOAD_CAP_BYTES by the router (InputRejected → 413).
    An over-cap or broken upload leaves no file (W1-D04)."""
    with rt.engine.connect() as conn:
        _uploading(repo.get_run(conn, import_id))
    size, sha256 = await staging.write_upload(staging.import_dir(), import_id, name, chunks)
    with rt.engine.begin() as conn:
        _uploading(repo.get_run(conn, import_id, lock=True))
        repo.record_file(conn, import_id, name, size, sha256)
    return ImportFile(name=name, bytes=size, sha256=sha256)


def _uploading(run: repo.Run) -> None:
    if run.phase != "uploading" or run.job_id is not None:
        raise AccessError("IMPORT_NOT_UPLOADING", 409)


def commit_import(
    rt, scope, import_id: UUID, request: ImportCommit, idempotency_key: str
) -> ImportAccepted:
    status_url = f"/api/v1/imports/{import_id}"
    with rt.engine.begin() as conn:
        run = repo.get_run(conn, import_id, lock=True)
        if run.job_id is not None:
            if not _ended(rt, run.organization_id, run.job_id):
                # one job while it runs or once it has run: the same job, never a second one
                return ImportAccepted(import_id=import_id, job_id=run.job_id,
                                      status_url=status_url)
            # it stopped before committing and the files are kept: commit again with a new job
        elif run.phase != "uploading":
            raise AccessError("IMPORT_NOT_UPLOADING", 409)
        present = {f["name"] for f in run.files}
        missing = [name for name in REQUIRED_TEMPLATES if name not in present]
        if missing:
            error = InputRejected("MISSING_FILES",
                                  f"required files are missing: {', '.join(missing)}")
            error.details = {"missing": missing}
            raise error
        if run.network_id is not None:
            # The network row lock serializes concurrent commits for one network.
            conn.execute(sa.text("SELECT 1 FROM networks WHERE id = :n FOR UPDATE"),
                         {"n": run.network_id})
            running = conn.execute(sa.text(
                "SELECT organization_id, job_id FROM import_runs WHERE network_id = :n AND "
                "id <> :id AND job_id IS NOT NULL AND "
                "phase IN ('staging', 'validating', 'committing')"),
                {"n": run.network_id, "id": import_id}).all()
            if not all(_ended(rt, org, job_id) for org, job_id in running):
                raise AccessError("IMPORT_IN_PROGRESS", 409)
        accepted = rt.queue.submit(
            TrustedScope(run.organization_id, scope.actor_ref), CONTRACT,
            staging.job_input(conn, run, request.as_of_date, staging.import_dir(),
                              scope.actor_ref),
            idempotency_key)
        repo.set_phase(conn, import_id, "staging", job_id=accepted.job_id,
                       progress={"unit": "rows", "done": 0, "total": None})
    return ImportAccepted(import_id=import_id, job_id=accepted.job_id, status_url=status_url)


def _ended(rt, organization_id: UUID, job_id: UUID) -> bool:
    """The job stopped without committing (the run's stored phase still reads running)."""
    return rt.queue.get_job(TrustedScope(organization_id, "status"), job_id).state in FAILED_JOBS


def import_status(rt, scope, import_id: UUID) -> ImportStatus:
    with rt.engine.connect() as conn:
        run = repo.get_run(conn, import_id)
        errors = repo.stored_errors(conn, import_id)
        version = conn.execute(sa.text(
            "SELECT id, as_of_date FROM dataset_versions WHERE import_run_id = :r"),
            {"r": import_id}).one_or_none()
        outside = [] if version is None else repo.outside_horizon(conn, version.id)
    phase = run.phase
    if phase in ("uploading", *RUNNING_PHASES) and run.job_id is not None:
        job = rt.queue.get_job(TrustedScope(run.organization_id, "status"), run.job_id)
        if job.state in FAILED_JOBS:
            phase = "failed"  # the job ended without a commit, so nothing was saved
    progress = run.progress if run.progress.get("unit") else None
    return ImportStatus(
        import_id=run.id,
        network_id=run.network_id,  # None for a new network until its commit
        job_id=run.job_id,
        phase=phase,
        files=tuple(ImportFile(**f) for f in run.files),
        progress=None if progress is None else ImportProgress(**progress),
        error_count=run.error_count,
        errors_truncated=run.errors_truncated,
        errors=tuple(errors),
        outside_horizon_inbound=tuple(outside),
        dataset_version_id=None if version is None else version.id,
        as_of_date=None if version is None else version.as_of_date,
        failure=_failure(errors, run.error_count, run.errors_truncated) if phase == "failed"
        else None,
    )


def _plural(count: int, word: str) -> str:
    return f"{count:,} {word}{'' if count == 1 else 's'}"


def _failure(errors: list[RowError], count: int, truncated: bool) -> ImportFailure:
    if not errors:
        return ImportFailure(
            kind="JOB_FAILED", message=FAILED_MESSAGE,
            reason="The import job stopped before it finished.",
            next_steps=("Commit the import again; the uploaded files are kept.",
                        "If it stops again, check the files are UTF-8 CSV within the size "
                        "limits shown in the template guide."))
    files = {e.file for e in errors}
    if all(e.line == 1 and e.column is None and "is required and is missing" in e.reason
           for e in errors):
        return ImportFailure(
            kind="MISSING_FILES", message=FAILED_MESSAGE,
            reason=f"{_plural(len(files), 'required file')} missing: "
                   f"{', '.join(sorted(files))}",
            next_steps=("Upload every required file: locations, products, inventory and "
                        "demand_history.",))
    rows = len({(e.file, e.line) for e in errors})
    reason = (f"more than {rows:,} rows in {_plural(len(files), 'file')} have errors "
              f"({count:,} errors; the first {len(errors):,} are listed)" if truncated else
              f"{_plural(rows, 'row')} in {_plural(len(files), 'file')} "
              f"{'has' if rows == 1 else 'have'} errors")
    kind = "OVER_ENVELOPE" if all(e.code == "OVER_ENVELOPE" for e in errors) else "ROW_ERRORS"
    steps = ("Change each listed row as its fix says, then upload the corrected files and "
             "import again.",)
    if kind == "OVER_ENVELOPE":
        steps = ("Reduce the data to the listed limits (100 locations, 500 products, 90 days "
                 "of history, 200,000 batches), then import again.",)
    return ImportFailure(kind=kind, message=FAILED_MESSAGE, reason=reason, next_steps=steps)
