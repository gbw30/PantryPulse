"""Linux browser-test fault injection, restricted to an isolated demo's exact boundary.

Run in the worker's PID namespace. This never changes queue state or publication data;
the production supervisor observes a real child failure and publishes the survivor.
"""
import argparse
import os
import sys
import time
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/api"))

import sqlalchemy as sa

from app.models.jobs import compute_attempts as attempts, compute_jobs as jobs
from app.models.operational import Organization
from app.repositories.jobs import create_queue_engine
from app.workers.process_driver import BoundaryIdentity, PosixProcessDriver


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id", type=UUID)
    args = parser.parse_args()
    schema = os.environ["PP_DATABASE_SCHEMA"]
    if not schema.startswith("ppor_demo_"):
        parser.error("Only explicitly isolated ppor_demo_* schemas are allowed")
    engine = create_queue_engine(os.environ["DATABASE_URL"], schema=schema)
    driver = PosixProcessDriver(cwd=Path(__file__).resolve().parents[2] / "apps/api")
    end = time.monotonic() + 60
    try:
        while time.monotonic() < end:
            with engine.connect() as conn:
                row = conn.execute(sa.select(
                    jobs.c.handler_contract, attempts.c.state, attempts.c.current_phase,
                    attempts.c.execution_boundary, Organization.is_demo,
                ).select_from(jobs.join(attempts, jobs.c.current_attempt_id == attempts.c.attempt_id)
                    .join(Organization, jobs.c.organization_id == Organization.id))
                    .where(jobs.c.job_id == args.job_id)).mappings().one()
            if not row["is_demo"] or row["handler_contract"] != "or-comparison.v2":
                raise RuntimeError("Not an isolated demo comparison")
            if row["state"] == "RUNNING" and row["current_phase"] == "EGP_PI_INSPIRED" and row["execution_boundary"]:
                identity = BoundaryIdentity.from_json(row["execution_boundary"])
                evidence = driver.cleanup_foreign(identity, timeout_s=2)
                if not evidence or evidence.get("method") != "PROCESS_GROUP_KILLED":
                    raise RuntimeError("Exact live partner boundary could not be terminated")
                print("Terminated the identified demo partner; supervisor owns cleanup/publication.")
                return
            if row["state"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
                raise RuntimeError("Comparison ended before fault injection")
            time.sleep(0.02)
        raise TimeoutError("Partner did not start")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
