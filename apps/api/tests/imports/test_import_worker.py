# covers: V1-A07, V1-A09
"""import.v1 end to end on PostgreSQL (W1-D05, CR-w1-data-2): commit submits the job; a real
supervisor runs the DB-less `validate` step, which writes load-ready files; `prepare` bulk-loads
them into staged tables named by the attempt (outside the queue lock); `publish` moves the small
rows in and attaches the history under the lock. Discarded or crashed attempts leave nothing.
A committed version queues its enrichment.v1 in the same transaction (CR-w1-data-5)."""

import contextlib
import dataclasses
import time
import uuid
from datetime import date
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command

import tests.integration.fake_driver as fake_driver
from app.repositories import imports as repo
from app.repositories.jobs import QueueRepository, TrustedScope, create_queue_engine
from app.schemas.v1_imports import ImportCommit, ImportCreate
from app.services.enrichment.api import enrichment_status
from app.services.enrichment.census import CensusClient
from app.services.imports import api
from app.services.imports.staging import job_input, stage_table
from app.services.jobs.contracts import TERMINAL_STATES, AttemptState, StepStatus
from app.services.jobs.registry import (
    ExecutionContext,
    InputRejected,
    PublicationIdentity,
    PublicationRejected,
    Registry,
)
from app.workers.enrichment import ENRICHMENT_REGISTRATION, EnrichmentHandler, EnrichmentPublisher
from app.workers.imports import REGISTRATION, ImportHandler, ImportPublisher
from app.workers.supervisor import Supervisor, SupervisorConfig
from tests.enrichment.test_enrichment_job import PROFILE, QUIET
from tests.enrichment.test_enrichment_postgres import Census, acs  # noqa: F401
from tests.imports.test_import_job import _new, _upload
from tests.imports.test_import_postgres import FILES, NEW, _write
from tests.integration.wq_support import alembic_config, database_url, reset_schema

pytestmark = pytest.mark.integration
SCHEMA = "w1_data_import_worker_test"
SCOPE = TrustedScope(uuid.UUID(int=7), "local")
AS_OF = date(2026, 11, 4)
IMPORT_PROFILE = dataclasses.replace(PROFILE, import_total_s=20)
BAD = {**FILES, "inventory": FILES["inventory"] + "H1,RICE,B9,2.5,2026-12-01,,\n"}


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


@contextlib.contextmanager
def _running(engine, base, monkeypatch, *more):
    monkeypatch.setenv("PP_IMPORT_DIR", str(base))
    monkeypatch.setattr(fake_driver, "_behavior_for", lambda validated, step: QUIET)
    monkeypatch.setattr(fake_driver, "_with_behavior", lambda validated, step, b: validated)
    registry = Registry([dataclasses.replace(REGISTRATION, publisher=ImportPublisher()), *more])
    queue = QueueRepository(engine, registry=registry, profile=IMPORT_PROFILE)
    supervisor = Supervisor(queue, registry, fake_driver.FakeDriver(registry=registry),
                            SupervisorConfig(registry_name="test", profile=IMPORT_PROFILE,
                                             tick_s=0.02))
    assert supervisor.start()
    try:
        yield SimpleNamespace(engine=engine, queue=queue, supervisor=supervisor, base=base,
                              publisher=registry.get("import.v1").publisher)
    finally:
        supervisor.shutdown_drain(timeout_s=5)


@pytest.fixture
def lane(engine, tmp_path, monkeypatch):
    """import.v1 only: an enrichment follow-up is rejected as an unknown contract."""
    with _running(engine, tmp_path, monkeypatch) as running:
        yield running


@pytest.fixture
def enriching(engine, tmp_path, monkeypatch, acs):  # noqa: F811
    """import.v1 and enrichment.v1 (replayed Census answers) on one supervisor."""
    enrichment = dataclasses.replace(
        ENRICHMENT_REGISTRATION, handler=EnrichmentHandler(CensusClient(Census())),
        publisher=EnrichmentPublisher(lambda: acs))
    with _running(engine, tmp_path, monkeypatch, enrichment) as running:
        yield running


def _commit(lane, files, request=None):
    created = api.create_import(lane, SCOPE, request or _new())
    _upload(lane, created.import_id, files)
    accepted = api.commit_import(lane, SCOPE, created.import_id, ImportCommit(as_of_date=AS_OF),
                                 f"commit-{created.import_id}")
    return created.import_id, accepted.job_id


def _settle(lane, import_id, job_id):
    with lane.engine.connect() as conn:
        org = repo.get_run(conn, import_id).organization_id
    end = time.monotonic() + 15
    while time.monotonic() < end:
        lane.supervisor.tick()
        job = lane.queue.get_job(TrustedScope(org, "test"), job_id)
        if job.state in TERMINAL_STATES:
            return job
        time.sleep(0.01)
    raise AssertionError("import.v1 did not settle")


def _staged(engine) -> list[str]:
    with engine.connect() as conn:
        return list(conn.scalars(sa.text(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
            "AND tablename LIKE 'pp\\_stage\\_%' ORDER BY tablename")))


def _count(engine, sql, **params) -> int:
    with engine.connect() as conn:
        return conn.scalar(sa.text(sql), params)


def test_commit_runs_the_job_and_publishes_one_version(lane):
    import_id, job_id = _commit(lane, FILES)
    job = _settle(lane, import_id, job_id)
    assert job.state == AttemptState.SUCCEEDED, job
    status = api.import_status(lane, SCOPE, import_id)
    assert status.phase == "done" and status.network_id and status.dataset_version_id
    [attempt] = job.attempts
    assert attempt.result_manifest == {"ok": True, "network_id": str(status.network_id),
                                       "dataset_version_id": str(status.dataset_version_id)}
    version = status.dataset_version_id
    assert _count(lane.engine, "SELECT count(*) FROM net_demand_history "
                  "WHERE dataset_version_id = :v", v=version) == 3
    assert _count(lane.engine, "SELECT count(*) FROM net_batches "
                  "WHERE dataset_version_id = :v", v=version) == 3
    assert _count(lane.engine, (
        "SELECT count(*) FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid "
        "JOIN pg_class p ON p.oid = i.inhparent WHERE c.relname = p.relname || '_' || :hex"),
        hex=version.hex) == 3  # batches and both history partitions, attached by version
    assert _count(lane.engine, (
        "SELECT count(*) FROM pg_constraint WHERE contype = 'f' AND conrelid = "
        "to_regclass('net_demand_history_' || :hex)"), hex=version.hex) == 3  # the parent's, cloned
    assert _staged(lane.engine) == []
    assert not list((lane.base / str(import_id)).glob("attempt-*"))


def test_row_errors_fail_the_import_save_nothing_and_keep_the_files(lane):
    import_id, job_id = _commit(lane, BAD)
    job = _settle(lane, import_id, job_id)
    assert job.state == AttemptState.SUCCEEDED  # the job finished; its result is the report
    [attempt] = job.attempts
    assert attempt.result_manifest == {"ok": False, "error_count": 1}
    status = api.import_status(lane, SCOPE, import_id)
    assert (status.phase, status.failure.kind) == ("failed", "ROW_ERRORS")
    assert [(e.file, e.line, e.column, e.code) for e in status.errors] == [
        ("inventory", 5, "quantity", "FRACTIONAL")]
    assert status.network_id is None and status.dataset_version_id is None
    assert _staged(lane.engine) == []
    assert sorted(p.name for p in (lane.base / str(import_id)).iterdir()) == sorted(
        f"{name}.csv" for name in BAD)  # uploads kept for a corrected retry, no attempt folder


def test_prepare_drops_what_a_crashed_attempt_left(lane):
    orphan = uuid.uuid4().hex  # a supervisor died between prepare and publish
    with lane.engine.begin() as conn:
        conn.execute(sa.text(f"CREATE TABLE pp_stage_{orphan}_demand (LIKE net_demand_history)"))
    crashed = lane.base / str(uuid.uuid4()) / f"attempt-{orphan}"
    crashed.mkdir(parents=True)
    (crashed / "history.csv").write_text("demand_history,2,P1,RICE,2026-11-01,3,demand\n")
    import_id, job_id = _commit(lane, FILES)
    assert _settle(lane, import_id, job_id).state == AttemptState.SUCCEEDED
    assert _staged(lane.engine) == []
    assert not crashed.exists()


def test_next_import_removes_the_uploads_of_a_done_import(lane):
    first, job_id = _commit(lane, FILES)
    assert _settle(lane, first, job_id).state == AttemptState.SUCCEEDED
    failed, job_id = _commit(lane, BAD)
    assert _settle(lane, failed, job_id).state == AttemptState.SUCCEEDED
    assert not (lane.base / str(first)).exists()  # done: its files are no longer needed
    assert (lane.base / str(failed) / "inventory.csv").exists()  # failed: kept for the retry


def test_rejected_publication_discards_the_staged_tables(lane, monkeypatch):
    def reject(connection, identity, package):
        raise PublicationRejected("IMPORT_NOT_FOUND")

    monkeypatch.setattr(lane.publisher, "publish", reject)
    request = _new()
    import_id, job_id = _commit(lane, FILES, request)
    job = _settle(lane, import_id, job_id)
    assert job.state == AttemptState.FAILED
    assert _staged(lane.engine) == []
    status = api.import_status(lane, SCOPE, import_id)
    assert (status.phase, status.failure.kind) == ("failed", "JOB_FAILED")
    assert _count(lane.engine, "SELECT count(*) FROM networks WHERE name = :n",
                  n=request.network.name) == 0


@pytest.mark.parametrize(("suffix", "column"), [
    ("batches", "location_id"), ("batches", "product_id"), ("batches", "organization_id"),
    ("demand", "product_id")])
def test_a_foreign_key_failure_at_attach_fails_the_import(lane, monkeypatch, suffix, column):
    """W2-06: staged partitions carry no FKs, so ATTACH is the first check. A row it refuses
    must end the attempt FAILED and discarded, never stop the worker."""
    prepare = lane.publisher.prepare

    def corrupt(engine, identity, package, *, remaining_s):
        prepared = prepare(engine, identity, package, remaining_s=remaining_s)
        with engine.begin() as conn:
            conn.execute(sa.text(
                f"UPDATE {stage_table(identity.attempt_id, suffix)} SET {column} = "
                f"gen_random_uuid() WHERE ctid = (SELECT min(ctid) FROM "
                f"{stage_table(identity.attempt_id, suffix)})"))
        return prepared

    monkeypatch.setattr(lane.publisher, "prepare", corrupt)
    request = _new()
    import_id, job_id = _commit(lane, FILES, request)
    job = _settle(lane, import_id, job_id)
    assert (job.attempts[0].state, job.attempts[0].reason_code) == (
        AttemptState.FAILED, "PUBLICATION_STORAGE_FAILED")
    assert _staged(lane.engine) == []
    assert _count(lane.engine, "SELECT count(*) FROM networks WHERE name = :n",
                  n=request.network.name) == 0
    assert _count(lane.engine, "SELECT count(*) FROM dataset_versions WHERE import_run_id = :r",
                  r=import_id) == 0
    status = api.import_status(lane, SCOPE, import_id)
    assert (status.phase, status.failure.kind) == ("failed", "JOB_FAILED")
    monkeypatch.setattr(lane.publisher, "prepare", prepare)
    after, after_job = _commit(lane, FILES)  # the supervisor still serves the next job
    assert _settle(lane, after, after_job).state == AttemptState.SUCCEEDED


def test_a_failed_reimport_blocks_neither_the_network_nor_its_own_retry(lane, monkeypatch):
    first, job_id = _commit(lane, FILES)
    assert _settle(lane, first, job_id).state == AttemptState.SUCCEEDED
    again = ImportCreate(network_id=api.import_status(lane, SCOPE, first).network_id)
    publish = lane.publisher.publish

    def reject(connection, identity, package):
        raise PublicationRejected("IMPORT_NOT_FOUND")

    monkeypatch.setattr(lane.publisher, "publish", reject)
    failed, failed_job = _commit(lane, FILES, again)
    assert _settle(lane, failed, failed_job).state == AttemptState.FAILED
    assert api.import_status(lane, SCOPE, failed).phase == "failed"
    monkeypatch.setattr(lane.publisher, "publish", publish)
    other, other_job = _commit(lane, FILES, again)  # not IMPORT_IN_PROGRESS: nothing runs
    assert _settle(lane, other, other_job).state == AttemptState.SUCCEEDED
    retried = api.commit_import(lane, SCOPE, failed, ImportCommit(as_of_date=AS_OF),
                                f"retry-{failed}")  # "Commit the import again"
    assert retried.job_id != failed_job
    assert _settle(lane, failed, retried.job_id).state == AttemptState.SUCCEEDED
    assert api.import_status(lane, SCOPE, failed).phase == "done"


# --- enrichment.v1 queued with the publication (CR-w1-data-5) -----------------------------

def _enrichment_jobs(engine) -> list[tuple]:
    with engine.connect() as conn:
        return conn.execute(sa.text(
            "SELECT job_id, organization_id, requested_by_ref, input_package -> 'input' "
            "FROM compute_jobs WHERE handler_contract = 'enrichment.v1' "
            "ORDER BY created_at")).all()


def test_a_committed_import_queues_one_enrichment_job_that_then_runs(enriching):
    before = _enrichment_jobs(enriching.engine)
    import_id, job_id = _commit(enriching, FILES)
    assert _settle(enriching, import_id, job_id).state == AttemptState.SUCCEEDED
    status = api.import_status(enriching, SCOPE, import_id)
    with enriching.engine.connect() as conn:
        org = repo.get_run(conn, import_id).organization_id
    [(enrich_id, enrich_org, actor, payload)] = _enrichment_jobs(enriching.engine)[len(before):]
    assert (enrich_org, actor) == (org, SCOPE.actor_ref)  # the importer's organization and actor
    with enriching.engine.connect() as conn:
        queued = conn.scalars(sa.text(
            "SELECT details FROM compute_audit_events "
            "WHERE job_id = :j AND event_type = 'FOLLOW_UP_QUEUED'"), {"j": job_id}).all()
    assert queued == [{"contract": "enrichment.v1", "follow_up_job_id": str(enrich_id)}]
    assert enriching.queue.get_job(TrustedScope(org, "test"), enrich_id).state == (
        AttemptState.QUEUED)
    assert payload == {"dataset_version_id": str(status.dataset_version_id), "addresses": [
        ["H1", "301 S Monroe St", "Tallahassee", "FL", "32301"],
        ["P1", "201 E University Ave", "Gainesville", "FL", "32601"]]}
    end = time.monotonic() + 15
    while (enriched := enrichment_status(enriching, SCOPE, status.network_id)).state == "running":
        assert time.monotonic() < end, "enrichment.v1 did not settle"
        enriching.supervisor.tick()
        time.sleep(0.01)
    assert (enriched.state, enriched.job_id) == ("done", enrich_id)


def test_an_import_that_saves_nothing_queues_no_enrichment(enriching, monkeypatch):
    before = len(_enrichment_jobs(enriching.engine))
    import_id, job_id = _commit(enriching, BAD)  # row errors: the job succeeds, nothing saved
    assert _settle(enriching, import_id, job_id).state == AttemptState.SUCCEEDED

    def reject(connection, identity, package):
        raise PublicationRejected("IMPORT_NOT_FOUND")

    monkeypatch.setattr(enriching.publisher, "publish", reject)
    import_id, job_id = _commit(enriching, FILES)
    assert _settle(enriching, import_id, job_id).state == AttemptState.FAILED
    assert len(_enrichment_jobs(enriching.engine)) == before


def test_a_rejected_enrichment_still_commits_the_import(lane):
    import_id, job_id = _commit(lane, FILES)  # enrichment.v1 is not registered on this lane
    assert _settle(lane, import_id, job_id).state == AttemptState.SUCCEEDED
    status = api.import_status(lane, SCOPE, import_id)
    assert status.phase == "done"
    with lane.engine.connect() as conn:
        audited = conn.execute(sa.text(
            "SELECT reason_code, details FROM compute_audit_events "
            "WHERE job_id = :j AND event_type = 'FOLLOW_UP_REJECTED'"), {"j": job_id}).all()
    [(reason, details)] = audited  # details also name the error type
    assert (reason, details["contract"]) == ("UNKNOWN_CONTRACT", "enrichment.v1")
    assert enrichment_status(lane, SCOPE, status.network_id).state == "not_started"


# --- the hooks, called directly ---------------------------------------------------------

@pytest.fixture
def prepared(engine, tmp_path):
    """One run's step output and publication package, as the supervisor builds them."""
    with engine.begin() as conn:
        run = repo.create_run(conn, NEW, None)
    _write(engine, tmp_path, run.id, FILES)
    with engine.connect() as conn:
        validated = ImportHandler().validate_input(
            job_input(conn, repo.get_run(conn, run.id), AS_OF, tmp_path, "local"))
    attempt = uuid.uuid4()
    output = ImportHandler().execute_step(
        "validate", validated, (), ExecutionContext(uuid.uuid4(), attempt, "validate", 10, 10))
    step = SimpleNamespace(name="validate", status=StepStatus.COMPLETED, output=output)
    package = ImportPublisher().validate(validated, [step])
    identity = PublicationIdentity(uuid.uuid4(), attempt, run.organization_id, "import.v1",
                                   "0" * 64)
    return SimpleNamespace(package=package, identity=identity, run=run, base=tmp_path)


def test_discard_drops_the_attempts_tables_and_is_idempotent(engine, prepared):
    ImportPublisher().prepare(engine, prepared.identity, prepared.package, remaining_s=30)
    assert len(_staged(engine)) == 7  # five row tables and two history partitions
    assert not list(prepared.base.glob("*/attempt-*"))  # loaded, so its files are gone
    ImportPublisher().discard(engine, prepared.identity)
    ImportPublisher().discard(engine, prepared.identity)
    assert _staged(engine) == []


def test_prepare_refuses_another_organizations_job(engine, prepared):
    other = dataclasses.replace(prepared.identity, organization_id=uuid.uuid4())
    with pytest.raises(PublicationRejected) as error:
        ImportPublisher().prepare(engine, other, prepared.package, remaining_s=30)
    assert error.value.code == "IMPORT_NOT_FOUND"
    assert _staged(engine) == []


def _payload(**change):
    payload = {"import_id": str(uuid.uuid4()), "organization_id": str(uuid.uuid4()),
               "as_of_date": "2026-11-04", "mode": "PANTRY", "timezone": "America/New_York",
               "files": ["locations", "products", "inventory", "demand_history"],
               "import_dir": "/var/lib/pp-imports", "actor": "local"}
    return {**payload, **change}


@pytest.mark.parametrize("payload", [
    {}, _payload(import_dir="relative/dir"), _payload(files=["locations", "../etc/passwd"]),
    _payload(mode="WHOLESALE"), _payload(timezone="Mars/Olympus"), _payload(extra=1),
    _payload(import_id="nope"), _payload(as_of_date="2026-13-01"),
])
def test_handler_rejects_malformed_payloads(payload):
    with pytest.raises(InputRejected) as error:
        ImportHandler().validate_input(payload)
    assert error.value.code == "INVALID_IMPORT_JOB"


def test_handler_accepts_the_commit_payload():
    validated = ImportHandler().validate_input(_payload(as_of_date=None))
    assert validated["as_of_date"] is None and validated["files"] == sorted(_payload()["files"])
