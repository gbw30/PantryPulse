"""enrichment.v1 (Census, W1-D06) and routes-google.v1 (Google road distances, W1-D08).

enrichment.v1 keeps the CR-w1-data-2 split: the payload carries the addresses (read when the
job is submitted), the one `geocode` step calls Census without database access, and publish
writes ~100 location rows and the refreshed routes for that dataset version. A Census outage
is a completed step with an error, so the job publishes "fields unknown, retry" instead of
failing."""

from uuid import UUID

import sqlalchemy as sa

from app.schemas.v1_envelope import V1_ENVELOPE
from app.services.enrichment.census import CensusClient, default_acs
from app.services.enrichment.service import apply_enrichment, geocode_step
from app.services.jobs.contracts import OperationKind, StepSpec, StepStatus
from app.services.jobs.registry import InputRejected, PublicationRejected, Registration
from app.workers.v1_stub import NotBuiltHandler, NotBuiltPublisher

CONTRACT = "enrichment.v1"
GEOCODE = "geocode"
FIELD_MAX = 500


class EnrichmentHandler:
    def __init__(self, client: CensusClient | None = None):
        self.client = client

    def validate_input(self, payload):
        try:
            if set(payload) != {"dataset_version_id", "addresses"}:
                raise ValueError
            version = str(UUID(payload["dataset_version_id"]))
            addresses = [[str(v) for v in a] for a in payload["addresses"]]
            if len(addresses) > V1_ENVELOPE.max_locations or any(
                    len(a) != 5 or any(len(v) > FIELD_MAX for v in a) for a in addresses):
                raise ValueError
        except (TypeError, ValueError, AttributeError):
            raise InputRejected("INVALID_ENRICHMENT_JOB", "enrichment.v1 needs "
                                "dataset_version_id and at most 100 addresses") from None
        return {"dataset_version_id": version, "addresses": addresses}

    def steps(self, validated, profile):
        return (StepSpec(name=GEOCODE, min_s=profile.method_min_s),)

    def execute_step(self, step, validated, prior, context):
        return geocode_step(validated, self.client or CensusClient())


class EnrichmentPublisher:
    def __init__(self, acs=default_acs):
        self.acs = acs

    def validate(self, validated, outcomes):
        done = [o for o in outcomes if o.name == GEOCODE and o.status == StepStatus.COMPLETED]
        if not done:
            last = outcomes[-1] if outcomes else None
            raise PublicationRejected("GEOCODE_STEP_FAILED",
                                      timed_out=bool(last and last.status == StepStatus.TIMED_OUT))
        output = dict(done[-1].output or {})
        sent = {a[0] for a in validated["addresses"]}
        try:
            if set(output) != {"geocodes", "error"} or not all(
                    g["location_id"] in sent for g in output["geocodes"]):
                raise ValueError
        except (TypeError, KeyError, ValueError):
            raise PublicationRejected("OUTPUT_INVALID") from None
        return {"dataset_version_id": validated["dataset_version_id"], "step": output}

    def publish(self, connection, identity, package):
        """Inside the queue's publication transaction: small row writes only."""
        version_id = UUID(package["dataset_version_id"])
        owner = connection.scalar(sa.text(
            "SELECT organization_id FROM dataset_versions WHERE id = :v"), {"v": version_id})
        if owner != identity.organization_id:
            raise PublicationRejected("DATASET_VERSION_NOT_FOUND")
        return apply_enrichment(connection, version_id, package["step"], self.acs())


ENRICHMENT_REGISTRATION = Registration(
    contract=CONTRACT,
    operation_kind=OperationKind.ENRICHMENT,
    input_schema_version="1",
    max_input_bytes=64_000,
    max_output_bytes=4_000_000,
    handler=EnrichmentHandler(),
    publisher=EnrichmentPublisher(),
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
