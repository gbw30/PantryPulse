# covers: V1-A11
"""routes-google.v1 end to end on PostgreSQL (W1-D08): google-fetch submits the job, a real
supervisor runs it with the key in the step child's environment only (child_secrets), and
publish caches and relabels the routes. No Google API is called."""

import dataclasses
import os
import time
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from pydantic import SecretStr

import tests.integration.fake_driver as fake_driver
from app.repositories.jobs import QueueRepository, TrustedScope, create_queue_engine
from app.services.enrichment import settings
from app.services.enrichment.api import list_routes
from app.services.enrichment.google import fetch_routes
from app.services.jobs.contracts import TERMINAL_STATES, AttemptState, StepStatus
from app.services.jobs.registry import (
    InputRejected,
    PublicationIdentity,
    PublicationRejected,
    Registry,
)
from app.workers.enrichment import GOOGLE_REGISTRATION, GoogleHandler, GooglePublisher
from app.workers.supervisor import Supervisor, SupervisorConfig
from tests.enrichment.test_distance import LOCATED
from tests.enrichment.test_enrichment_job import PROFILE, QUIET
from tests.enrichment.test_google import KEY, Routes, _http_error
from tests.imports.test_import_postgres import _import
from tests.integration.wq_support import alembic_config, database_url, reset_schema

pytestmark = pytest.mark.integration
SCHEMA = "w1_data_google_job_test"
SCOPE = TrustedScope(uuid.UUID(int=1), "local")


class ChildEnvDriver(fake_driver.FakeDriver):
    """The FakeDriver runs steps in-process; give each step the environment a real child
    would get (the declared secrets), and nothing after it."""

    def start(self, argv, stdin_bytes, *, child_env=None, **kwargs):
        before = dict(os.environ)
        os.environ.update(child_env or {})
        try:
            return super().start(argv, stdin_bytes, child_env=child_env, **kwargs)
        finally:
            os.environ.clear()
            os.environ.update(before)


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
def lane(engine, monkeypatch):
    monkeypatch.setattr(fake_driver, "_behavior_for", lambda validated, step: QUIET)
    monkeypatch.setattr(fake_driver, "_with_behavior", lambda validated, step, b: validated)
    routes = Routes()
    registry = Registry([dataclasses.replace(GOOGLE_REGISTRATION,
                                             handler=GoogleHandler(transport=routes))])
    queue = QueueRepository(engine, registry=registry, profile=PROFILE)
    driver = ChildEnvDriver(registry=registry)
    supervisor = Supervisor(queue, registry, driver,
                            SupervisorConfig(registry_name="test", profile=PROFILE, tick_s=0.02))
    assert supervisor.start()
    rt = SimpleNamespace(engine=engine, queue=queue)
    settings.set_google_key(rt, SecretStr(KEY))
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM google_distance_cache"))
    yield SimpleNamespace(rt=rt, routes=routes, driver=driver, supervisor=supervisor)
    supervisor.shutdown_drain(timeout_s=5)
    settings.delete_google_key(rt)


@pytest.fixture
def network(engine, tmp_path):
    outcome = _import(engine, tmp_path, LOCATED)
    assert outcome.ok, outcome.errors
    return outcome


def _org(engine, network):
    with engine.connect() as conn:
        return conn.scalar(sa.text("SELECT organization_id FROM networks WHERE id = :n"),
                           {"n": network.network_id})


def _run(lane, network):
    accepted = fetch_routes(lane.rt, SCOPE, network.network_id, str(uuid.uuid4()))
    scope = TrustedScope(_org(lane.rt.engine, network), "test")
    end = time.monotonic() + 10
    while time.monotonic() < end:
        lane.supervisor.tick()
        job = lane.rt.queue.get_job(scope, accepted.job_id)
        if job.state in TERMINAL_STATES:
            return job
        time.sleep(0.01)
    raise AssertionError("routes-google.v1 did not settle")


def _methods(lane, network):
    return {(r.from_location_id, r.to_location_id): r.method
            for r in list_routes(lane.rt, SCOPE, network.network_id).routes}


def _stored_text(engine) -> str:
    with engine.connect() as conn:
        rows = [conn.execute(sa.text(f"SELECT * FROM {t}")).all()
                for t in ("compute_jobs", "compute_attempts", "compute_audit_events")]
    return repr(rows)


def test_fetch_job_relabels_routes_with_the_key_only_in_the_child_env(lane, network):
    job = _run(lane, network)
    assert job.state == AttemptState.SUCCEEDED
    assert set(_methods(lane, network).values()) == {"google_road"}
    assert len(lane.routes.requests) == 2  # one billed request per receiver
    assert lane.driver.child_envs == [{"PP_SECRET_GOOGLE_MAPS_API_KEY": KEY}]
    assert "PP_SECRET_GOOGLE_MAPS_API_KEY" not in os.environ
    [attempt] = job.attempts
    assert attempt.result_manifest == {"fetched": 4, "error": None}
    assert KEY not in _stored_text(lane.rt.engine)


def test_provider_error_publishes_nothing_new_and_keeps_straight_line(lane, network):
    lane.routes.error = _http_error()
    job = _run(lane, network)
    assert job.state == AttemptState.SUCCEEDED  # a provider error is a result, not a crash
    [attempt] = job.attempts
    assert attempt.result_manifest == {"fetched": 0, "error": "GOOGLE_HTTP_403"}
    assert set(_methods(lane, network).values()) == {"straight_line_estimate"}
    assert KEY not in _stored_text(lane.rt.engine)


@pytest.mark.parametrize("payload", [
    {}, {"dataset_version_id": "nope", "lookups": []},
    {"dataset_version_id": str(uuid.uuid4()), "lookups": [["29.0", "-82.0"]]},
    {"dataset_version_id": str(uuid.uuid4()), "lookups": [["91", "-82.0", [["29", "-82"]]]]},
    {"dataset_version_id": str(uuid.uuid4()), "lookups": [], "key": KEY},
])
def test_handler_rejects_malformed_payloads(payload):
    with pytest.raises(InputRejected):
        GoogleHandler().validate_input(payload)


def test_publisher_rejects_results_it_did_not_ask_for(network):
    validated = {"dataset_version_id": str(network.dataset_version_id),
                 "lookups": [["29.651600", "-82.324800", [["30.438300", "-84.280700"]]]]}
    outcome = SimpleNamespace(name="fetch", status=StepStatus.COMPLETED, output={
        "results": [["1.0", "2.0", "29.651600", "-82.324800", 10, 10]], "error": None})
    with pytest.raises(PublicationRejected) as error:
        GooglePublisher().validate(validated, [outcome])
    assert error.value.code == "OUTPUT_INVALID"


def test_publish_refuses_another_organizations_version(engine, network):
    identity = PublicationIdentity(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "routes-google.v1",
                                   "0" * 64)
    package = {"dataset_version_id": str(network.dataset_version_id),
               "step": {"results": [], "error": None}}
    with engine.begin() as conn, pytest.raises(PublicationRejected) as error:
        GooglePublisher().publish(conn, identity, package)
    assert error.value.code == "DATASET_VERSION_NOT_FOUND"


def test_production_registration_declares_only_the_google_secret():
    assert GOOGLE_REGISTRATION.child_secrets == ("google_maps_api_key",)
