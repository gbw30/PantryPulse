"""OR-only bounded file/child execution. No dependency on shared jobs or workers."""

import json
import sys
import time

from app.schemas.or_outputs import MethodOutcome
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.canonical import operational_hash
from app.services.optimization.process import run_child
from app.services.optimization.service import DEFAULT_SETTINGS
from app.services.optimization.verify import verify


def bounded_methods(scenario, methods, settings=None):
    # OR-DEC-011 [PROVISIONAL]: offline limits; shared application runtime is external.
    if methods not in (
        ("CLASSICAL_GP",),
        ("EGP_PI_INSPIRED",),
        ("CLASSICAL_GP", "EGP_PI_INSPIRED"),
    ):
        raise ValueError("EXACT_OFFLINE_METHODS_REQUIRED")
    settings = dict(DEFAULT_SETTINGS if settings is None else settings)
    pair_end = time.monotonic() + (60 if len(methods) == 2 else 25)
    outcomes = []
    for method in methods:
        identity = dict(
            method=method,
            transfer_mode=scenario.transfer_mode,
            operational_hash=scenario.operational_hash,
            policy_hash=scenario.policy_hash,
            settings_hash=operational_hash(settings),
            decision_ids=scenario.decision_ids,
            historical=scenario.intent == "HISTORICAL_REPLAY",
        )
        deadline = min(pair_end, time.monotonic() + 25)
        request = json.dumps(
            {"scenario": scenario.model_dump(mode="json"), "method": method, "settings": settings},
            allow_nan=False,
        ).encode()
        result = run_child(
            [sys.executable, "-m", "app.services.optimization._child"], request, deadline=deadline
        )
        failure = result.reason or ("CHILD_PROCESS_FAILED" if result.returncode else None)
        if not failure:
            try:
                outcome = MethodOutcome.model_validate_json(result.stdout)
                if any(getattr(outcome, key) != value for key, value in identity.items()):
                    raise ValueError("CHILD_IDENTITY_MISMATCH")
                if outcome.outcome == "VERIFIED":
                    checked = verify(prepare_problem(scenario), outcome.candidate, method)
                    objective = (
                        (
                            checked.metrics.classical_objective
                            if method == "CLASSICAL_GP"
                            else checked.metrics.research_objective
                        )
                        if checked.passed
                        else None
                    )
                    if (
                        not checked.passed
                        or checked != outcome.verification
                        or objective != outcome.objective
                    ):
                        raise ValueError("PARENT_CHECK_FAILED")
                outcomes.append(outcome)
                continue
            except (ValueError, TypeError, AttributeError):
                failure = "INVALID_CHILD_OUTPUT"
        outcomes.append(
            MethodOutcome(
                **identity,
                native_status=None,
                outcome="TIMED_OUT" if failure == "DEADLINE_EXCEEDED" else "FAILED",
                candidate=None,
                verification=None,
                objective=None,
                error_code=failure,
            )
        )
    return tuple(outcomes)
