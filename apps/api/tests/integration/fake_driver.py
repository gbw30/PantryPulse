"""Deterministic in-memory execution boundary for supervisor tests (WQ-03 "explicit fakes").

It runs the registered fixture handler with its sleep removed and models the sleep, SIGTERM
handling, forced stops and cleanup confirmation on the monotonic clock. It is not process
containment evidence; the Linux driver has its own real-process tests.
"""

import json
import time
import uuid
from dataclasses import dataclass, field

from app.services.jobs.contracts import canonical_json
from app.services.jobs.registry import ClassifiedStepFailure, ExecutionContext
from app.workers.process_driver import BoundaryIdentity, ChildOutput


@dataclass
class FakeHandle:
    identity: BoundaryIdentity
    step: str
    finish_at: float
    stdout: bytes
    final_rc: int
    ignore_term: bool
    max_stdout: int
    term_sent: bool = False
    killed: bool = False
    returncode: int | None = None


@dataclass
class FakeDriver:
    registry: object
    clock: object = time.monotonic
    capable: bool = True
    stuck_steps: set = field(default_factory=set)
    unkillable_steps: set = field(default_factory=set)
    foreign_evidence: dict | None = field(default_factory=lambda: {"method": "FAKE_GROUP_SCAN"})
    fail_spawn: bool = False
    started: list = field(default_factory=list)
    foreign_checked: list = field(default_factory=list)

    def host_identity_text(self) -> str:
        return "fake-host"

    def start(self, argv, stdin_bytes, *, max_stdout_bytes, max_stderr_bytes=16_384):
        if self.fail_spawn:
            raise OSError("spawn failed")
        contract = argv[argv.index("--contract") + 1]
        step = argv[argv.index("--step") + 1]
        envelope = json.loads(stdin_bytes)
        reg = self.registry.get(contract)
        validated = reg.handler.validate_input(envelope["input"])
        behavior = _behavior_for(validated, step)
        quiet = {**behavior, "sleep_s": 0, "spawn_descendant": False, "ignore_sigterm": False}
        runnable = _with_behavior(validated, step, quiet)
        rc = 0
        if behavior["fail"] == "crash":
            stdout, rc = b"", 3
        else:
            try:
                output = reg.handler.execute_step(
                    step,
                    runnable,
                    envelope["prior"],
                    ExecutionContext(
                        job_id=uuid.UUID(envelope["context"]["job_id"]),
                        attempt_id=uuid.UUID(envelope["context"]["attempt_id"]),
                        step=step,
                        remaining_s=envelope["context"]["remaining_s"],
                        search_limit_s=envelope["context"]["search_limit_s"],
                    ),
                )
                result = {"status": "COMPLETED", "output": output}
            except ClassifiedStepFailure as exc:
                result = {
                    "status": "FAILED",
                    "error_code": exc.code,
                    "fallback_eligible": exc.fallback_eligible,
                }
            except Exception:  # noqa: BLE001
                result = {"status": "FAILED", "error_code": "HANDLER_FAILED"}
            stdout = canonical_json(result).encode()
        identity = BoundaryIdentity(
            boot_id="fake-boot",
            pid_namespace="fake-ns",
            pgid=10_000 + len(self.started),
            leader_pid=10_000 + len(self.started),
            leader_start_ticks=1,
            nonce=str(uuid.uuid4()),
        )
        handle = FakeHandle(
            identity=identity,
            step=step,
            finish_at=self.clock() + behavior["sleep_s"],
            stdout=stdout,
            final_rc=rc,
            ignore_term=behavior["ignore_sigterm"],
            max_stdout=max_stdout_bytes,
        )
        self.started.append(handle)
        return handle

    def poll(self, handle):
        if handle.step in self.unkillable_steps:
            return None  # e.g. uninterruptible sleep: even SIGKILL does not land
        if handle.returncode is None:
            if handle.killed:
                handle.returncode = -9
            elif handle.term_sent and not handle.ignore_term:
                handle.returncode = -15
            elif self.clock() >= handle.finish_at:
                handle.returncode = handle.final_rc
        return handle.returncode

    def request_stop(self, handle):
        handle.term_sent = True

    def force_stop(self, handle):
        handle.killed = True

    def confirm_empty(self, identity):
        handle = next(h for h in self.started if h.identity == identity)
        return handle.returncode is not None and handle.step not in self.stuck_steps

    def collect(self, handle, timeout_s=2.0):
        clean = handle.returncode == handle.final_rc and not handle.killed
        data = handle.stdout if clean else b""
        return ChildOutput(
            stdout=data[: handle.max_stdout],
            stderr=b"",
            overflow=len(data) > handle.max_stdout,
            returncode=handle.returncode,
        )

    def dispose(self, handle):
        pass

    def cleanup_foreign(self, identity, *, timeout_s):
        self.foreign_checked.append(identity)
        return self.foreign_evidence


def _behavior_for(validated, step):
    if "methods" in validated:
        return validated["methods"][step]
    if step in ("primary", "fallback"):
        return validated[step]
    return validated["behavior"]


def _with_behavior(validated, step, behavior):
    if "methods" in validated:
        return {**validated, "methods": {**validated["methods"], step: behavior}}
    if step in ("primary", "fallback"):
        return {**validated, step: behavior}
    return {**validated, "behavior": behavior}
