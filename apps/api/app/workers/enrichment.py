"""enrichment.v1 (Census, W1-D06) and routes-google.v1 (Google road distances, W1-D08).

enrichment.v1 keeps the CR-w1-data-2 split: the payload carries the addresses (read when the
job is submitted), the one `geocode` step calls Census without database access, and publish
writes ~100 location rows and the refreshed routes for that dataset version. A Census outage
is a completed step with an error, so the job publishes "fields unknown, retry" instead of
failing.

routes-google.v1 gets the user's key only in its step child's environment (child_secrets):
never in the payload, an output, an error or a log. Provider errors are safe codes."""

import os
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

import sqlalchemy as sa

from app.schemas.v1_envelope import V1_ENVELOPE
from app.services.enrichment.census import CensusClient, default_acs
from app.services.enrichment.google import (
    GoogleClient,
    GoogleUnavailable,
    apply_google,
    google_step,
    urlopen_transport,
)
from app.services.enrichment.service import apply_enrichment, geocode_step
from app.services.enrichment.settings import GOOGLE_KEY
from app.services.jobs.contracts import OperationKind, StepSpec, StepStatus
from app.services.jobs.registry import (
    InputRejected,
    PublicationRejected,
    Registration,
    secret_env,
)

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
FETCH = "fetch"
SAFE_ERROR = re.compile(r"GOOGLE_(HTTP_\d{3}|UNAVAILABLE|BAD_RESPONSE|KEY_MISSING)")


def _point(lat, lon) -> tuple[str, str]:
    """Coordinates as the canonical 6-decimal text the cache and net_locations use."""
    lat, lon = Decimal(str(lat)), Decimal(str(lon))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError
    q = Decimal("0.000001")
    return str(lat.quantize(q)), str(lon.quantize(q))


class GoogleHandler:
    def __init__(self, transport=None):
        self.transport = transport

    def validate_input(self, payload):
        try:
            if set(payload) != {"dataset_version_id", "lookups"}:
                raise ValueError
            version = str(UUID(payload["dataset_version_id"]))
            lookups = [[*_point(dlat, dlon), [list(_point(*o)) for o in origins]]
                       for dlat, dlon, origins in payload["lookups"]]
            if len(lookups) > V1_ENVELOPE.max_locations or any(
                    not 1 <= len(o) < V1_ENVELOPE.max_locations for _, _, o in lookups):
                raise ValueError
        except (TypeError, ValueError, AttributeError, InvalidOperation):
            raise InputRejected("INVALID_GOOGLE_JOB", "routes-google.v1 needs "
                                "dataset_version_id and per-receiver lookups") from None
        return {"dataset_version_id": version, "lookups": lookups}

    def steps(self, validated, profile):
        return (StepSpec(name=FETCH, min_s=profile.method_min_s),)

    def execute_step(self, step, validated, prior, context):
        try:
            client = GoogleClient(os.environ.get(secret_env(GOOGLE_KEY), ""),
                                  self.transport or urlopen_transport)
        except GoogleUnavailable as error:
            return {"results": [], "error": error.code}
        return google_step(validated, client)


class GooglePublisher:
    def validate(self, validated, outcomes):
        done = [o for o in outcomes if o.name == FETCH and o.status == StepStatus.COMPLETED]
        if not done:
            last = outcomes[-1] if outcomes else None
            raise PublicationRejected("GOOGLE_STEP_FAILED",
                                      timed_out=bool(last and last.status == StepStatus.TIMED_OUT))
        output = dict(done[-1].output or {})
        asked = {(*o, d[0], d[1]) for d in validated["lookups"] for o in d[2]}
        try:
            results = [[*_point(r[0], r[1]), *_point(r[2], r[3]), int(r[4]), int(r[5])]
                       for r in output["results"]]
            if set(output) != {"results", "error"} or any(
                    tuple(r[:4]) not in asked or r[4] < 0 or r[5] < 0 for r in results) or not (
                    output["error"] is None or SAFE_ERROR.fullmatch(output["error"])):
                raise ValueError
        except (TypeError, KeyError, ValueError, IndexError, InvalidOperation):
            raise PublicationRejected("OUTPUT_INVALID") from None
        return {"dataset_version_id": validated["dataset_version_id"],
                "step": {"results": results, "error": output["error"]}}

    def publish(self, connection, identity, package):
        """Inside the queue's publication transaction: at most ~1,000 small rows."""
        version_id = UUID(package["dataset_version_id"])
        owner = connection.scalar(sa.text(
            "SELECT organization_id FROM dataset_versions WHERE id = :v"), {"v": version_id})
        if owner != identity.organization_id:
            raise PublicationRejected("DATASET_VERSION_NOT_FOUND")
        apply_google(connection, version_id, package["step"], datetime.now(UTC))
        return {"fetched": len(package["step"]["results"]), "error": package["step"]["error"]}


GOOGLE_REGISTRATION = Registration(
    contract="routes-google.v1",
    operation_kind=OperationKind.ENRICHMENT,
    input_schema_version="1",
    max_input_bytes=300_000,  # the handler's maximum, 100 × 99 pairs, encodes to 290,340
    max_output_bytes=4_000_000,
    handler=GoogleHandler(),
    publisher=GooglePublisher(),
    child_secrets=(GOOGLE_KEY,),
)
