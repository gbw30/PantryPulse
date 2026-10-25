"""Pair assembly rejects mixed identities and forged verification across all states."""

from pathlib import Path

import pytest

from app.schemas.or_inputs import ORScenarioPayload, Rational
from app.services.optimization.compare import assemble
from app.services.optimization.service import DEFAULT_SETTINGS, solve_one

DATA = Path(__file__).resolve().parents[4] / "data/demo/or-v2"


@pytest.fixture(scope="module")
def pair():
    scenario = ORScenarioPayload.model_validate_json(
        (DATA / "six-beneficiary-v2.snapshot.json").read_text()
    )
    return scenario, tuple(
        solve_one(scenario, name) for name in ("CLASSICAL_GP", "EGP_PI_INSPIRED")
    )


def failed(outcome, *, built=True):
    return outcome.model_copy(
        update={
            "native_status": "UNKNOWN",
            "outcome": "FAILED",
            "candidate": None,
            "verification": None,
            "objective": None,
            "error_code": "MODEL_UNKNOWN",
            "physical_fingerprint": outcome.physical_fingerprint if built else None,
        }
    )


@pytest.mark.parametrize("states", [(True, True), (True, False), (False, True), (False, False)])
@pytest.mark.parametrize(
    "field,value",
    [
        ("operational_hash", "a" * 64),
        ("policy_hash", "b" * 64),
        ("settings_hash", "c" * 64),
        ("transfer_mode", "HUB_AND_PANTRY"),
        ("historical", True),
        ("decision_ids", ("OR-DEC-001",)),
        ("physical_fingerprint", "d" * 64),
    ],
)
def test_mixed_pair_metadata_is_rejected_even_when_a_method_failed(pair, states, field, value):
    scenario, original = pair
    outcomes = [item if keep else failed(item) for item, keep in zip(original, states, strict=True)]
    outcomes[1] = outcomes[1].model_copy(update={field: value})
    with pytest.raises(ValueError, match="PAIRED_"):
        assemble(scenario, outcomes)


def test_same_forged_policy_hash_in_both_outcomes_is_not_the_scenario_policy(pair):
    scenario, outcomes = pair
    with pytest.raises(ValueError, match="PAIRED_"):
        assemble(
            scenario,
            tuple(failed(item).model_copy(update={"policy_hash": "f" * 64}) for item in outcomes),
        )


@pytest.mark.parametrize("states", [(True, True), (True, False), (False, True), (False, False)])
def test_consistent_pairs_keep_valid_independent_outcomes(pair, states):
    scenario, original = pair
    outcomes = tuple(
        item if keep else failed(item, built=False)
        for item, keep in zip(original, states, strict=True)
    )
    result = assemble(scenario, outcomes, expected_settings=DEFAULT_SETTINGS)
    assert result.outcome == (
        "SUCCEEDED" if all(states) else "PARTIAL" if any(states) else "FAILED"
    )
    assert result.methods == outcomes
    assert bool(result.common_differences) == all(states)


def test_pair_can_check_the_callers_expected_settings(pair):
    scenario, outcomes = pair
    with pytest.raises(ValueError, match="PAIRED_"):
        assemble(scenario, outcomes, expected_settings={**DEFAULT_SETTINGS, "seed": 7})


def test_verified_results_require_a_real_model_fingerprint(pair):
    scenario, outcomes = pair
    with pytest.raises(ValueError, match="PAIRED_"):
        assemble(
            scenario,
            tuple(item.model_copy(update={"physical_fingerprint": None}) for item in outcomes),
        )


@pytest.mark.parametrize("forgery", ["objective", "metrics", "candidate"])
def test_pair_replays_verified_results_instead_of_trusting_passed_true(pair, forgery):
    scenario, outcomes = pair
    first = outcomes[0]
    if forgery == "objective":
        first = first.model_copy(update={"objective": Rational.of(first.objective.fraction() + 1)})
    elif forgery == "metrics":
        metrics = first.verification.metrics.model_copy(update={"W": Rational.of(999)})
        first = first.model_copy(
            update={"verification": first.verification.model_copy(update={"metrics": metrics})}
        )
    else:
        transfer = first.candidate.assignments[0]
        candidate = first.candidate.model_copy(
            update={
                "assignments": (
                    transfer.model_copy(update={"units": transfer.units + 1}),
                    *first.candidate.assignments[1:],
                )
            }
        )
        first = first.model_copy(update={"candidate": candidate})
    with pytest.raises(ValueError, match="PAIRED_"):
        assemble(scenario, (first, outcomes[1]))


@pytest.mark.parametrize("field", ["physical_fingerprint", "settings_hash"])
def test_pair_rejects_consistent_forged_model_or_expected_settings(pair, field):
    scenario, outcomes = pair
    with pytest.raises(ValueError, match="PAIRED_"):
        assemble(
            scenario,
            tuple(item.model_copy(update={field: "e" * 64}) for item in outcomes),
            expected_settings=DEFAULT_SETTINGS,
        )


@pytest.mark.parametrize("field", ["physical_fingerprint", "settings_hash"])
def test_pair_rejects_malformed_identity_even_when_both_failed(pair, field):
    scenario, outcomes = pair
    with pytest.raises(ValueError, match="PAIRED_"):
        assemble(
            scenario,
            tuple(failed(item).model_copy(update={field: "invalid"}) for item in outcomes),
        )
