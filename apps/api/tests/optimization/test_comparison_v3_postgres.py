# covers: V1-A14, V1-A15, V1-A16, V1-A22
"""or-comparison.v3 on PostgreSQL: submit, worker steps, fenced publication, reads and export.

Runs on an isolated schema of the dedicated test database (PP_TEST_DATABASE_URL, never skipped
in the full gate). The scenario row is inserted directly: scenario creation is W1-D09.
"""

import hashlib
import json
import uuid
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import create_app
from app.repositories.jobs import (
    CommitUncertain,
    QueueRepository,
    TrustedScope,
    create_queue_engine,
)
from app.services.forecast_runtime import ForecastRuntime
from app.services.jobs.contracts import (
    PRODUCTION_PROFILE,
    AttemptState,
    ReasonCode,
    StepOutcome,
    StepStatus,
    SupervisorState,
)
from app.services.jobs.policies import supervisor_advertisement
from app.services.jobs.registry import ExecutionContext
from app.services.optimization.export import SIMULATED_NOTE
from app.workers.registries import load_registry
from tests.integration.wq_support import alembic_config, database_url, reset_schema
from tests.optimization.test_retail_oracle import load

pytestmark = pytest.mark.integration

SCHEMA = "w1_solver_v3_test"
RETAIL = ["NO_TRANSFERS", "SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED"]


@pytest.fixture(scope="module")
def storage():
    url = database_url()
    reset_schema(url, SCHEMA)
    engine = create_queue_engine(url, schema=SCHEMA)
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    queue = QueueRepository(
        engine, registry=load_registry("production"), profile=PRODUCTION_PROFILE
    )
    own = queue.acquire_ownership(
        supervisor_id=uuid.uuid4(),
        host_identity="TEST_DIRECT_EXECUTION",
        effective_limits=supervisor_advertisement(
            PRODUCTION_PROFILE,
            handler_contracts=queue.registry.contracts(),
            process_containment=True,
        ),
    )
    assert own and queue.set_state(own, SupervisorState.READY)
    yield ForecastRuntime(engine, queue), own
    engine.dispose()
    reset_schema(url, SCHEMA)


def seed(engine, name="retail-usd-flip"):
    """Organization → network → dataset version → one frozen or-input-v3 scenario row."""
    ids = {k: uuid.uuid4() for k in ("org", "net", "ver", "run", "scenario")}
    s, _ = load(name)
    payload = s.model_copy(
        update=dict(
            network_id=ids["net"], organization_id=ids["org"], dataset_version_id=ids["ver"]
        )
    ).model_dump(mode="json")
    content_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with engine.begin() as conn:
        q = lambda sql, **kw: conn.execute(sa.text(sql), {**ids, **kw})  # noqa: E731
        q("INSERT INTO organizations (id, name, is_demo) VALUES (:org, 'w1-solver', false)")
        q(
            "INSERT INTO networks (id, organization_id, name, mode, timezone) "
            "VALUES (:net, :org, 'n', :mode, 'America/New_York')",
            mode=s.mode,
        )
        q(
            "INSERT INTO import_runs (id, organization_id, network_id, phase) "
            "VALUES (:run, :org, :net, 'committing')"
        )
        q(
            "INSERT INTO dataset_versions (id, organization_id, network_id, import_run_id, "
            "as_of_date, input_sha256) VALUES (:ver, :org, :net, :run, '2026-11-03', "
            "repeat('a', 64))"
        )
        q(
            "INSERT INTO planning_scenarios_v3 (id, organization_id, network_id, "
            "dataset_version_id, forecast_run_id, content_hash, payload) VALUES (:scenario, :org, "
            ":net, :ver, :run, :hash, CAST(:payload AS jsonb))",
            hash=content_hash,
            payload=json.dumps(payload),
        )
    return ids


@pytest.fixture
def api(storage, monkeypatch):
    rt, own = storage
    ids = seed(rt.engine)
    salt = "37" * 16
    digest = hashlib.scrypt(
        b"test-password", salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=64
    ).hex()
    for k, v in dict(
        PP_PRESENTER_USERNAME="tester",
        PP_PRESENTER_PASSWORD_HASH=f"scrypt$16384$8$1${salt}${digest}",
        PP_PRESENTER_ORGANIZATION_ID=str(ids["org"]),
        PP_COOKIE_SECURE="false",
        PP_ALLOWED_ORIGINS="http://testserver",
    ).items():
        monkeypatch.setenv(k, v)
    with TestClient(create_app(rt)) as client:
        login = client.post(
            "/api/v1/presenter/login",
            json=dict(username="tester", password="test-password"),
            headers={"Origin": "http://testserver"},
        )
        assert login.status_code == 200, login.text
        headers = {"Origin": "http://testserver", "X-CSRF-Token": login.json()["csrf_token"]}
        yield client, headers, rt, own, ids


def submit(client, headers, ids, key="cmp", methods=RETAIL, measure="UNITS"):
    return client.post(
        f"/api/v1/networks/{ids['net']}/comparisons",
        json=dict(scenario_id=str(ids["scenario"]), methods=methods, measure=measure),
        headers=headers | {"Idempotency-Key": key},
    )


def run(queue, own, skip=()):
    """Claim the next job and run its steps the way the supervisor does; return the package."""
    claim = queue.claim_next(own)
    assert claim is not None and claim.contract == "or-comparison.v3"
    reg = queue.registry.get(claim.contract)
    data = claim.input_package["input"]
    outcomes = []
    for step in reg.handler.steps(data, PRODUCTION_PROFILE):
        if step.name in skip:
            outcomes.append(StepOutcome(step.name, StepStatus.TIMED_OUT, None, "STEP_TIMEOUT"))
            continue
        context = ExecutionContext(claim.job_id, claim.attempt_id, step.name, 330, 300)
        output = reg.handler.execute_step(step.name, data, [], context)
        outcomes.append(StepOutcome(step.name, StepStatus.COMPLETED, output))
    return claim, reg.publisher.validate(data, outcomes)


def published(api, **kw):
    client, headers, rt, own, ids = api
    accepted = submit(client, headers, ids)
    assert accepted.status_code == 202, accepted.text
    claim, package = run(rt.queue, own, **kw)
    rt.queue.publish(own, claim, package)
    return accepted.json()["result_url"], package["comparison"]


def code(response):
    return response.json()["error"]["code"]


def rows(engine, job_id):
    with engine.connect() as conn:
        return conn.execute(
            sa.text("SELECT attempt_id FROM planning_comparisons_v3 WHERE job_id = :j"),
            {"j": job_id},
        ).all()


def test_comparison_is_404_until_published_then_readable(api):
    client, headers, rt, own, ids = api
    accepted = submit(client, headers, ids)
    assert accepted.status_code == 202, accepted.text
    job = accepted.json()
    base = f"/api/v1/networks/{ids['net']}/comparisons"
    assert job["result_url"] == f"{base}/{job['job_id']}"  # comparison_id = job_id
    assert accepted.headers["Location"] == job["status_url"] == f"/api/v1/jobs/{job['job_id']}"
    early = client.get(job["result_url"])
    assert early.status_code == 404 and code(early) == "COMPARISON_NOT_FOUND"

    claim, package = run(rt.queue, own)
    assert claim.job_id == UUID(job["job_id"])
    manifest = rt.queue.publish(own, claim, package)
    assert manifest == dict(
        result_ref=job["job_id"], planning_ready=True, comparison_outcome="SUCCEEDED"
    )
    saved = client.get(job["result_url"])
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["id"], body["network_id"]) == (job["job_id"], str(ids["net"]))
    assert body["scenario_id"] == str(ids["scenario"])
    assert body["result"] == package["comparison"]
    assert [m["method"] for m in body["result"]["methods"]] == RETAIL
    assert all(m["verified"] for m in body["result"]["methods"])

    replay = submit(client, headers, ids)
    assert replay.json()["replayed"] and replay.json()["job_id"] == job["job_id"]

    actions = client.get(f"{job['result_url']}/methods/RETAIL_OPTIMIZED/actions")
    assert actions.status_code == 200, actions.text
    transfers = body["result"]["methods"][2]["transfers"]
    assert transfers and {a["id"] for a in actions.json()["actions"]} == {
        t["id"] for t in transfers
    }
    assert actions.json()["comparison_id"] == job["job_id"]


def stock_counts(engine):
    """Row count of every table in the test schema except the job queue's own bookkeeping."""
    with engine.connect() as conn:
        tables = conn.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = :s "
                "AND table_name NOT LIKE 'compute\\_%' AND table_name NOT LIKE 'worker\\_%'"
            ),
            {"s": SCHEMA},
        ).scalars()
        return {t: conn.scalar(sa.text(f'SELECT count(*) FROM "{SCHEMA}"."{t}"')) for t in tables}


def test_export_changes_no_stock(api):
    client, headers, rt, _, _ = api
    url, comparison = published(api)
    chosen = [t["id"] for t in comparison["methods"][2]["transfers"]][:1]
    before = stock_counts(rt.engine)
    assert {"net_batches", "planning_comparisons_v3"} <= set(before)
    exported = client.post(
        f"{url}/methods/RETAIL_OPTIMIZED/export", json=dict(action_ids=chosen), headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("text/csv")
    lines = exported.text.strip().splitlines()
    assert len(lines) == 2 and SIMULATED_NOTE in lines[1]  # header plus the one chosen action
    assert stock_counts(rt.engine) == before


def test_reads_reject_what_is_not_there(api):
    client, headers, rt, _, ids = api
    other = dict(ids, scenario=uuid.uuid4())
    missing = submit(client, headers, other, key="missing")
    assert missing.status_code == 404 and code(missing) == "SCENARIO_NOT_FOUND"
    tenant = seed(rt.engine)  # another organization's network and scenario
    for net in (ids["net"], tenant["net"]):
        theirs = submit(client, headers, dict(net=net, scenario=tenant["scenario"]), key=f"t{net}")
        assert theirs.status_code == 404 and code(theirs) == "SCENARIO_NOT_FOUND"
    foreign = submit(client, headers, ids, key="foreign", methods=["CLASSICAL_GP"])
    assert foreign.status_code == 422 and code(foreign) == "METHOD_NOT_IN_MODE"

    url, _ = published(api, skip={"SOONEST_EXPIRY_FIRST"})
    elsewhere = url.replace(str(ids["net"]), str(uuid.uuid4()))
    assert code(client.get(elsewhere)) == "COMPARISON_NOT_FOUND"
    not_run = client.get(f"{url}/methods/EQUAL_SHARE/actions")
    assert not_run.status_code == 404 and code(not_run) == "METHOD_NOT_IN_COMPARISON"
    timed_out = client.get(f"{url}/methods/SOONEST_EXPIRY_FIRST/actions")
    assert timed_out.status_code == 409 and code(timed_out) == "RESULT_NOT_VERIFIED"
    unknown = client.post(
        f"{url}/methods/RETAIL_OPTIMIZED/export", json=dict(action_ids=["nope"]), headers=headers
    )
    assert unknown.status_code == 422 and code(unknown) == "UNKNOWN_ACTION_ID"


class _CommitThenLose(QueueRepository):
    def _commit(self, transaction):
        transaction.commit()
        raise OperationalError("COMMIT", {}, Exception("connection lost after commit"))


class _LoseBeforeCommit(QueueRepository):
    def _commit(self, transaction):
        transaction.rollback()
        raise OperationalError("COMMIT", {}, Exception("connection lost before commit"))


@pytest.mark.parametrize(
    ("cls", "expected"), [(_CommitThenLose, "COMMITTED"), (_LoseBeforeCommit, "ABSENT")]
)
def test_uncertain_commit_leaves_one_row_or_none_and_retry_never_doubles(api, cls, expected):
    """Comparison row and SUCCEEDED commit together; rows are immutable, so nothing is orphaned."""
    client, headers, rt, own, ids = api
    accepted = submit(client, headers, ids, key=f"uncertain-{expected}").json()
    job_id = UUID(accepted["job_id"])
    claim, package = run(rt.queue, own)
    lossy = cls(rt.engine, registry=rt.queue.registry, profile=PRODUCTION_PROFILE)
    with pytest.raises(CommitUncertain):
        lossy.publish(own, claim, package)
    assert rt.queue.reconcile_publication(own, claim) == expected
    if expected == "COMMITTED":
        assert rows(rt.engine, job_id) == [(claim.attempt_id,)]
        assert client.get(accepted["result_url"]).status_code == 200
        return
    assert rows(rt.engine, job_id) == []
    assert code(client.get(accepted["result_url"])) == "COMPARISON_NOT_FOUND"
    failure = ReasonCode.PUBLICATION_COMMIT_LOST
    assert rt.queue.finalize(own, claim, failure_reason=failure) is AttemptState.FAILED
    scope = TrustedScope(organization_id=ids["org"], actor_ref="tester")
    retried = rt.queue.retry(scope, job_id, "retry-uncertain")
    again, package = run(rt.queue, own)
    assert (again.job_id, again.attempt_id) == (job_id, retried.attempt_id)
    rt.queue.publish(own, again, package)
    assert rows(rt.engine, job_id) == [(again.attempt_id,)]
    assert client.get(accepted["result_url"]).json()["id"] == str(job_id)
