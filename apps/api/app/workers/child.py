"""Step child entrypoint: ``python -m app.workers.child --registry R --contract C --step S``.

Reads one bounded JSON envelope on stdin and writes one JSON result on stdout. The child
owns no database connection, heartbeat, job state or publication. The registry name comes
from supervisor configuration and the contract from the claimed job; both are looked up in
fixed allowlists, never imported from a payload.
"""

import argparse
import ctypes
import json
import os
import signal
import sys
import traceback
import uuid
from typing import Any

PR_SET_PDEATHSIG = 1


def _bind_to_parent() -> None:
    """Ask the kernel to SIGKILL this leader if the supervisor dies (Linux)."""
    if not sys.platform.startswith("linux"):
        return
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL)
    expected = os.environ.get("PP_WQ_PARENT_PID")
    if expected is not None and os.getppid() != int(expected):
        os._exit(70)  # the supervisor already died before the death signal was armed


def _emit(result: dict[str, Any]) -> None:
    from app.services.jobs.contracts import canonical_json

    try:
        text = canonical_json(result)
    except (TypeError, ValueError):
        text = canonical_json(
            {"status": "FAILED", "error_code": "OUTPUT_INVALID", "fallback_eligible": False}
        )
    sys.stdout.write(text)
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    _bind_to_parent()
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--step", required=True)
    args = parser.parse_args(argv)

    from app.services.jobs.registry import (
        ClassifiedStepFailure,
        ExecutionContext,
        InputRejected,
        UnregisteredContract,
    )
    from app.workers.registries import load_registry

    try:
        registration = load_registry(args.registry).get(args.contract)
    except (UnregisteredContract, ValueError):
        _emit(
            {"status": "FAILED", "error_code": "UNREGISTERED_CONTRACT", "fallback_eligible": False}
        )
        return 0
    try:
        envelope = json.loads(sys.stdin.buffer.read(registration.max_input_bytes * 2 + 4096))
        validated = registration.handler.validate_input(envelope["input"])
        context = envelope["context"]
        ctx = ExecutionContext(
            job_id=uuid.UUID(context["job_id"]),
            attempt_id=uuid.UUID(context["attempt_id"]),
            step=args.step,
            remaining_s=float(context["remaining_s"]),
            search_limit_s=float(context["search_limit_s"]),
        )
        prior = envelope.get("prior", [])
    except (InputRejected, KeyError, TypeError, ValueError):
        _emit({"status": "FAILED", "error_code": "INPUT_INTEGRITY", "fallback_eligible": False})
        return 0
    try:
        output = registration.handler.execute_step(args.step, validated, prior, ctx)
    except ClassifiedStepFailure as exc:
        _emit(
            {
                "status": "FAILED",
                "error_code": exc.code,
                "fallback_eligible": exc.fallback_eligible,
            }
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - programming errors are reported, never hidden
        traceback.print_exc(limit=5, file=sys.stderr)
        _emit(
            {
                "status": "FAILED",
                "error_code": "HANDLER_FAILED",
                "fallback_eligible": False,
                "exception_type": type(exc).__name__,
            }
        )
        return 0
    _emit({"status": "COMPLETED", "output": output})
    return 0


if __name__ == "__main__":
    sys.exit(main())
