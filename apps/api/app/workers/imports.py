"""import.v1: stage, validate and commit one network dataset version (W1-D05).

Admission works now: the payload is validated and the job is durably queued. Execution is
blocked by CR-w1-data-2 (a step child has no database access, and `publish` holds the queue's
control lock), so the handler is never advertised for execution and no supervisor claims it.
"""

from datetime import date
from uuid import UUID

from app.services.jobs.contracts import OperationKind
from app.services.jobs.registry import InputRejected, Registration
from app.services.v1_errors import NotImplementedV1
from app.workers.v1_stub import NotBuiltPublisher


class ImportHandler:
    def validate_input(self, payload):
        try:
            if set(payload) != {"import_id", "as_of_date"}:
                raise ValueError
            import_id = str(UUID(payload["import_id"]))
            as_of = payload["as_of_date"]
            as_of = None if as_of is None else date.fromisoformat(as_of).isoformat()
        except (TypeError, ValueError, AttributeError):
            raise InputRejected("INVALID_IMPORT_JOB", "import.v1 needs import_id and "
                                "as_of_date") from None
        return {"import_id": import_id, "as_of_date": as_of}

    def steps(self, validated, profile):
        raise NotImplementedV1("W1-D05")

    def execute_step(self, step, validated, prior, context):
        raise NotImplementedV1("W1-D05")

    @staticmethod
    def execution_capability():
        return None  # not advertised until CR-w1-data-2 settles where the job may use the DB


REGISTRATION = Registration(
    contract="import.v1",
    operation_kind=OperationKind.IMPORT,
    input_schema_version="1",
    max_input_bytes=64_000,
    max_output_bytes=1_000_000,
    handler=ImportHandler(),
    publisher=NotBuiltPublisher("W1-D05"),
)
