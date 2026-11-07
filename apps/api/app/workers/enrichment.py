"""enrichment.v1 (Census, W1-D06) and routes-google.v1 (Google road distances, W1-D08)."""

from app.services.jobs.contracts import OperationKind
from app.services.jobs.registry import Registration
from app.workers.v1_stub import NotBuiltHandler, NotBuiltPublisher

ENRICHMENT_REGISTRATION = Registration(
    contract="enrichment.v1",
    operation_kind=OperationKind.ENRICHMENT,
    input_schema_version="1",
    max_input_bytes=64_000,
    max_output_bytes=4_000_000,
    handler=NotBuiltHandler("W1-D06"),
    publisher=NotBuiltPublisher("W1-D06"),
)
GOOGLE_REGISTRATION = Registration(
    contract="routes-google.v1",
    operation_kind=OperationKind.ENRICHMENT,
    input_schema_version="1",
    max_input_bytes=64_000,
    max_output_bytes=4_000_000,
    handler=NotBuiltHandler("W1-D08"),
    publisher=NotBuiltPublisher("W1-D08"),
)
