"""Seed a FIXTURE forecast run for a network the connected e2e imported (Escalation E-1).

The v1 forecast routes return 501 until W3-F03 merges (W4), and a scenario needs a forecast run.
This runs the W2-05 backend journey's FIXTURE_FORECAST job
(apps/api/tests/networks/test_build_scenario.py) on its own queue lane, so the production
worker keeps the default lane. The series come from a fixture forecast.json keyed by external
IDs. The run is a fixture and never forecast evidence; import, scenario, comparison, decisions
and export stay real. It reads DATABASE_URL and PP_DATABASE_SCHEMA, as db_probe.py does.
Usage: seed_forecast.py NETWORK_ID DATASET_VERSION_ID FORECAST_JSON  (prints the forecast_run_id)
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "api"))

import sqlalchemy as sa  # noqa: E402
import tests.integration.fake_driver as fake_driver  # noqa: E402
from app.repositories.jobs import QueueRepository, TrustedScope, create_queue_engine  # noqa: E402
from app.services.jobs.contracts import PRODUCTION_PROFILE, TERMINAL_STATES, AttemptState  # noqa: E402
from app.services.jobs.registry import Registry  # noqa: E402
from app.workers.supervisor import Supervisor, SupervisorConfig  # noqa: E402
from tests.enrichment.test_enrichment_job import QUIET  # noqa: E402
from tests.networks.test_build_scenario import FIXTURE_FORECAST, _forecast_output  # noqa: E402

LANE = "e2e_fixture"


def seed(
    engine: sa.Engine, network_id: uuid.UUID, version_id: uuid.UUID, series: list[dict]
) -> str:
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO compute_control (lane_id) VALUES (:l) ON CONFLICT DO NOTHING"),
            {"l": LANE},
        )
        as_of = conn.execute(
            sa.text("SELECT as_of_date FROM dataset_versions WHERE id = :v AND network_id = :n"),
            {"v": version_id, "n": network_id},
        ).scalar_one()
    network = SimpleNamespace(network_id=network_id, dataset_version_id=version_id)
    org, output = _forecast_output(engine, network, as_of, series)
    # The fixture job's one step does nothing; the in-process driver runs it without a child.
    fake_driver._behavior_for = lambda validated, step: QUIET
    fake_driver._with_behavior = lambda validated, step, behavior: validated
    registry = Registry([FIXTURE_FORECAST])
    queue = QueueRepository(engine, registry=registry, profile=PRODUCTION_PROFILE, lane_id=LANE)
    supervisor = Supervisor(
        queue,
        registry,
        fake_driver.FakeDriver(registry=registry),
        SupervisorConfig(registry_name="e2e-fixture", profile=PRODUCTION_PROFILE, tick_s=0.02),
    )
    if not supervisor.start():
        raise SystemExit(f"lane {LANE} is held by another live supervisor")
    try:
        scope = TrustedScope(org, "e2e-fixture")
        accepted = queue.submit(
            scope,
            FIXTURE_FORECAST.contract,
            {"dataset_id": str(version_id), "planning_ready": True, "output": output},
            str(uuid.uuid4()),
        )
        end = time.monotonic() + 60
        while (job := queue.get_job(scope, accepted.job_id)).state not in TERMINAL_STATES:
            if time.monotonic() > end:
                raise SystemExit("the fixture forecast run did not settle in 60 s")
            supervisor.tick()
            time.sleep(0.01)
        if job.state != AttemptState.SUCCEEDED:
            raise SystemExit(f"the fixture forecast run ended {job.state}")
        return job.attempts[-1].result_manifest["forecast_run_id"]
    finally:
        supervisor.shutdown_drain(timeout_s=5)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: seed_forecast.py NETWORK_ID DATASET_VERSION_ID FORECAST_JSON")
    series = json.loads(Path(sys.argv[3]).read_text())["series"]
    engine = create_queue_engine(
        os.environ["DATABASE_URL"], schema=os.environ["PP_DATABASE_SCHEMA"]
    )
    try:
        print(seed(engine, uuid.UUID(sys.argv[1]), uuid.UUID(sys.argv[2]), series))
    finally:
        engine.dispose()
