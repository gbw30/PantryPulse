"""Independent review regressions for source time, canonical replay and invalid vectors."""

import json
from datetime import date, datetime
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.schemas.or_inputs import ORInputPackage, ORScenarioPayload
from app.schemas.or_outputs import Candidate
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.canonical import canonical_bytes, operational_hash
from app.services.optimization.scenario import freeze_scenario, verify_scenario
from app.services.optimization.verify import verify

DATA = Path(__file__).resolve().parents[4] / "data/demo/or-v1"


def valid_snapshot():
    raw = json.loads((DATA / "six-beneficiary-v1.snapshot.json").read_text())
    package = raw["package"]
    as_of = datetime.fromisoformat(package["snapshot_as_of"])
    snapshot_day = as_of.astimezone(ZoneInfo(package["operational_timezone"])).date()
    # Older synthetic fixtures used the planning date for original on-hand stock.
    # Prepare an actually available original stock set independently of those dates.
    for lot in package["inventory"]:
        lot["available_on"] = min(date.fromisoformat(lot["available_on"]), snapshot_day)
    package = ORInputPackage.model_validate(package)
    original = ORScenarioPayload.model_validate(raw)
    return freeze_scenario(
        package,
        original.policy,
        transfer_mode=original.transfer_mode,
        planning_days=original.planning_days,
        modifiers=original.modifiers,
        intent=original.intent,
        expected_source_revision=package.source_revision_token,
    )


def test_canonical_snapshot_roundtrip_replays_with_same_identity():
    # OR-DEC-009 [PROVISIONAL]: unordered identity arrays have canonical semantics.
    scenario = valid_snapshot()
    restored = ORScenarioPayload.model_validate_json(canonical_bytes(scenario))
    assert restored.operational_hash == scenario.operational_hash
    verify_scenario(restored)


def test_reordering_unordered_product_records_preserves_replay():
    scenario = valid_snapshot()
    reordered = scenario.model_copy(
        update={
            "package": scenario.package.model_copy(
                update={"products": scenario.package.products[::-1]}
            )
        }
    )
    assert operational_hash(reordered.model_dump(exclude={"operational_hash"})) == (
        scenario.operational_hash
    )
    verify_scenario(reordered)


def test_rehashed_derived_demand_tampering_is_still_rejected():
    scenario = valid_snapshot()
    series = scenario.demand[0]
    point = series.days[0].model_copy(update={"units": series.days[0].units + 1})
    series = series.model_copy(update={"days": (point, *series.days[1:])})
    changed = scenario.model_copy(update={"demand": (series, *scenario.demand[1:])})
    changed = changed.model_copy(
        update={
            "operational_hash": operational_hash(changed.model_dump(exclude={"operational_hash"}))
        }
    )
    with pytest.raises(ValueError, match="SCENARIO_DERIVATION_MISMATCH"):
        verify_scenario(changed)


@pytest.mark.parametrize("dispatchable", [False, True])
def test_original_on_hand_must_exist_by_snapshot_day(dispatchable):
    # OR-DEC-005 [PROVISIONAL]: a future resource cannot assert current physical stock.
    raw = valid_snapshot().package.model_dump()
    raw["inventory"][0].update(available_on=raw["first_planning_date"], dispatchable=dispatchable)
    with pytest.raises(ValidationError, match="FUTURE_ON_HAND_STOCK"):
        ORInputPackage.model_validate(raw)


def test_on_hand_snapshot_cutoff_uses_network_local_date():
    raw = valid_snapshot().package.model_dump()
    raw["snapshot_as_of"] = datetime.fromisoformat("2026-10-25T01:00:00+00:00")
    raw["inventory"][0]["available_on"] = date(2026, 10, 25)
    assert raw["snapshot_as_of"].date() == raw["inventory"][0]["available_on"]
    with pytest.raises(ValidationError, match="FUTURE_ON_HAND_STOCK"):
        ORInputPackage.model_validate(raw)


@pytest.mark.parametrize("timezone", ["Invalid/Zone", ""])
def test_invalid_operational_timezone_is_a_structured_validation_error(timezone):
    raw = valid_snapshot().package.model_dump()
    raw["operational_timezone"] = timezone
    with pytest.raises(ValidationError, match="Unknown operational timezone"):
        ORInputPackage.model_validate(raw)


def test_on_hand_local_date_may_be_ahead_of_utc_date():
    raw = valid_snapshot().package.model_dump()
    raw["operational_timezone"] = "Pacific/Kiritimati"
    for row in (*raw["sites"], *raw["forecasts"]):
        row["timezone"] = raw["operational_timezone"]
    raw["inventory"][0]["available_on"] = date(2026, 10, 25)
    package = ORInputPackage.model_validate(raw)
    assert package.inventory[0].available_on > package.snapshot_as_of.date()


def test_future_confirmed_arrival_remains_supported():
    raw = valid_snapshot().package.model_dump()
    stock = raw["inventory"][0]
    raw["confirmed_arrivals"] = (
        {
            "id": UUID(int=8001),
            "source_line_id": UUID(int=8002),
            "site_id": stock["site_id"],
            "product_id": stock["product_id"],
            "unit": stock["unit"],
            "units": 1,
            "available_on": raw["first_planning_date"],
            "expires_on": stock["expires_on"],
            "eligibility": "ELIGIBLE",
            "confirmed": True,
            "already_posted": False,
            "source_revision": "review-v1",
        },
    )
    package = ORInputPackage.model_validate(raw)
    assert package.confirmed_arrivals[0].available_on > package.snapshot_as_of.date()


@pytest.mark.parametrize("malformed", [0.1, None, "wrong-shape"])
def test_invalid_model_copy_has_structured_failure_without_invented_hash(malformed):
    # OR-DEC-009 [PROVISIONAL]: only validated content receives a candidate identity.
    problem = prepare_problem(valid_snapshot())
    candidate = Candidate(route_quantities=(), assignments=()).model_copy(
        update={"route_quantities": malformed}
    )
    report = verify(problem, candidate)
    assert report.passed is False
    assert report.violations
    assert report.candidate_hash is None
    assert report.projection is None and report.metrics is None


def test_invalid_mapping_candidate_has_structured_failure():
    report = verify(prepare_problem(valid_snapshot()), {"route_quantities": 0.1, "assignments": []})
    assert report.passed is False
    assert report.candidate_hash is None


def test_valid_zero_candidate_retains_actual_identity():
    candidate = Candidate(route_quantities=(), assignments=())
    report = verify(prepare_problem(valid_snapshot()), candidate)
    assert report.passed is True
    assert report.candidate_hash == operational_hash(candidate)
