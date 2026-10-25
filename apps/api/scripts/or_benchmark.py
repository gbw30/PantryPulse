"""Real persisted queue submissions and saved reads; never invokes an inline solver."""

import argparse
import os
import platform
import statistics
import time
from uuid import UUID, uuid4

import sqlalchemy as sa

from app.models.or_records import PlanRecord, ScenarioRecord
from app.repositories.jobs import TrustedScope
from app.repositories.or_repository import ORRepository
from app.services.jobs.contracts import TERMINAL_STATES
from app.services.optimization.service import DEFAULT_SETTINGS
from app.services.or_runtime import ORRuntime
from scripts.or_common import write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-id", type=UUID, required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.runs <= 20:
        parser.error("runs must be 1–20")
    active = ORRuntime.from_environment()
    if active is None:
        parser.error("DATABASE_URL and running shared supervisor required")
    organization = UUID(os.environ["PP_PRESENTER_ORGANIZATION_ID"])
    actor = os.environ["PP_PRESENTER_ACTOR_ID"]
    scope = TrustedScope(organization, actor)
    with active.engine.connect() as connection:
        row = ORRepository(connection).get(ScenarioRecord, organization, args.scenario_id)
    payload = {
        "scenario_id": str(args.scenario_id),
        "scenario": row["payload"],
        "settings": DEFAULT_SETTINGS,
        "method": None,
        "org_epoch": row["org_epoch"],
    }
    results = []
    for _ in range(args.runs):
        started = time.monotonic()
        accepted = active.queue.submit(scope, "or-comparison-v1", payload, str(uuid4()))
        deadline = started + 965
        while time.monotonic() < deadline:
            job = active.queue.get_job(scope, accepted.job_id)
            if job.state in TERMINAL_STATES:
                break
            time.sleep(0.025)
        else:
            raise RuntimeError("BENCHMARK_JOB_DID_NOT_TERMINATE")
        elapsed = time.monotonic() - started
        read_started = time.monotonic()
        with active.engine.connect() as connection:
            plans = (
                connection.execute(
                    sa.select(PlanRecord.result).where(PlanRecord.job_id == accepted.job_id)
                )
                .scalars()
                .all()
            )
        read_seconds = time.monotonic() - read_started
        results.append(
            {
                "job_id": str(accepted.job_id),
                "state": job.state.value,
                "job_wall_seconds": elapsed,
                "saved_read_seconds": read_seconds,
                "methods": [
                    {
                        "method": plan["method"],
                        "native_status": plan["native_status"],
                        "total_seconds": plan["total_seconds"],
                        "objective": plan["objective"],
                    }
                    for plan in plans
                ],
            }
        )
    methods = [method["total_seconds"] for row in results for method in row["methods"]]
    saved = [row["saved_read_seconds"] for row in results]
    write(
        args.output,
        {
            "execution": "DURABLE_POSTGRESQL_QUEUE",
            "runs": args.runs,
            "platform": platform.platform(),
            "logical_cpu_count": os.cpu_count(),
            "operational_hash": payload["scenario"]["operational_hash"],
            "policy_hash": payload["scenario"]["policy_hash"],
            "settings": DEFAULT_SETTINGS,
            "effective_limits": active.queue.control().effective_limits,
            "memory_peak_bytes": None,
            "memory_note": "Use supervisor resource evidence separately",
            "median_method_seconds": statistics.median(methods) if methods else None,
            "maximum_method_seconds": max(methods, default=None),
            "median_saved_read_seconds": statistics.median(saved),
            "maximum_saved_read_seconds": max(saved),
            "samples": results,
        },
    )
    active.engine.dispose()
    return 0 if all(row["state"] == "SUCCEEDED" for row in results) else 4


if __name__ == "__main__":
    raise SystemExit(main())
