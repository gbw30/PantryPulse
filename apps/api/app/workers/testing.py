"""Fixed test handlers for queue infrastructure evidence (ADR 0004 A6).

Loaded only through the named ``test`` registry. Their outputs are test infrastructure
artifacts: never a forecast, allocation, feasible plan or research result. Behaviors are
chosen from a closed set; a payload cannot name a command, path or import.
"""

import os
import signal
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from typing import Any

from app.services.jobs.contracts import (
    OperationKind,
    RuntimeProfile,
    StepOutcome,
    StepSpec,
    StepStatus,
    canonical_json,
)
from app.services.jobs.policies import allocation_steps, comparison_steps, forecast_steps
from app.services.jobs.registry import (
    ClassifiedStepFailure,
    ExecutionContext,
    InputRejected,
    PublicationIdentity,
    PublicationRejected,
    Registration,
    Registry,
)
from app.services.solver_outcomes import classify_solver_status

FIXTURE_LABEL = "TEST_INFRASTRUCTURE_ARTIFACT"

# Created only by tests in their isolated schema; never by a production migration.
FIXTURE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS wq_fixture_results (
    attempt_id uuid PRIMARY KEY,
    job_id uuid NOT NULL,
    label text NOT NULL CHECK (label = 'TEST_INFRASTRUCTURE_ARTIFACT'),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
)
"""

_FAIL_MODES = (None, "classified", "error", "crash")
_BEHAVIOR_KEYS = {
    "sleep_s",
    "fail",
    "spawn_descendant",
    "ignore_sigterm",
    "output_bytes",
    "native_status",
}


def _behavior(raw: Any) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping) or set(raw) - _BEHAVIOR_KEYS:
        raise InputRejected("INVALID_INPUT", "behavior must be an object with known keys")
    sleep_s = raw.get("sleep_s", 0)
    if isinstance(sleep_s, bool) or not isinstance(sleep_s, int | float) or not 0 <= sleep_s <= 600:
        raise InputRejected("INVALID_INPUT", "sleep_s must be within [0, 600]")
    if raw.get("fail") not in _FAIL_MODES:
        raise InputRejected("INVALID_INPUT", "unknown fail mode")
    output_bytes = raw.get("output_bytes", 0)
    if isinstance(output_bytes, bool) or not isinstance(output_bytes, int):
        raise InputRejected("INVALID_INPUT", "output_bytes must be an int")
    if not 0 <= output_bytes <= 1_000_000:
        raise InputRejected("INVALID_INPUT", "output_bytes out of range")
    for flag in ("spawn_descendant", "ignore_sigterm"):
        if not isinstance(raw.get(flag, False), bool):
            raise InputRejected("INVALID_INPUT", f"{flag} must be a bool")
    status = raw.get("native_status", "OPTIMAL")
    if not isinstance(status, str):
        raise InputRejected("INVALID_INPUT", "native_status must be a string")
    return {
        "sleep_s": float(sleep_s),
        "fail": raw.get("fail"),
        "spawn_descendant": raw.get("spawn_descendant", False),
        "ignore_sigterm": raw.get("ignore_sigterm", False),
        "output_bytes": output_bytes,
        "native_status": status,
    }


def _run_behavior(behavior: Mapping[str, Any]) -> str:
    if behavior["ignore_sigterm"]:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if behavior["spawn_descendant"]:
        # Same process group as the step child: containment must stop it too.
        subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(600)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    deadline = time.monotonic() + behavior["sleep_s"]
    while time.monotonic() < deadline:
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    if behavior["fail"] == "classified":
        raise ClassifiedStepFailure("TEST_PROVIDER_FAILURE")
    if behavior["fail"] == "error":
        raise RuntimeError("test programming error")
    if behavior["fail"] == "crash":
        os._exit(3)
    return "x" * behavior["output_bytes"]


def _only_keys(payload: Any, allowed: set[str]) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping) or set(payload) - allowed:
        raise InputRejected("INVALID_INPUT", f"input must be an object with keys {sorted(allowed)}")
    return payload


class EchoHandler:
    """Single-method ALLOCATION-shaped fixture."""

    def validate_input(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        payload = _only_keys(payload, {"value", "behavior", "publish_fail"})
        value = payload.get("value")
        if isinstance(value, bool) or not isinstance(value, int):
            raise InputRejected("INVALID_INPUT", "value must be an int")
        publish_fail = payload.get("publish_fail", False)
        if not isinstance(publish_fail, bool):
            raise InputRejected("INVALID_INPUT", "publish_fail must be a bool")
        return {
            "value": value,
            "behavior": _behavior(payload.get("behavior")),
            "publish_fail": publish_fail,
        }

    def steps(self, validated: Mapping[str, Any], profile: RuntimeProfile) -> tuple[StepSpec, ...]:
        return allocation_steps(profile, "TEST_METHOD")

    def execute_step(
        self,
        step: str,
        validated: Mapping[str, Any],
        prior: Sequence[Mapping[str, Any]],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        pad = _run_behavior(validated["behavior"])
        return {"value": validated["value"], "label": FIXTURE_LABEL, "pad": pad}


class ForecastFixtureHandler:
    """Primary/fallback FORECAST-shaped fixture; providers are labeled test stand-ins."""

    def validate_input(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        payload = _only_keys(payload, {"fallback_allowed", "primary", "fallback"})
        allowed = payload.get("fallback_allowed")
        if not isinstance(allowed, bool):
            raise InputRejected("INVALID_INPUT", "fallback_allowed must be a bool")
        return {
            "fallback_allowed": allowed,
            "primary": _behavior(payload.get("primary")),
            "fallback": _behavior(payload.get("fallback")),
        }

    def steps(self, validated: Mapping[str, Any], profile: RuntimeProfile) -> tuple[StepSpec, ...]:
        return forecast_steps(profile, fallback_allowed=validated["fallback_allowed"])

    def execute_step(
        self,
        step: str,
        validated: Mapping[str, Any],
        prior: Sequence[Mapping[str, Any]],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        _run_behavior(validated[step])
        output: dict[str, Any] = {"provider": f"test-{step}", "label": FIXTURE_LABEL}
        if step == "fallback":
            output["fallback_reason"] = prior[-1]["error_code"] if prior else None
        return output


class ComparisonFixtureHandler:
    """Two sequential method fixtures on one frozen input."""

    def validate_input(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        payload = _only_keys(payload, {"methods"})
        methods = payload.get("methods", {})
        _only_keys(methods, {"CLASSICAL_GP", "EGP_PI_INSPIRED"})
        return {
            "methods": {m: _behavior(methods.get(m)) for m in ("CLASSICAL_GP", "EGP_PI_INSPIRED")}
        }

    def steps(self, validated: Mapping[str, Any], profile: RuntimeProfile) -> tuple[StepSpec, ...]:
        return comparison_steps(profile)

    def execute_step(
        self,
        step: str,
        validated: Mapping[str, Any],
        prior: Sequence[Mapping[str, Any]],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        behavior = validated["methods"][step]
        _run_behavior(behavior)
        return {
            "method": step,
            "native_status": behavior["native_status"],
            "search_limit_s": context.search_limit_s,
            "label": FIXTURE_LABEL,
        }


class FixturePublisher:
    """Validates staged fixture outcomes and writes them to the test-only results table."""

    def __init__(self, kind: str):
        self.kind = kind

    def validate(
        self, validated: Mapping[str, Any], outcomes: Sequence[StepOutcome]
    ) -> dict[str, Any]:
        completed = [o for o in outcomes if o.status is StepStatus.COMPLETED]
        if self.kind == "comparison":
            methods = []
            for o in outcomes:
                entry: dict[str, Any] = {"method": o.name, "step_status": o.status.value}
                if o.status is StepStatus.COMPLETED:
                    if not isinstance(o.output, Mapping) or o.output.get("label") != FIXTURE_LABEL:
                        raise PublicationRejected("OUTPUT_INVALID")
                    try:
                        gate = classify_solver_status(o.output.get("native_status"))
                    except (TypeError, ValueError):
                        raise PublicationRejected("OUTPUT_INVALID") from None
                    entry["native_status"] = gate.native_status.value
                    entry["candidate_readable"] = gate.may_read_candidate
                else:
                    entry["reason"] = o.error_code
                methods.append(entry)
            if not completed:
                raise PublicationRejected(
                    "HANDLER_FAILED",
                    timed_out=all(o.status is StepStatus.TIMED_OUT for o in outcomes),
                )
            return {"kind": "comparison", "methods": methods, "publish_fail": False}
        if not completed:
            last = outcomes[-1] if outcomes else None
            raise PublicationRejected(
                last.error_code if last and last.error_code else "HANDLER_FAILED",
                timed_out=bool(last) and last.status is StepStatus.TIMED_OUT,
            )
        final = completed[-1]
        if not isinstance(final.output, Mapping) or final.output.get("label") != FIXTURE_LABEL:
            raise PublicationRejected("OUTPUT_INVALID")
        package: dict[str, Any] = {
            "kind": self.kind,
            "outputs": [{k: v for k, v in final.output.items() if k != "pad"}],
            "steps": [o.summary() for o in outcomes],
            "publish_fail": bool(validated.get("publish_fail", False)),
        }
        return package

    def publish(
        self, connection: Any, identity: PublicationIdentity, package: Mapping[str, Any]
    ) -> dict[str, Any]:
        from sqlalchemy import text

        connection.execute(
            text(
                "INSERT INTO wq_fixture_results (attempt_id, job_id, label, payload)"
                " VALUES (:a, :j, :l, CAST(:p AS jsonb))"
            ),
            {
                "a": identity.attempt_id,
                "j": identity.job_id,
                "l": FIXTURE_LABEL,
                "p": canonical_json(dict(package)),
            },
        )
        if package.get("publish_fail"):
            raise PublicationRejected("PUBLICATION_REJECTED")
        return {
            "label": FIXTURE_LABEL,
            "kind": package["kind"],
            "result_ref": str(identity.attempt_id),
        }


REGISTRY = Registry(
    [
        Registration(
            contract="test.echo.v1",
            operation_kind=OperationKind.ALLOCATION,
            input_schema_version="1",
            max_input_bytes=16_384,
            max_output_bytes=65_536,
            handler=EchoHandler(),
            publisher=FixturePublisher("echo"),
        ),
        Registration(
            contract="test.forecast.v1",
            operation_kind=OperationKind.FORECAST,
            input_schema_version="1",
            max_input_bytes=16_384,
            max_output_bytes=65_536,
            handler=ForecastFixtureHandler(),
            publisher=FixturePublisher("forecast"),
        ),
        Registration(
            contract="test.comparison.v1",
            operation_kind=OperationKind.COMPARISON,
            input_schema_version="1",
            max_input_bytes=16_384,
            max_output_bytes=65_536,
            handler=ComparisonFixtureHandler(),
            publisher=FixturePublisher("comparison"),
        ),
    ]
)
