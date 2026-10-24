"""BE-05 (BACKEND-SPEC.md section 13.5): native status gate before vector access.

The sentinel tests below validate the gate flags only. They drive a fake caller from the
returned record; they are not evidence of solver correctness.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from app.services.solver_outcomes import classify_solver_status

# Hand-written section 13.5 table: status -> (may_read_candidate, requires_verification).
STATUS_TABLE = {
    "OPTIMAL": (True, True),
    "FEASIBLE": (True, True),
    "INFEASIBLE": (False, False),
    "UNKNOWN": (False, False),
    "MODEL_INVALID": (False, False),
}
DISALLOWED = ["INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
PERMITTED = ["OPTIMAL", "FEASIBLE"]


@pytest.mark.parametrize(("status", "flags"), sorted(STATUS_TABLE.items()))
def test_status_table_rows(status, flags):
    outcome = classify_solver_status(status)
    assert outcome.native_status == status
    assert str(outcome.native_status) == status
    assert outcome.may_read_candidate is flags[0]
    assert outcome.requires_independent_verification is flags[1]


def test_feasible_keeps_exact_label_and_is_not_optimal():
    outcome = classify_solver_status("FEASIBLE")
    assert outcome.native_status == "FEASIBLE"
    assert outcome.native_status != "OPTIMAL"
    assert outcome != classify_solver_status("OPTIMAL")


def test_every_status_maps_to_a_distinct_record():
    outcomes = {classify_solver_status(s) for s in STATUS_TABLE}
    assert len(outcomes) == 5


def test_record_is_immutable():
    outcome = classify_solver_status("FEASIBLE")
    with pytest.raises(AttributeError):
        outcome.native_status = "OPTIMAL"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        outcome.may_read_candidate = False  # type: ignore[misc]
    with pytest.raises(AttributeError):
        outcome.requires_independent_verification = False  # type: ignore[misc]
    assert outcome.native_status == "FEASIBLE"
    assert outcome.may_read_candidate is True


def test_deterministic():
    assert classify_solver_status("UNKNOWN") == classify_solver_status("UNKNOWN")


@pytest.mark.parametrize(
    "bad",
    [
        "optimal",
        "Optimal",
        "feasible",
        "Feasible",
        "model_invalid",
        " OPTIMAL",
        "OPTIMAL ",
        "OPTIMAL\n",
        "\tFEASIBLE",
        "",
        "MODEL-INVALID",
        "TIMEOUT",
        "CANCELLED",
        "ERROR",
        "UNSPECIFIED",
    ],
)
def test_unknown_case_and_whitespace_variants_raise_value_error(bad):
    with pytest.raises(ValueError) as info:
        classify_solver_status(bad)
    assert not isinstance(info.value, TypeError)


@pytest.mark.parametrize("bad", [None, 0, 4, True, False, 4.0, b"OPTIMAL", ["OPTIMAL"], object()])
def test_non_string_raises_type_error(bad):
    with pytest.raises(TypeError):
        classify_solver_status(bad)


# ---- Sentinel gate tests (gate-only evidence) ----


class _ForbiddenReader:
    """Fake vector reader that fails the test if accessed."""

    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        raise AssertionError("candidate vector accessed for a disallowed status")


class _Recorder:
    def __init__(self):
        self.events: list[tuple[str, object]] = []


def _fake_caller(status, read_candidate, verify, publish):
    """Caller following the section 13.5 contract using only the gate record."""
    outcome = classify_solver_status(status)
    if not outcome.may_read_candidate:
        return outcome, None
    candidate = read_candidate()
    if outcome.requires_independent_verification and not verify(candidate):
        return outcome, None
    publish(candidate)
    return outcome, candidate


@pytest.mark.parametrize("status", DISALLOWED)
def test_disallowed_status_never_touches_vector_reader(status):
    reader = _ForbiddenReader()
    rec = _Recorder()
    outcome, candidate = _fake_caller(
        status,
        reader,
        verify=lambda c: rec.events.append(("verify", c)) or True,
        publish=lambda c: rec.events.append(("publish", c)),
    )
    assert reader.calls == 0
    assert candidate is None
    assert rec.events == []
    assert outcome.may_read_candidate is False


@pytest.mark.parametrize("status", PERMITTED)
def test_permitted_candidate_reaches_verifier_before_publisher(status):
    rec = _Recorder()
    vector = (("lot-1", 3),)

    def read():
        rec.events.append(("read", vector))
        return vector

    def verify(candidate):
        rec.events.append(("verify", candidate))
        return True

    def publish(candidate):
        rec.events.append(("publish", candidate))

    outcome, candidate = _fake_caller(status, read, verify, publish)
    assert [name for name, _ in rec.events] == ["read", "verify", "publish"]
    assert candidate == vector
    assert outcome.native_status == status


@pytest.mark.parametrize("status", PERMITTED)
def test_permitted_candidate_failing_verification_is_not_published(status):
    rec = _Recorder()
    outcome, candidate = _fake_caller(
        status,
        read_candidate=lambda: (("lot-1", 99),),
        verify=lambda c: rec.events.append(("verify", c)) or False,
        publish=lambda c: rec.events.append(("publish", c)),
    )
    assert [name for name, _ in rec.events] == ["verify"]
    assert candidate is None


def test_module_imports_no_solver_or_database_packages():
    api_root = Path(__file__).resolve().parents[1]
    code = (
        "import sys, app.services.solver_outcomes; "
        "bad = [m for m in ('ortools', 'sqlalchemy', 'chronos', 'torch', 'psycopg') "
        "if m in sys.modules]; "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=api_root, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
