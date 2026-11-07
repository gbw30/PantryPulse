"""import.v1: validate, stage and commit one network dataset version (W1-D05, CR-w1-data-2).

The one `validate` step has no database access: it reads the uploaded CSVs from the imports
volume, runs the Validator and writes COPY-ready files next to them. `prepare` bulk-loads those
into tables named by the attempt, outside the queue lock; `publish`, inside it, writes the error
report, or moves the rows in and attaches the history partitions. `discard` drops the attempt's
tables, and `prepare` clears whatever a crashed attempt left (app/services/imports/staging.py).
Row errors are a result, not a crash: the job succeeds and the import reads `failed`.
"""

from datetime import date
from pathlib import Path
from typing import get_args
from uuid import UUID
from zoneinfo import ZoneInfo

from app.schemas.v1_imports import ImportSettings, RowError
from app.schemas.v1_networks import TemplateName
from app.services.imports.staging import (
    drop_staged,
    load_staged,
    publish_staged,
    write_load_files,
)
from app.services.jobs.contracts import OperationKind, StepSpec, StepStatus
from app.services.jobs.registry import InputRejected, PublicationRejected, Registration

VALIDATE = "validate"
KEYS = {"import_id", "organization_id", "as_of_date", "mode", "timezone", "files",
        "import_dir", "actor"}
OUTPUT_KEYS = {"ok", "error_count", "errors", "rows", "as_of_date", "dataset_version_id"}
TEMPLATES = frozenset(get_args(TemplateName))


class ImportHandler:
    def validate_input(self, payload):
        try:
            if set(payload) != KEYS:
                raise ValueError
            files = sorted(set(payload["files"]))
            folder, actor, as_of = payload["import_dir"], payload["actor"], payload["as_of_date"]
            if not set(files) <= TEMPLATES or not Path(folder).is_absolute() or not (
                    isinstance(actor, str) and 0 < len(actor) <= 200):
                raise ValueError
            as_of = None if as_of is None else date.fromisoformat(as_of)
            settings = ImportSettings(mode=payload["mode"],
                                      timezone=str(ZoneInfo(payload["timezone"])), as_of_date=as_of)
            validated = {
                "import_id": str(UUID(payload["import_id"])),
                "organization_id": str(UUID(payload["organization_id"])),
                "as_of_date": as_of and as_of.isoformat(),
                "mode": settings.mode, "timezone": settings.timezone, "files": files,
                "import_dir": folder, "actor": actor}
        except (TypeError, ValueError, AttributeError, KeyError):  # ZoneInfoNotFound is a KeyError
            raise InputRejected("INVALID_IMPORT_JOB", "import.v1 needs the import, its "
                                "organization, settings, files and imports folder") from None
        return validated

    def steps(self, validated, profile):
        return (StepSpec(name=VALIDATE, min_s=profile.method_min_s),)

    def execute_step(self, step, validated, prior, context):
        return write_load_files(validated, context.attempt_id)


class ImportPublisher:
    def validate(self, validated, outcomes):
        done = [o for o in outcomes if o.name == VALIDATE and o.status == StepStatus.COMPLETED]
        if not done:
            last = outcomes[-1] if outcomes else None
            raise PublicationRejected("IMPORT_STEP_FAILED",
                                      timed_out=bool(last and last.status == StepStatus.TIMED_OUT))
        output = dict(done[-1].output or {})
        try:
            if set(output) != OUTPUT_KEYS:
                raise ValueError
            ok, count, rows = output["ok"], output["error_count"], output["rows"]
            errors = [RowError.model_validate(e).model_dump(mode="json") for e in output["errors"]]
            if not (isinstance(ok, bool) and type(count) is int and type(rows) is int
                    and rows >= 0 and (count == 0 if ok else count >= max(1, len(errors)))):
                raise ValueError
            version = str(UUID(output["dataset_version_id"])) if ok else None
            as_of = date.fromisoformat(output["as_of_date"]).isoformat() if ok else None
        except (TypeError, KeyError, ValueError, AttributeError):
            raise PublicationRejected("OUTPUT_INVALID") from None
        return {"job": dict(validated), "step": {
            "ok": ok, "error_count": count, "errors": errors, "rows": rows, "as_of_date": as_of,
            "dataset_version_id": version}}

    def prepare(self, engine, identity, package, *, remaining_s):
        """Outside the queue lock: bulk-load this attempt's files into its staged tables."""
        if package["job"]["organization_id"] != str(identity.organization_id):
            raise PublicationRejected("IMPORT_NOT_FOUND")
        load_staged(engine, identity.attempt_id, package["job"], package["step"],
                    timeout_s=remaining_s)
        return package

    def publish(self, connection, identity, package):
        """Inside the queue lock: the small inserts, the history FKs and ATTACH."""
        return publish_staged(connection, identity.organization_id, identity.attempt_id,
                              package["job"], package["step"])

    def discard(self, engine, identity):
        drop_staged(engine, identity.attempt_id)


REGISTRATION = Registration(
    contract="import.v1",
    operation_kind=OperationKind.IMPORT,
    input_schema_version="1",
    max_input_bytes=64_000,
    max_output_bytes=1_000_000,
    handler=ImportHandler(),
    publisher=ImportPublisher(),
)
