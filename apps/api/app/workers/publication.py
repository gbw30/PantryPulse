"""Staged step outcomes from bounded child transport (WQ-05).

The child returns one JSON object; anything else, oversized output or output that arrives
after its step was stopped is never treated as a publishable result.
"""

import json
import re

from app.services.jobs.contracts import ReasonCode, StepOutcome, StepStatus
from app.workers.process_driver import ChildOutput

_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")


def reason_for(code: str) -> ReasonCode:
    try:
        return ReasonCode(code)
    except ValueError:
        return ReasonCode.PUBLICATION_REJECTED


def step_outcome(
    name: str,
    output: ChildOutput,
    *,
    timed_out: bool,
    overflowed: bool,
    elapsed_s: float,
    hard_stop_s: float,
) -> StepOutcome:
    """``elapsed_s`` is when the supervisor observed exit; past ``hard_stop_s`` it is a
    recorded cutoff breach and the output, if any, is not publishable (spec §9.3)."""
    elapsed = round(elapsed_s, 3)
    breach = round(elapsed_s - hard_stop_s, 3)
    if breach > 0:
        return StepOutcome(
            name,
            StepStatus.TIMED_OUT,
            error_code=ReasonCode.STEP_DEADLINE_EXCEEDED.value,
            fallback_eligible=True,
            elapsed_s=elapsed,
            details={"cutoff_breach_s": breach},
        )
    if timed_out:
        # Late raw output is discarded; a stopped primary may make fallback eligible.
        return StepOutcome(
            name,
            StepStatus.TIMED_OUT,
            error_code=ReasonCode.STEP_DEADLINE_EXCEEDED.value,
            fallback_eligible=True,
            elapsed_s=elapsed,
        )
    if overflowed or output.overflow:
        return StepOutcome(
            name, StepStatus.FAILED, error_code=ReasonCode.OUTPUT_TOO_LARGE.value, elapsed_s=elapsed
        )
    try:
        result = json.loads(output.stdout) if output.returncode == 0 else None
    except (ValueError, UnicodeDecodeError):
        result = None
    if not isinstance(result, dict):
        return StepOutcome(
            name,
            StepStatus.FAILED,
            error_code=ReasonCode.CHILD_EXITED_ABNORMALLY.value,
            elapsed_s=elapsed,
            details={"returncode": output.returncode},
        )
    if result.get("status") == "COMPLETED" and isinstance(result.get("output"), dict):
        return StepOutcome(name, StepStatus.COMPLETED, output=result["output"], elapsed_s=elapsed)
    code = result.get("error_code")
    if result.get("status") != "FAILED" or not isinstance(code, str) or not _CODE.fullmatch(code):
        return StepOutcome(
            name, StepStatus.FAILED, error_code=ReasonCode.OUTPUT_INVALID.value, elapsed_s=elapsed
        )
    return StepOutcome(
        name,
        StepStatus.FAILED,
        error_code=code,
        fallback_eligible=result.get("fallback_eligible") is True,
        elapsed_s=elapsed,
    )
