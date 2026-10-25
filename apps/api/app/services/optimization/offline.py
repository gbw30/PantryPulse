"""Offline execution using the same controlled children as the durable supervisor."""

import sys
import time
from pathlib import Path
from uuid import uuid4

from app.schemas.or_outputs import MethodOutcome
from app.services.jobs.contracts import PRODUCTION_PROFILE, canonical_json
from app.services.optimization.canonical import operational_hash
from app.services.optimization.service import DEFAULT_SETTINGS
from app.workers.process_driver import PosixProcessDriver
from app.workers.publication import step_outcome

API_ROOT = Path(__file__).resolve().parents[3]


def bounded_methods(scenario, methods, settings=None, profile=PRODUCTION_PROFILE):
    """No DB mutation; whole methods/pair include startup, checking and cleanup."""
    settings = dict(settings or DEFAULT_SETTINGS)
    driver = PosixProcessDriver(cwd=API_ROOT)
    if not driver.capable:
        raise RuntimeError("PROCESS_CONTAINMENT_UNAVAILABLE")
    started = time.monotonic()
    pair_end = started + (
        profile.comparison_total_s if len(methods) == 2 else profile.allocation_total_s
    )
    contract = "or-comparison-v1" if len(methods) == 2 else "or-allocation-v1"
    payload = {
        "scenario_id": str(uuid4()),
        "scenario": scenario.model_dump(mode="json"),
        "settings": settings,
        "method": None if len(methods) == 2 else methods[0],
        "org_epoch": 0,
    }
    outcomes = []
    for method in methods:
        method_start = time.monotonic()
        hard_end = min(pair_end, method_start + profile.method_wall_s)
        soft_end = hard_end - profile.stop_grace_s
        force_end = hard_end - profile.kill_margin_s
        envelope = {
            "input": payload,
            "prior": [],
            "context": {
                "job_id": str(uuid4()),
                "attempt_id": str(uuid4()),
                "remaining_s": hard_end - method_start,
                "search_limit_s": min(profile.method_search_s, hard_end - method_start - 3),
            },
        }
        handle = driver.start(
            [
                sys.executable,
                "-m",
                "app.workers.child",
                "--registry",
                "production",
                "--contract",
                contract,
                "--step",
                method,
            ],
            canonical_json(envelope).encode(),
            max_stdout_bytes=8 * 1024**2,
        )
        stopped = False
        try:
            while time.monotonic() < soft_end:
                if driver.poll(handle) is not None and driver.confirm_empty(handle.identity):
                    break
                time.sleep(0.01)
            if driver.poll(handle) is None or not driver.confirm_empty(handle.identity):
                stopped = True
                driver.request_stop(handle)
                while time.monotonic() < force_end:
                    if driver.poll(handle) is not None and driver.confirm_empty(handle.identity):
                        break
                    time.sleep(0.01)
                if driver.poll(handle) is None or not driver.confirm_empty(handle.identity):
                    driver.force_stop(handle)
                while time.monotonic() < hard_end:
                    if driver.poll(handle) is not None and driver.confirm_empty(handle.identity):
                        break
                    time.sleep(0.005)
            if not driver.confirm_empty(handle.identity):
                raise RuntimeError("CLEANUP_UNCONFIRMED")
            output = driver.collect(handle, timeout_s=max(0, min(0.1, hard_end - time.monotonic())))
            step = step_outcome(
                method,
                output,
                timed_out=stopped,
                overflowed=output.overflow,
                elapsed_s=time.monotonic() - method_start,
                hard_stop_s=hard_end - method_start,
            )
            if step.output is not None:
                outcome = MethodOutcome.model_validate(step.output)
                # Parent independently replays after child exit, just like durable publication.
                from app.services.optimization.candidates import prepare_problem
                from app.services.optimization.verify import verify

                if outcome.outcome == "VERIFIED":
                    checked = verify(prepare_problem(scenario), outcome.candidate, method)
                    if not checked.passed or checked != outcome.verification:
                        raise ValueError("PARENT_CHECK_FAILED")
            else:
                outcome = MethodOutcome(
                    method=method,
                    transfer_mode=scenario.transfer_mode,
                    operational_hash=scenario.operational_hash,
                    policy_hash=scenario.policy_hash,
                    settings_hash=operational_hash(settings),
                    decision_ids=scenario.decision_ids,
                    native_status=None,
                    outcome="TIMED_OUT" if stopped else "FAILED",
                    candidate=None,
                    verification=None,
                    objective=None,
                    error_code=step.error_code,
                )
            if time.monotonic() >= hard_end:
                outcome = MethodOutcome(
                    method=method,
                    transfer_mode=scenario.transfer_mode,
                    operational_hash=scenario.operational_hash,
                    policy_hash=scenario.policy_hash,
                    settings_hash=operational_hash(settings),
                    decision_ids=scenario.decision_ids,
                    native_status=None,
                    outcome="TIMED_OUT",
                    candidate=None,
                    verification=None,
                    objective=None,
                    error_code="METHOD_DEADLINE_EXCEEDED",
                )
            outcomes.append(outcome)
        finally:
            driver.dispose(handle)
    return tuple(outcomes)
