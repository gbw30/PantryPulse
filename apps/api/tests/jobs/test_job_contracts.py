"""WQ-01 internal job contracts: vocabulary, runtime profile and canonical input identity."""

import dataclasses
import math
import subprocess
import sys
from pathlib import Path

import pytest

from app.services.jobs.contracts import (
    LANE_OCCUPYING_STATES,
    NONTERMINAL_STATES,
    PRODUCTION_PROFILE,
    RETRYABLE_STATES,
    TERMINAL_STATES,
    AttemptState,
    OperationKind,
    RuntimeProfile,
    StepSpec,
    SupervisorState,
    canonical_json,
    sha256_hex,
)

API_ROOT = Path(__file__).resolve().parents[2]


def test_attempt_vocabulary_includes_provisional_partial_comparison_state():
    # OR-DEC-016 [PROVISIONAL]: PARTIAL is a terminal reviewed domain outcome.
    assert {s.value for s in AttemptState} == {
        "QUEUED",
        "RUNNING",
        "STOPPING",
        "SUCCEEDED",
        "PARTIAL",
        "FAILED",
        "TIMED_OUT",
        "INTERRUPTED",
        "CANCELLED",
        "EXPIRED",
    }
    assert {s.value for s in TERMINAL_STATES} == {
        "SUCCEEDED",
        "PARTIAL",
        "FAILED",
        "TIMED_OUT",
        "INTERRUPTED",
        "CANCELLED",
        "EXPIRED",
    }
    assert {s.value for s in NONTERMINAL_STATES} == {"QUEUED", "RUNNING", "STOPPING"}
    assert {s.value for s in LANE_OCCUPYING_STATES} == {"RUNNING", "STOPPING"}
    assert {s.value for s in RETRYABLE_STATES} == {
        "PARTIAL",
        "FAILED",
        "TIMED_OUT",
        "INTERRUPTED",
        "EXPIRED",
        "CANCELLED",
    }


def test_unknown_or_lowercase_state_values_are_rejected():
    for bad in ("queued", "DONE", " QUEUED", ""):
        with pytest.raises(ValueError):
            AttemptState(bad)
    assert {k.value for k in OperationKind} == {"FORECAST", "ALLOCATION", "COMPARISON"}
    assert {s.value for s in SupervisorState} == {
        "OFFLINE",
        "STARTING",
        "READY",
        "DRAINING",
        "RECOVERING",
        "QUARANTINED",
    }


def test_production_profile_holds_every_accepted_v5_ceiling():
    p = PRODUCTION_PROFILE
    assert p.max_queued == 2
    assert p.queue_wait_s == 900
    assert p.forecast_total_s == 300
    assert p.forecast_primary_cutoff_s == 270
    assert p.method_search_s == 15
    assert p.method_wall_s == 25
    assert p.allocation_total_s == 25
    assert p.comparison_total_s == 60
    assert p.heartbeat_interval_s == 5
    assert p.heartbeat_stale_s == 15
    assert p.worker_cpu == 6
    assert p.worker_memory_gib == 8
    assert p.stop_grace_s == 2


@pytest.mark.parametrize(
    "change",
    [
        {"queue_wait_s": 0},
        {"queue_wait_s": -1},
        {"queue_wait_s": math.inf},
        {"queue_wait_s": math.nan},
        {"max_queued": -1},
        {"max_queued": 2.5},
        {"max_queued": True},
        {"heartbeat_interval_s": 15},
        {"method_search_s": 26},
        {"forecast_primary_cutoff_s": 300},
        {"stop_grace_s": 0},
        {"publication_reserve_s": 25},
        {"method_wall_s": 61},
    ],
)
def test_inconsistent_profiles_are_rejected(change):
    with pytest.raises(ValueError):
        dataclasses.replace(PRODUCTION_PROFILE, **change)


def test_effective_limits_are_versioned_and_contain_no_secrets():
    limits = PRODUCTION_PROFILE.effective_limits()
    assert limits["version"] == 1
    assert limits["limits"]["queue_wait_s"] == 900
    assert limits["limits"]["worker_memory_gib"] == 8
    assert "database" not in canonical_json(limits).lower()


def test_short_profiles_are_explicit_and_valid():
    short = RuntimeProfile(
        queue_wait_s=3,
        heartbeat_interval_s=0.2,
        heartbeat_stale_s=1,
        forecast_total_s=6,
        forecast_primary_cutoff_s=3,
        allocation_total_s=4,
        method_wall_s=4,
        method_search_s=2,
        comparison_total_s=6,
        stop_grace_s=0.3,
        publication_reserve_s=0.5,
        method_min_s=0.5,
    )
    assert short.queue_wait_s == 3


def test_canonical_json_is_order_independent_and_compact():
    assert (
        canonical_json({"b": 1, "a": [1, {"d": 2, "c": "é"}]}) == '{"a":[1,{"c":"é","d":2}],"b":1}'
    )
    assert sha256_hex({"b": 1, "a": 2}) == sha256_hex({"a": 2, "b": 1})
    # Independent value: sha256 of the bytes '{"a":2,"b":1}'.
    assert sha256_hex({"a": 2, "b": 1}) == (
        "d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772"
    )


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, {1: "x"}, {"a": object()}, b"x"])
def test_canonical_json_rejects_non_finite_and_non_json_values(bad):
    with pytest.raises((ValueError, TypeError)):
        canonical_json(bad)


def test_step_spec_requires_positive_bounds_and_a_name():
    with pytest.raises(ValueError):
        StepSpec(name="", min_s=1)
    with pytest.raises(ValueError):
        StepSpec(name="x", min_s=0)
    with pytest.raises(ValueError):
        StepSpec(name="x", min_s=1, max_s=0)
    with pytest.raises(ValueError):
        StepSpec(name="x", min_s=1, cutoff_s=-1)


@pytest.mark.parametrize(
    "module",
    ["app.services.jobs.contracts", "app.services.jobs.policies", "app.services.jobs.registry"],
)
def test_pure_job_modules_import_no_database_solver_or_model_packages(module):
    forbidden = ("ortools", "sqlalchemy", "chronos", "torch", "psycopg")
    code = (
        f"import sys, {module}; "
        f"bad = [m for m in {forbidden!r} if m in sys.modules]; "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=API_ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_profile_may_be_shorter_but_never_longer_than_the_ceiling():
    shorter = dataclasses.replace(PRODUCTION_PROFILE, queue_wait_s=60)
    assert shorter.within(PRODUCTION_PROFILE)
    longer = dataclasses.replace(PRODUCTION_PROFILE, comparison_total_s=61)
    assert not longer.within(PRODUCTION_PROFILE)
    more_waiters = dataclasses.replace(PRODUCTION_PROFILE, max_queued=3)
    assert not more_waiters.within(PRODUCTION_PROFILE)


@pytest.mark.parametrize("margin", [0, 2, 3])
def test_kill_margin_must_fit_inside_the_stop_grace(margin):
    with pytest.raises(ValueError):
        dataclasses.replace(PRODUCTION_PROFILE, kill_margin_s=margin)


def test_production_kill_margin_is_recorded():
    assert PRODUCTION_PROFILE.kill_margin_s == 0.25
    assert PRODUCTION_PROFILE.effective_limits()["limits"]["kill_margin_s"] == 0.25
