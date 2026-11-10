# covers: V1-A10
"""enrichment.v1 end to end on PostgreSQL (W1-D06): retry submits the job, a real supervisor
runs it (FakeDriver boundary, recorded Census answers), status reads the published result."""

import dataclasses
import time
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command

import tests.integration.fake_driver as fake_driver
from app.repositories.jobs import QueueRepository, TrustedScope, create_queue_engine
from app.services.enrichment.api import enrichment_status, retry_enrichment
from app.services.enrichment.census import CensusClient
from app.services.jobs.contracts import AttemptState, RuntimeProfile
from app.services.jobs.registry import (
    InputRejected,
    PublicationIdentity,
    PublicationRejected,
    Registry,
)
from app.services.presenter_access import AccessError
from app.workers.enrichment import (
    ENRICHMENT_REGISTRATION,
    EnrichmentHandler,
    EnrichmentPublisher,
)
from app.workers.supervisor import Supervisor, SupervisorConfig
from tests.enrichment.test_enrichment_postgres import LOCATIONS, Census, acs  # noqa: F401
from tests.imports.test_import_postgres import FILES, _import
from tests.integration.wq_support import alembic_config, database_url, reset_schema

pytestmark = pytest.mark.integration
SCHEMA = "w1_data_enrich_job_test"
SCOPE = TrustedScope(uuid.UUID(int=1), "local")
PROFILE = RuntimeProfile(
    queue_wait_s=30, heartbeat_interval_s=0.2, heartbeat_stale_s=1.5, forecast_total_s=3,
    forecast_primary_cutoff_s=1.5, allocation_total_s=2, method_wall_s=2, method_search_s=1,
    comparison_total_s=4.5, stop_grace_s=0.2, publication_reserve_s=0.3, kill_margin_s=0.1,
    method_min_s=0.3, enrichment_total_s=5)
QUIET = {"sleep_s": 0, "spawn_descendant": False, "ignore_sigterm": False, "fail": None}


@pytest.fixture(scope="module")
def engine():
    url = database_url()
    reset_schema(url, SCHEMA)
    eng = create_queue_engine(url, schema=SCHEMA)
    with eng.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    yield eng
    eng.dispose()
    reset_schema(url, SCHEMA)


@pytest.fixture
def lane(engine, acs, monkeypatch):  # noqa: F811
    """A queue and a started supervisor whose enrichment.v1 calls the replayed Census."""
    # The FakeDriver models fixture behaviors; enrichment.v1 has none, so run it as-is.
    monkeypatch.setattr(fake_driver, "_behavior_for", lambda validated, step: QUIET)
    monkeypatch.setattr(fake_driver, "_with_behavior", lambda validated, step, b: validated)
    census = Census()
    registry = Registry([dataclasses.replace(
        ENRICHMENT_REGISTRATION, handler=EnrichmentHandler(CensusClient(census)),
        publisher=EnrichmentPublisher(lambda: acs))])
    queue = QueueRepository(engine, registry=registry, profile=PROFILE)
    supervisor = Supervisor(queue, registry, fake_driver.FakeDriver(registry=registry),
                            SupervisorConfig(registry_name="test", profile=PROFILE, tick_s=0.02))
    assert supervisor.start()
    yield SimpleNamespace(rt=SimpleNamespace(engine=engine, queue=queue), census=census,
                          supervisor=supervisor)
    supervisor.shutdown_drain(timeout_s=5)  # releases the lane for the next test


def _settle(lane, network_id):
    end = time.monotonic() + 10
    while time.monotonic() < end:
        lane.supervisor.tick()
        status = enrichment_status(lane.rt, SCOPE, network_id)
        if status.state != "running":
            return status
        time.sleep(0.01)
    raise AssertionError("enrichment job did not settle")


@pytest.fixture
def network(engine, tmp_path):
    outcome = _import(engine, tmp_path, {**FILES, "locations": LOCATIONS})
    assert outcome.ok, outcome.errors
    return outcome


def test_retry_runs_the_job_and_status_reports_the_result(lane, network):
    before = enrichment_status(lane.rt, SCOPE, network.network_id)
    assert (before.state, before.job_id, before.dataset_version_id) == (
        "not_started", None, network.dataset_version_id)
    assert {b.location_id for b in before.egp_blockers} == {"P1", "P2", "P3", "P4"}
    accepted = retry_enrichment(lane.rt, SCOPE, network.network_id, str(uuid.uuid4()))
    assert accepted.status_url == f"/api/v1/networks/{network.network_id}/enrichment"
    assert enrichment_status(lane.rt, SCOPE, network.network_id).state == "running"
    status = _settle(lane, network.network_id)
    assert (status.state, status.job_id, status.last_error) == ("done", accepted.job_id, None)
    assert {u.location_id for u in status.unmatched} == {"P3", "P4"}
    attributes = {a.location_id: a for a in status.locations}
    assert attributes["H1"].state == "known"
    assert attributes["H1"].source == "ACS 5-year 2024, tract 12073000200"


def test_outage_publishes_unknown_fields_and_a_retry_fills_them(lane, network):
    lane.census.down = True
    retry_enrichment(lane.rt, SCOPE, network.network_id, str(uuid.uuid4()))
    status = _settle(lane, network.network_id)
    with lane.rt.engine.connect() as conn:
        org = conn.scalar(sa.text("SELECT organization_id FROM networks WHERE id = :n"),
                          {"n": network.network_id})
    job = lane.rt.queue.get_job(TrustedScope(org, "test"), status.job_id)
    assert job.state == AttemptState.SUCCEEDED  # an outage is a result, not a failed job
    assert status.state == "failed"
    assert status.last_error.startswith("Census geocoder unavailable")
    assert {a.location_id: a.state for a in status.locations}["H1"] == "unknown"
    lane.census.down = False
    retry_enrichment(lane.rt, SCOPE, network.network_id, str(uuid.uuid4()))
    status = _settle(lane, network.network_id)
    assert status.state == "done"
    assert {a.location_id: a.state for a in status.locations}["H1"] == "known"


def test_retry_while_a_job_is_running_is_409(lane, network):
    retry_enrichment(lane.rt, SCOPE, network.network_id, str(uuid.uuid4()))
    with pytest.raises(AccessError) as error:
        retry_enrichment(lane.rt, SCOPE, network.network_id, str(uuid.uuid4()))
    assert (error.value.code, error.value.status) == ("ENRICHMENT_IN_PROGRESS", 409)
    _settle(lane, network.network_id)


def test_two_retries_racing_past_the_running_check_share_one_job(lane, network, monkeypatch):
    """#10: two tabs both pass the in-progress check before either job exists; the queue's
    dedupe on the identical payload gives the second the first one's job."""
    import app.services.enrichment.api as enrichment_api

    first = retry_enrichment(lane.rt, SCOPE, network.network_id, str(uuid.uuid4()))
    latest_job = enrichment_api._latest_job
    monkeypatch.setattr(enrichment_api, "_latest_job",
                        lambda conn, n, v: (latest_job(conn, n, v)[0], None))
    second = retry_enrichment(lane.rt, SCOPE, network.network_id, str(uuid.uuid4()))
    assert (second.job_id, second.replayed) == (first.job_id, True)
    monkeypatch.undo()
    _settle(lane, network.network_id)


def test_non_exact_match_stays_listed_for_review_after_a_retry(lane, network):
    """W2-06 verifier: P4's Non_Exact match keeps its "unconfirmed address match" marker, so it
    stays listed with the address Census matched, though the retry no longer sends it."""
    retry_enrichment(lane.rt, SCOPE, network.network_id, str(uuid.uuid4()))
    first = {u.location_id: u for u in _settle(lane, network.network_id).unmatched}
    retry_enrichment(lane.rt, SCOPE, network.network_id, str(uuid.uuid4()))
    status = _settle(lane, network.network_id)
    assert lane.census.calls[-1] == ["99999 Nonexistent Pantry Rd"]  # P4 is not resent
    assert {u.location_id: u for u in status.unmatched} == first
    assert "100 N ANDREWS AVE" in first["P4"].hint


def test_unknown_network_is_404(lane):
    with pytest.raises(AccessError) as error:
        enrichment_status(lane.rt, SCOPE, uuid.uuid4())
    assert error.value.status == 404


@pytest.mark.parametrize("payload", [
    {}, {"dataset_version_id": "nope", "addresses": []},
    {"dataset_version_id": str(uuid.uuid4()), "addresses": [["L1", "street"]]},
    {"dataset_version_id": str(uuid.uuid4()), "addresses": [["L", "s", "c", "FL", "1"]] * 101},
    {"dataset_version_id": str(uuid.uuid4()), "addresses": [], "extra": 1},
])
def test_handler_rejects_malformed_payloads(payload):
    with pytest.raises(InputRejected):
        EnrichmentHandler().validate_input(payload)


def test_publish_refuses_another_organizations_version(engine, network, acs):  # noqa: F811
    identity = PublicationIdentity(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "enrichment.v1",
                                   "0" * 64)
    package = {"dataset_version_id": str(network.dataset_version_id),
               "step": {"geocodes": [], "error": None}}
    with engine.begin() as conn, pytest.raises(PublicationRejected) as error:
        EnrichmentPublisher(lambda: acs).publish(conn, identity, package)
    assert error.value.code == "DATASET_VERSION_NOT_FOUND"
