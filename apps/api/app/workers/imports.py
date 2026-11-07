"""import.v1: stage, validate and commit one network dataset version (W1-D05 builds it)."""

from app.services.jobs.contracts import OperationKind
from app.services.jobs.registry import Registration
from app.workers.v1_stub import NotBuiltHandler, NotBuiltPublisher

REGISTRATION = Registration(
    contract="import.v1",
    operation_kind=OperationKind.IMPORT,
    input_schema_version="1",
    max_input_bytes=64_000,
    max_output_bytes=1_000_000,
    handler=NotBuiltHandler("W1-D05"),
    publisher=NotBuiltPublisher("W1-D05"),
)
