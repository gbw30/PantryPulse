"""BE-05 (BACKEND-SPEC.md section 13.5): native status gate before vector access.

The sentinel tests below validate the gate flags only. They drive a fake caller from the
returned record; they are not evidence of solver correctness.
"""

from unittest.mock import Mock

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
    with pytest.raises(ValueError):
        classify_solver_status(bad)


@pytest.mark.parametrize("bad", [None, 0, 4, True, False, 4.0, b"OPTIMAL", ["OPTIMAL"], object()])
def test_non_string_raises_type_error(bad):
    with pytest.raises(TypeError):
        classify_solver_status(bad)


# ---- Sentinel gate tests (gate-only evidence) ----


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
    # The reader raises if it is ever called; verify/publish must not run either.
    caller = Mock()
    caller.read.side_effect = AssertionError("candidate vector accessed for a disallowed status")
    outcome, candidate = _fake_caller(status, caller.read, caller.verify, caller.publish)
    assert caller.mock_calls == []
    assert candidate is None
    assert outcome.may_read_candidate is False


@pytest.mark.parametrize("status", PERMITTED)
def test_permitted_candidate_reaches_verifier_before_publisher(status):
    vector = (("lot-1", 3),)
    caller = Mock()
    caller.read.return_value = vector
    caller.verify.return_value = True
    outcome, candidate = _fake_caller(status, caller.read, caller.verify, caller.publish)
    assert [name for name, _, _ in caller.mock_calls] == ["read", "verify", "publish"]
    caller.verify.assert_called_once_with(vector)
    caller.publish.assert_called_once_with(vector)
    assert candidate == vector
    assert outcome.native_status == status


@pytest.mark.parametrize("status", PERMITTED)
def test_permitted_candidate_failing_verification_is_not_published(status):
    caller = Mock()
    caller.read.return_value = (("lot-1", 99),)
    caller.verify.return_value = False
    outcome, candidate = _fake_caller(status, caller.read, caller.verify, caller.publish)
    assert [name for name, _, _ in caller.mock_calls] == ["read", "verify"]
    caller.publish.assert_not_called()
    assert candidate is None
