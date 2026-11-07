# covers: V1-A07, V1-A09
"""Import lifecycle on PostgreSQL (W1-D05): create → upload → commit (import.v1) → status,
re-import, network reads. The worker step itself is CR-w1-data-2; these tests run
`run_import` directly, exactly as the job will."""

import asyncio
import uuid
from datetime import date
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command

from app.repositories.jobs import QueueRepository, TrustedScope, create_queue_engine
from app.schemas.v1_imports import ImportCommit, ImportCreate, NewNetwork
from app.services.imports import api
from app.services.imports.staging import import_dir, run_import
from app.services.jobs.contracts import PRODUCTION_PROFILE, SupervisorState
from app.services.jobs.policies import supervisor_advertisement
from app.services.jobs.registry import InputRejected
from app.services.networks.api import get_network, list_networks
from app.services.presenter_access import AccessError
from app.workers.registries import load_registry
from tests.imports.test_import_postgres import FILES
from tests.integration.wq_support import alembic_config, database_url, reset_schema

pytestmark = pytest.mark.integration
SCHEMA = "w1_data_job_test"
SCOPE = TrustedScope(organization_id=uuid.UUID(int=7), actor_ref="local")


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


@pytest.fixture(scope="module")
def queue(engine):
    """A READY supervisor advertising import.v1, as the worker will once CR-w1-data-2 lands
    (admission needs one; no step is executed in these tests)."""
    repo = QueueRepository(engine, registry=load_registry("production"),
                           profile=PRODUCTION_PROFILE)
    own = repo.acquire_ownership(
        supervisor_id=uuid.uuid4(), host_identity="test-host",
        effective_limits=supervisor_advertisement(
            PRODUCTION_PROFILE, handler_contracts=("import.v1",), process_containment=True))
    assert own is not None and repo.finish_recovery(own)
    assert repo.set_state(own, SupervisorState.READY)
    return repo


@pytest.fixture
def rt(engine, queue, tmp_path, monkeypatch):
    monkeypatch.setenv("PP_IMPORT_DIR", str(tmp_path))
    yield SimpleNamespace(engine=engine, queue=queue)
    _cancel_queued(engine, queue)


def _cancel_queued(engine, queue):
    """The production profile queues at most 2 jobs, and no step runs here (CR-w1-data-2)."""
    with engine.connect() as conn:
        jobs = conn.execute(sa.text(
            "SELECT job_id, organization_id FROM compute_jobs WHERE state = 'QUEUED'")).all()
    for job_id, org in jobs:
        queue.cancel(TrustedScope(org, "test"), job_id, f"cleanup-{job_id}")


def _new(name=None):
    return ImportCreate(network=NewNetwork(name=name or f"Net {uuid.uuid4().hex[:6]}",
                                           mode="PANTRY", timezone="America/New_York"))


def _upload(rt, import_id, files):
    async def chunks(text):
        yield text.encode()

    for name, text in files.items():
        asyncio.run(api.store_import_file(rt, SCOPE, import_id, name, chunks(text)))


def _commit(rt, import_id, as_of=date(2026, 11, 4)):
    accepted = api.commit_import(rt, SCOPE, import_id, ImportCommit(as_of_date=as_of),
                                 f"commit-{import_id}")
    return accepted


def _run(rt, import_id, as_of=date(2026, 11, 4), on_phase=None):
    return run_import(rt.engine, import_id, as_of, import_dir(), "local", on_phase=on_phase)


def _imported(rt, files=FILES, request=None, as_of=date(2026, 11, 4)):
    created = api.create_import(rt, SCOPE, request or _new())
    _upload(rt, created.import_id, files)
    _commit(rt, created.import_id, as_of)
    _run(rt, created.import_id, as_of)
    _cancel_queued(rt.engine, rt.queue)  # the run is done; free the queue slot
    return api.import_status(rt, SCOPE, created.import_id)


def test_create_then_commit(rt):
    created = api.create_import(rt, SCOPE, _new())
    assert created.network_id is None  # atomic import: no network row yet
    _upload(rt, created.import_id, {k: v for k, v in FILES.items() if k != "inventory"})
    with pytest.raises(InputRejected) as missing:
        _commit(rt, created.import_id)
    assert missing.value.code == "MISSING_FILES"
    assert missing.value.details == {"missing": ["inventory"]}

    _upload(rt, created.import_id, {"inventory": FILES["inventory"]})
    accepted = _commit(rt, created.import_id)
    assert accepted.import_id == created.import_id
    assert accepted.status_url == f"/api/v1/imports/{created.import_id}"
    job = rt.queue.get_job(TrustedScope(_org(rt, created.import_id), "local"), accepted.job_id)
    assert job.handler_contract == "import.v1"
    status = api.import_status(rt, SCOPE, created.import_id)
    assert (status.phase, status.job_id) == ("staging", accepted.job_id)
    assert sorted(f.name for f in status.files) == sorted(FILES)
    replay = _commit(rt, created.import_id)
    assert replay.job_id == accepted.job_id  # same idempotency key → same job


def test_routes_answer_201_202_422(rt):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.routers.forecasts import presenter, runtime

    app = create_app()
    app.dependency_overrides[runtime] = lambda: rt
    app.dependency_overrides[presenter] = lambda: SCOPE
    client = TestClient(app)
    created = client.post("/api/v1/imports", json={"network": {
        "name": "Http", "mode": "RETAIL", "timezone": "America/Chicago"}})
    assert created.status_code == 201, created.text
    import_id = created.json()["import_id"]
    missing = client.post(f"/api/v1/imports/{import_id}/commit", json={},
                          headers={"Idempotency-Key": "k1"})
    assert missing.status_code == 422
    assert missing.json()["error"]["details"]["missing"] == [
        "locations", "products", "inventory", "demand_history"]
    for name, text in FILES.items():
        text = text.replace("hub", "distribution_center").replace("pantry", "store")
        assert client.post(f"/api/v1/imports/{import_id}/files/{name}", content=text.encode(),
                           headers={"Content-Type": "text/csv"}).status_code == 200
    accepted = client.post(f"/api/v1/imports/{import_id}/commit", json={},
                           headers={"Idempotency-Key": "k2"})
    assert accepted.status_code == 202, accepted.text
    assert accepted.headers["location"] == f"/api/v1/imports/{import_id}"
    assert client.get(f"/api/v1/imports/{import_id}").json()["phase"] == "staging"


def _org(rt, import_id):
    with rt.engine.connect() as conn:
        return conn.scalar(sa.text("SELECT organization_id FROM import_runs WHERE id = :i"),
                           {"i": import_id})


def test_progress_phases_in_order(rt):
    created = api.create_import(rt, SCOPE, _new())
    _upload(rt, created.import_id, FILES)
    _commit(rt, created.import_id)
    seen = []

    def record(phase):
        status = api.import_status(rt, SCOPE, created.import_id)
        seen.append((status.phase, status.progress))

    _run(rt, created.import_id, on_phase=record)
    final = api.import_status(rt, SCOPE, created.import_id)
    phases = ["uploading", "staging"] + [p for p, _ in seen if p != "staging"] + [final.phase]
    assert phases == ["uploading", "staging", "validating", "committing", "done"]
    units = {phase: progress.unit for phase, progress in seen}
    assert units == {"staging": "rows", "validating": "checks", "committing": "rows"}
    for _, progress in seen:
        assert progress.total is not None and progress.done <= progress.total
    assert seen[0][1].total == 10  # data rows in the four files


def test_failed_import_reports_errors_and_saves_nothing(rt):
    bad = {**FILES, "inventory": FILES["inventory"] + "H1,RICE,B9,2.5,2026-12-01,,\n"}
    status = _imported(rt, bad)
    assert status.phase == "failed"
    assert status.network_id is None and status.dataset_version_id is None
    assert status.error_count == 1 and not status.errors_truncated
    assert [(e.file, e.line, e.column, e.code) for e in status.errors] == [
        ("inventory", 5, "quantity", "FRACTIONAL")]
    assert status.failure.kind == "ROW_ERRORS"
    assert status.failure.message.startswith("Import failed")
    assert "nothing was saved" in status.failure.message
    assert status.failure.reason == "1 row in 1 file has errors"
    assert status.failure.next_steps
    with rt.engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM dataset_versions WHERE import_run_id = "
                                   ":r"), {"r": status.import_id}) == 0


def test_job_failure_reported_as_failed_import(rt):
    created = api.create_import(rt, SCOPE, _new())
    _upload(rt, created.import_id, FILES)
    accepted = _commit(rt, created.import_id)
    rt.queue.cancel(TrustedScope(_org(rt, created.import_id), "local"), accepted.job_id, "stop-1")
    status = api.import_status(rt, SCOPE, created.import_id)
    assert status.phase == "failed" and status.failure.kind == "JOB_FAILED"
    assert "nothing was saved" in status.failure.message


def test_reimport_creates_new_dataset_version_and_old_scenarios_keep_theirs(rt):
    first = _imported(rt)
    assert first.phase == "done"
    later = {**FILES, "inventory": FILES["inventory"].replace("H1,RICE,B1,40", "H1,RICE,B1,7")}
    second = _imported(rt, later, ImportCreate(network_id=first.network_id),
                       as_of=date(2026, 11, 5))
    assert second.phase == "done" and second.network_id == first.network_id
    assert second.dataset_version_id != first.dataset_version_id
    with rt.engine.connect() as conn:
        def qty(version):
            return conn.scalar(sa.text(
                "SELECT quantity FROM net_batches WHERE dataset_version_id = :v AND "
                "external_id = 'B1' AND quantity IN (7, 40)"), {"v": version})
        assert (qty(first.dataset_version_id), qty(second.dataset_version_id)) == (40, 7)
    network = get_network(rt, SCOPE, first.network_id)
    assert (network.dataset_version_id, network.as_of_date) == (
        second.dataset_version_id, date(2026, 11, 5))


def test_second_import_while_first_runs_returns_409(rt):
    first = _imported(rt)
    running = api.create_import(rt, SCOPE, ImportCreate(network_id=first.network_id))
    _upload(rt, running.import_id, FILES)
    _commit(rt, running.import_id)
    other = api.create_import(rt, SCOPE, ImportCreate(network_id=first.network_id))
    _upload(rt, other.import_id, FILES)
    with pytest.raises(AccessError) as conflict:
        _commit(rt, other.import_id)
    assert (conflict.value.code, conflict.value.status) == ("IMPORT_IN_PROGRESS", 409)
    with pytest.raises(AccessError) as late:
        asyncio.run(api.store_import_file(rt, SCOPE, running.import_id, "routes",
                                          _one(b"from_location_id,to_location_id\n")))
    assert late.value.status == 409


async def _one(data):
    yield data


def test_list_networks_returns_mode_timezone_as_of(rt):
    name = f"Listed {uuid.uuid4().hex[:6]}"
    done = _imported(rt, request=_new(name))
    failed_name = f"Failed {uuid.uuid4().hex[:6]}"
    _imported(rt, {**FILES, "products": "product_id,name\n"}, request=_new(failed_name))
    networks = {n.name: n for n in list_networks(rt, SCOPE).networks}
    assert failed_name not in networks  # a failed first import leaves no network
    listed = networks[name]
    assert (listed.id, listed.mode, listed.timezone, listed.is_sample) == (
        done.network_id, "PANTRY", "America/New_York", False)
    assert (listed.dataset_version_id, listed.as_of_date) == (
        done.dataset_version_id, date(2026, 11, 4))
    assert (listed.location_count, listed.product_count) == (2, 2)
    with pytest.raises(AccessError) as missing:
        get_network(rt, SCOPE, uuid.uuid4())
    assert missing.value.status == 404


def test_as_of_defaults_to_day_after_last_history(rt):
    status = _imported(rt, as_of=None)
    assert status.phase == "done"
    assert status.as_of_date == date(2026, 11, 4)  # last history day is 2026-11-03


def test_run_import_is_idempotent_for_a_done_run(rt):
    status = _imported(rt)
    again = _run(rt, status.import_id)
    assert again.ok and again.dataset_version_id == status.dataset_version_id
    with rt.engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM dataset_versions WHERE import_run_id = "
                                   ":r"), {"r": status.import_id}) == 1


def test_outside_horizon_inbound_listed_in_status(rt):
    inbound = ("location_id,product_id,quantity,arrival_date,expiry_date,non_expiring\n"
               "P1,RICE,6,2026-11-20,,true\n")
    status = _imported(rt, {**FILES, "inbound": inbound})
    assert [(r.line, r.quantity) for r in status.outside_horizon_inbound] == [(2, 6)]
