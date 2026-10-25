"""Operator commands for the compute lane (ADR 0004 A1).

    python -m app.workers.admin status
    python -m app.workers.admin attest-cleanup --attempt UUID --operator REF --note TEXT

Attestation is recorded as OPERATOR_ATTESTATION evidence, never as automatic proof. Use it
only after confirming outside PantryPulse (for example, the old worker container was
removed) that the recorded execution boundary no longer exists.
"""

import argparse
import os
import sys
import uuid

from app.repositories.jobs import QueueRepository, create_queue_engine
from app.services.jobs.contracts import PRODUCTION_PROFILE, canonical_json
from app.services.jobs.registry import Registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--schema", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    attest = sub.add_parser("attest-cleanup")
    attest.add_argument("--attempt", required=True, type=uuid.UUID)
    attest.add_argument("--operator", required=True)
    attest.add_argument("--note", required=True)
    args = parser.parse_args(argv)
    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URL is required")
    repo = QueueRepository(
        create_queue_engine(url, schema=args.schema),
        registry=Registry([]),
        profile=PRODUCTION_PROFILE,
    )
    if args.command == "status":
        ctl = repo.control()
        print(
            canonical_json(
                {
                    "lane_id": ctl.lane_id,
                    "state": ctl.state.value,
                    "generation": ctl.generation,
                    "heartbeat_at": ctl.heartbeat_at.isoformat() if ctl.heartbeat_at else None,
                    "active_attempt_id": str(ctl.active_attempt_id)
                    if ctl.active_attempt_id
                    else None,
                    "recovery_required": ctl.recovery_required,
                }
            )
        )
        return 0
    state = repo.operator_attest_cleanup(args.attempt, args.operator, args.note)
    print(canonical_json({"attempt_id": str(args.attempt), "state": state.value}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
