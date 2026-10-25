"""Real Linux boundaries beyond the withdrawn 25-second method deadline."""

import os
import time
from uuid import uuid4

import pytest

from app.repositories.jobs import QueueRepository, TrustedScope
from app.services.jobs.contracts import PRODUCTION_PROFILE, AttemptState
from app.workers.process_driver import PosixProcessDriver, linux_containment_available
from app.workers.supervisor import Supervisor, SupervisorConfig
from app.workers.testing import REGISTRY

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not linux_containment_available(), reason="Requires real Linux process control"
    ),
]


def test_native_boundary_survives_old_deadline_and_drains_cleanly(db):
    queue = QueueRepository(db, registry=REGISTRY, profile=PRODUCTION_PROFILE)
    driver = PosixProcessDriver(cwd=os.getcwd())
    supervisor = Supervisor(queue, REGISTRY, driver, SupervisorConfig("test", PRODUCTION_PROFILE))
    assert supervisor.start()
    scope = TrustedScope(uuid4(), "long-boundary-test")
    try:
        accepted = queue.submit(
            scope, "test.echo.v1", {"value": 7, "behavior": {"sleep_s": 31}}, str(uuid4())
        )
        started = time.monotonic()
        observed_after_old_deadline = False
        while time.monotonic() - started < 45:
            supervisor.tick()
            view = queue.get_job(scope, accepted.job_id)
            if time.monotonic() - started > 26 and view.state == AttemptState.RUNNING:
                observed_after_old_deadline = True
            if view.state == AttemptState.SUCCEEDED:
                break
            time.sleep(0.05)
        assert observed_after_old_deadline
        assert view.state == AttemptState.SUCCEEDED
        attempt = view.attempts[-1]
        assert (attempt.execution_deadline_at - attempt.started_at).total_seconds() == 330
        assert queue.control().active_attempt_id is None
        supervisor.shutdown_drain()
    finally:
        supervisor.close()
