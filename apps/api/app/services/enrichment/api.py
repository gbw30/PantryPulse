"""Enrichment status, retry, manual attributes, EGP blockers (W1-D06) and routes (W1-D07).

The local session may use every network of the install (W0-network-model §2): each call
checks the network it names exists, and jobs run under the network's own organization."""

from uuid import UUID

import sqlalchemy as sa

from app.repositories import enrichment as repo
from app.repositories import networks as networks_repo
from app.repositories.jobs import TrustedScope
from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_enrichment import (
    EgpBlocker,
    EnrichmentStatus,
    LocationAttributes,
    LocationAttributesUpdate,
    RouteEntry,
    RouteList,
    UnmatchedAddress,
)
from app.services.enrichment import service
from app.services.enrichment.distance import DB_TO_API
from app.services.jobs.contracts import TERMINAL_STATES, AttemptState
from app.services.presenter_access import AccessError

CONTRACT = "enrichment.v1"


def enrichment_status(rt, scope, network_id: UUID) -> EnrichmentStatus:
    """Attributes and EGP blockers from the latest version, plus its latest enrichment job.
    The job's published manifest holds the unmatched addresses and any Census outage."""
    with rt.engine.connect() as conn:
        version_id = _latest_version(conn, network_id)
        org, job_id = _latest_job(conn, network_id, version_id)
        locations = service.location_attributes(conn, version_id)
        found = service.blockers(conn, version_id)
    state, last_error, unmatched = "not_started", None, []
    if job_id is not None:
        job = rt.queue.get_job(TrustedScope(org, "status"), job_id)
        if job.state not in TERMINAL_STATES:
            state = "running"
        elif job.state == AttemptState.SUCCEEDED:
            [attempt] = [a for a in job.attempts if a.attempt_id == job.current_attempt_id]
            manifest = attempt.result_manifest or {}
            unmatched, last_error = manifest.get("unmatched", []), manifest.get("last_error")
            state = "failed" if last_error else "done"
        else:
            state = "failed"
            last_error = (f"The enrichment job ended {job.state.value.lower().replace('_', ' ')} "
                          "before saving anything. Retry it.")
    return EnrichmentStatus(
        network_id=network_id, dataset_version_id=version_id, state=state, job_id=job_id,
        last_error=last_error, locations=tuple(locations),
        unmatched=tuple(UnmatchedAddress(**u) for u in unmatched),
        egp_blockers=tuple(EgpBlocker(location_id=i, missing=m) for i, m in found))


def retry_enrichment(rt, scope, network_id: UUID, idempotency_key: str) -> ForecastAccepted:
    """Run enrichment.v1 for the latest version: geocode what is still unlocated and fill the
    rates still unknown. One job per version at a time."""
    with rt.engine.connect() as conn:
        version_id = _latest_version(conn, network_id)
        org, job_id = _latest_job(conn, network_id, version_id)
        payload = service.enrichment_input(conn, version_id)
    if job_id is not None and rt.queue.get_job(
            TrustedScope(org, "status"), job_id).state not in TERMINAL_STATES:
        raise AccessError("ENRICHMENT_IN_PROGRESS", 409)
    accepted = rt.queue.submit(TrustedScope(org, scope.actor_ref), CONTRACT, payload,
                               idempotency_key)
    url = f"/api/v1/networks/{network_id}/enrichment"
    return ForecastAccepted(job_id=accepted.job_id, attempt_id=accepted.attempt_id,
                            state=accepted.state, replayed=accepted.replayed, status_url=url,
                            result_url=url)


def _latest_job(conn: sa.Connection, network_id: UUID, version_id: UUID):
    org = conn.scalar(sa.text("SELECT organization_id FROM networks WHERE id = :n"),
                      {"n": network_id})
    job_id = conn.scalar(sa.text(
        "SELECT job_id FROM compute_jobs WHERE organization_id = :org AND handler_contract = "
        ":contract AND input_package -> 'input' ->> 'dataset_version_id' = :v "
        "ORDER BY created_at DESC, job_id LIMIT 1"),
        {"org": org, "contract": CONTRACT, "v": str(version_id)})
    return org, job_id


def set_location_attributes(
    rt, scope, network_id: UUID, location_id: str, update: LocationAttributesUpdate
) -> LocationAttributes:
    """A manual value for both rates, or an explicit exclusion from EGP, on the latest version.
    Looked-up values stay in their own columns, so the source of each stays visible."""
    with rt.engine.begin() as conn:
        version_id = _latest_version(conn, network_id)
        values = ({"poverty": None, "snap": None, "excluded": True,
                   "reason": "excluded from EGP by the user"} if update.excluded else
                  {"poverty": update.poverty_rate, "snap": update.snap_rate, "excluded": False,
                   "reason": None})
        changed = conn.execute(sa.text(
            "UPDATE net_locations SET manual_poverty_rate = coalesce(:poverty, "
            "manual_poverty_rate), manual_snap_rate = coalesce(:snap, manual_snap_rate), "
            "excluded = :excluded, exclusion_reason = :reason "
            "WHERE dataset_version_id = :v AND external_id = :e"),
            {**values, "v": version_id, "e": location_id}).rowcount
        if not changed:
            raise AccessError("LOCATION_NOT_FOUND", 404)
        [attributes] = service.location_attributes(conn, version_id, location_id)
    return attributes


def egp_blockers(rt, network_id: UUID, dataset_version_id: UUID) -> list[EgpBlocker]:
    with rt.engine.connect() as conn:
        if not conn.scalar(sa.text("SELECT 1 FROM dataset_versions WHERE id = :v AND "
                                   "network_id = :n"), {"v": dataset_version_id, "n": network_id}):
            raise AccessError("DATASET_VERSION_NOT_FOUND", 404)
        found = service.blockers(conn, dataset_version_id)
    return [EgpBlocker(location_id=location_id, missing=missing) for location_id, missing in found]


def _latest_version(conn: sa.Connection, network_id: UUID) -> UUID:
    found = networks_repo.networks(conn, network_id)
    if not found:
        raise AccessError("NETWORK_NOT_FOUND", 404)
    return found[0].dataset_version_id


def list_routes(rt, scope, network_id: UUID) -> RouteList:
    """The latest dataset version's routes, with the API method label."""
    with rt.engine.connect() as conn:
        version_id = _latest_version(conn, network_id)
        rows = repo.routes(conn, version_id)
    return RouteList(network_id=network_id, dataset_version_id=version_id, routes=tuple(
        RouteEntry(**{**r._mapping, "method": DB_TO_API[r.method]}) for r in rows))
