"""WQ-06 vertical slice: real supervisor processes, real Linux children, real PostgreSQL.

Exercises acceptance, single execution, heartbeat-independent containment, timeout with
descendant cleanup, cancellation, a real supervisor SIGKILL with orphan recovery, drain and
immediate shutdown, restart retention and manual retry (WQ-T10–T15, T21, T22). Test
handlers only: no forecast, allocation or model claim. NOT RUN off Linux.
"""

import json
import os
import signal
import subprocess
import sys
import time
import uuid

import pytest
import sqlalchemy as sa
from wq_support import API_ROOT, SCHEMA, database_url

from app.repositories.jobs import QueueRepository, TrustedScope
from app.services.jobs.contracts import AttemptState, RuntimeProfile, SupervisorState
from app.workers.process_driver import (
    BoundaryIdentity,
    PosixProcessDriver,
    linux_containment_available,
)
from app.workers.testing import REGISTRY

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not linux_containment_available(), reason="NOT RUN: Linux process containment unavailable"
    ),
]

PROFILE = dict(
    queue_wait_s=60,
    heartbeat_interval_s=0.3,
    heartbeat_stale_s=1.5,
    forecast_total_s=6,
    forecast_primary_cutoff_s=3,
    allocation_total_s=4,
    method_wall_s=4,
    method_search_s=2,
    comparison_total_s=8,
    stop_grace_s=0.5,
    publication_reserve_s=0.5,
    method_min_s=0.3,
)


@pytest.fixture
def q(db):
    return QueueRepository(db, registry=REGISTRY, profile=RuntimeProfile(**PROFILE))


@pytest.fixture
def org():
    return TrustedScope(organization_id=uuid.uuid4(), actor_ref="presenter")


class SupervisorProcess:
    def __init__(self):
        env = {**os.environ, "DATABASE_URL": database_url()}
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "app.workers.supervisor",
                "--registry",
                "test",
                "--schema",
                SCHEMA,
                "--profile-json",
                json.dumps(PROFILE),
            ],
            cwd=API_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        line = self.proc.stdout.readline()
        assert "SUPERVISOR_RUNNING" in line, line

    def signal(self, sig):
        self.proc.send_signal(sig)

    def wait(self, timeout=20):
        return self.proc.wait(timeout)

    def kill(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(10)


@pytest.fixture
def supervisors():
    started = []

    def start():
        sup = SupervisorProcess()
        started.append(sup)
        return sup

    yield start
    for sup in started:
        if sup.proc.poll() is None:
            sup.signal(signal.SIGINT)
            try:
                sup.wait(15)
            except subprocess.TimeoutExpired:
                sup.kill()


def wait_for(predicate, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not reached")


def state(q, org, job_id):
    return q.get_job(org, job_id).state


def terminal(q, org, job_id):
    return lambda: (
        state(q, org, job_id)
        not in (
            AttemptState.QUEUED,
            AttemptState.RUNNING,
            AttemptState.STOPPING,
        )
    )


def submit(q, org, behavior=None, contract="test.echo.v1", payload=None):
    payload = payload or {"value": 9, "behavior": behavior or {}}
    return q.submit(org, contract, payload, str(uuid.uuid4()))


def boundary(q, org, job_id, attempt=0):
    raw = q.get_job(org, job_id).attempts[attempt].execution_boundary
    return BoundaryIdentity.from_json(raw)


DRIVER = PosixProcessDriver(cwd=API_ROOT)


def test_watchdog_stops_real_child_while_database_read_blocks(q, org, monkeypatch):
    from app.workers.supervisor import Supervisor, SupervisorConfig

    sup = Supervisor(q, REGISTRY, DRIVER, SupervisorConfig("test", q.profile))
    handle = None
    try:
        assert sup.start()
        accepted = submit(q, org, {"sleep_s": 60, "ignore_sigterm": True, "spawn_descendant": True})
        sup.tick()
        run = sup.active.current
        handle = run.handle
        wait_for(lambda: len(DRIVER.members(handle.identity)) >= 2)
        original_control = q.control

        def blocked_control():
            # Keep the repository call blocked until beyond the step's hard deadline.
            while time.monotonic() < run.hard_at + 0.1:
                time.sleep(0.01)
            assert DRIVER.poll(handle) is not None
            assert DRIVER.confirm_empty(handle.identity)
            return original_control()

        monkeypatch.setattr(q, "control", blocked_control)
        sup._last_ownership_check = 0
        sup.tick()
        monkeypatch.setattr(q, "control", original_control)

        def finished():
            sup.tick()
            return terminal(q, org, accepted.job_id)()

        wait_for(finished)
        assert state(q, org, accepted.job_id) is AttemptState.TIMED_OUT
        assert q.control().active_attempt_id is None
        sup.shutdown_drain()
    finally:
        sup.close()
        if handle is not None:
            DRIVER.force_stop(handle)
            handle.process.wait(timeout=5)
            DRIVER.dispose(handle)


def test_accepted_job_runs_once_in_a_contained_child(q, org, supervisors):
    supervisors()
    accepted = submit(q, org)
    wait_for(terminal(q, org, accepted.job_id))
    view = q.get_job(org, accepted.job_id)
    assert view.state is AttemptState.SUCCEEDED
    identity = boundary(q, org, accepted.job_id)
    assert DRIVER.confirm_empty(identity)
    with q.engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT label FROM wq_fixture_results")).all()
    assert rows == [("TEST_INFRASTRUCTURE_ARTIFACT",)]
    claims = [e for e in q.audit_events(accepted.job_id) if e["event_type"] == "ATTEMPT_CLAIMED"]
    assert len(claims) == 1


def test_timeout_stops_the_child_and_its_descendants(q, org, supervisors):  # WQ-T12
    supervisors()
    accepted = submit(q, org, {"sleep_s": 60, "spawn_descendant": True})
    wait_for(lambda: q.get_job(org, accepted.job_id).attempts[0].execution_boundary is not None)
    identity = boundary(q, org, accepted.job_id)
    wait_for(lambda: len(DRIVER.members(identity)) >= 2)
    t0 = time.monotonic()
    wait_for(terminal(q, org, accepted.job_id))
    assert time.monotonic() - t0 < PROFILE["allocation_total_s"] + 1.5
    assert state(q, org, accepted.job_id) is AttemptState.TIMED_OUT
    assert DRIVER.confirm_empty(identity)


def test_cancel_running_work_stops_the_real_child(q, org, supervisors):  # WQ-T21
    supervisors()
    accepted = submit(q, org, {"sleep_s": 60})
    wait_for(lambda: q.get_job(org, accepted.job_id).attempts[0].execution_boundary is not None)
    identity = boundary(q, org, accepted.job_id)
    q.cancel(org, accepted.job_id, "cancel")
    wait_for(terminal(q, org, accepted.job_id), timeout=5)
    assert state(q, org, accepted.job_id) is AttemptState.CANCELLED
    assert DRIVER.confirm_empty(identity)


def test_primary_really_stops_by_cutoff_and_fallback_publishes(q, org, supervisors):  # WQ-T15
    supervisors()
    accepted = submit(
        q,
        org,
        contract="test.forecast.v1",
        payload={"fallback_allowed": True, "primary": {"sleep_s": 60}, "fallback": {}},
    )
    wait_for(terminal(q, org, accepted.job_id))
    view = q.get_job(org, accepted.job_id)
    assert view.state is AttemptState.SUCCEEDED
    attempt = view.attempts[0]
    elapsed = (attempt.completed_at - attempt.started_at).total_seconds()
    assert PROFILE["forecast_primary_cutoff_s"] - 1 < elapsed < PROFILE["forecast_total_s"]
    with q.engine.connect() as conn:
        payload = conn.scalar(
            sa.text("SELECT payload FROM wq_fixture_results WHERE attempt_id = :a"),
            {"a": attempt.attempt_id},
        )
    assert [s["status"] for s in payload["steps"]] == ["TIMED_OUT", "COMPLETED"]
    assert payload["steps"][0]["elapsed_s"] <= PROFILE["forecast_primary_cutoff_s"]


def test_sigterm_ignoring_primary_really_exits_by_the_cutoff(q, org, supervisors):  # F1
    supervisors()
    accepted = submit(
        q,
        org,
        contract="test.forecast.v1",
        payload={
            "fallback_allowed": True,
            "primary": {"sleep_s": 60, "ignore_sigterm": True, "spawn_descendant": True},
            "fallback": {},
        },
    )
    wait_for(terminal(q, org, accepted.job_id))
    view = q.get_job(org, accepted.job_id)
    assert view.state is AttemptState.SUCCEEDED
    with q.engine.connect() as conn:
        payload = conn.scalar(
            sa.text("SELECT payload FROM wq_fixture_results WHERE attempt_id = :a"),
            {"a": view.attempts[0].attempt_id},
        )
    primary = payload["steps"][0]
    assert primary["status"] == "TIMED_OUT"
    assert primary["elapsed_s"] <= PROFILE["forecast_primary_cutoff_s"]
    assert "cutoff_breach_s" not in primary


def test_supervisor_sigkill_recovers_orphans_and_never_recomputes(q, org, supervisors):  # T13
    first = supervisors()
    running = submit(q, org, {"sleep_s": 60, "spawn_descendant": True})
    waiting = submit(q, org)
    wait_for(lambda: q.get_job(org, running.job_id).attempts[0].execution_boundary is not None)
    identity = boundary(q, org, running.job_id)
    wait_for(lambda: len(DRIVER.members(identity)) >= 2)
    first.kill()  # real crash: no shutdown code runs
    # The leader dies with its parent (PDEATHSIG); its descendant is orphaned in the group.
    wait_for(lambda: identity.leader_pid not in DRIVER.members(identity), timeout=5)
    assert DRIVER.members(identity), "expected an orphaned descendant"
    # Compute is unavailable until a new owner recovers the lane.
    time.sleep(PROFILE["heartbeat_stale_s"] + 0.3)
    with pytest.raises(Exception) as err:
        submit(q, org)
    assert getattr(err.value, "code", "") == "COMPUTE_UNAVAILABLE"
    supervisors()
    wait_for(lambda: state(q, org, running.job_id) is AttemptState.INTERRUPTED, timeout=10)
    assert DRIVER.confirm_empty(identity)
    evidence = q.get_job(org, running.job_id).attempts[0].diagnostics["recovery_evidence"]
    assert evidence["method"] == "PROCESS_GROUP_KILLED"
    wait_for(terminal(q, org, waiting.job_id))
    assert state(q, org, waiting.job_id) is AttemptState.SUCCEEDED
    assert len(q.get_job(org, running.job_id).attempts) == 1
    retried = q.retry(org, running.job_id, "manual-retry")
    wait_for(terminal(q, org, running.job_id))
    view = q.get_job(org, running.job_id)
    assert [a.attempt_number for a in view.attempts] == [1, 2]
    assert view.current_attempt_id == retried.attempt_id
    assert view.attempts[1].state is AttemptState.TIMED_OUT  # same saved input, same behavior


def test_drain_and_restart_retain_queued_work(q, org, supervisors):  # WQ-T10/T22
    sup = supervisors()
    active = submit(q, org, {"sleep_s": 1.0})
    wait_for(lambda: state(q, org, active.job_id) is AttemptState.RUNNING)
    queued = submit(q, org)
    sup.signal(signal.SIGTERM)  # drain
    assert sup.wait(20) == 0
    assert state(q, org, active.job_id) is AttemptState.SUCCEEDED
    assert state(q, org, queued.job_id) is AttemptState.QUEUED
    assert q.control().state is SupervisorState.OFFLINE
    supervisors()
    wait_for(terminal(q, org, queued.job_id))
    assert state(q, org, queued.job_id) is AttemptState.SUCCEEDED


def test_immediate_stop_interrupts_and_confirms_cleanup(q, org, supervisors):  # WQ-T22
    sup = supervisors()
    active = submit(q, org, {"sleep_s": 60, "spawn_descendant": True})
    wait_for(lambda: q.get_job(org, active.job_id).attempts[0].execution_boundary is not None)
    identity = boundary(q, org, active.job_id)
    wait_for(lambda: len(DRIVER.members(identity)) >= 2)
    sup.signal(signal.SIGINT)
    assert sup.wait(20) == 0
    assert state(q, org, active.job_id) is AttemptState.INTERRUPTED
    assert DRIVER.confirm_empty(identity)
    assert q.control().active_attempt_id is None
