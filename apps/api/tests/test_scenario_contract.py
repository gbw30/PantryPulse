"""Strict frozen scenario identity; fixtures are deliberately reduced simulations."""

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.scenario import OperationalScenario, required_source_keys
from app.services.scenarios import assess_freshness, freeze_scenario

DAY = date(2026, 10, 24)


def uid(n):
    return UUID(int=n)


def scenario_data():
    dates = [DAY + timedelta(days=i) for i in range(7)]
    sites = []
    series = []
    for n, role in [(1, "HUB"), (2, "BENEFICIARY"), (3, "BENEFICIARY")]:
        sites.append(dict(
            site_id=uid(n), role=role, calendar_version_id=uid(100+n),
            timezone="America/New_York",
            receiving_capacity=[dict(day=d, handling_units=20) for d in dates],
            reserves=[dict(product_id=uid(10), day=d, quantity=0) for d in dates],
        ))
        series.append(dict(
            policy_version="projection-v1", snapshot_id=uid(200+n),
            organization_id=uid(99), site_id=uid(n), product_id=uid(10), base_unit="meal",
            timezone="America/New_York", calendar_version_id=uid(100+n),
            inventory_version=1, opening_on=DAY, forecast_id=uid(300+n),
            provider="SIMULATED_FIXTURE", planning_mode="CENTRAL", assumptions=["SIMULATED"],
            transfer_mode="HUB_AND_PANTRY", lots=[], commitments=[],
            demand=[dict(day=d, estimate=Decimal(0 if role == "HUB" else 10)) for d in dates],
        ))
    return dict(
        schema_version="scenario-v1", organization_id=uid(99),
        transfer_mode="HUB_AND_PANTRY", planning_timezone="America/New_York",
        horizon_start=DAY, allocation_start=DAY, allocation_days=2,
        network_site_ids=[uid(n) for n in range(1, 8)],
        excluded_sites=[dict(entity_id=uid(n), reason="SIMULATED_REDUCED_SCOPE")
                        for n in range(4, 8)],
        network_product_ids=[uid(10), uid(11)],
        excluded_products=[dict(entity_id=uid(11), reason="SIMULATED_REDUCED_SCOPE")],
        sites=sites, products=[dict(product_id=uid(10), base_unit="meal", handling_units=2)],
        series=series, routes=[dict(
            route_id=uid(400), origin_id=uid(1), destination_id=uid(2), enabled=True,
            transit_days=0, handling_capacity=20,
            unit_costs=[dict(product_id=uid(10), cost_ticks=3)],
        )],
        handling_unit_label="simulated handling unit", batch_handling_capacity=20,
        cost_unit_label="simulated movement tick",
        policy=dict(policy_id=uid(500), schema_version="fixture-policy-v1",
                    canonical_json='{"status":"FIXTURE_ONLY"}'),
        forecasts=[dict(forecast_id=s["forecast_id"], schema_version="fixture-forecast-v1",
                        canonical_json='{"actual_provider":"SIMULATED_FIXTURE"}') for s in series],
        assumptions_json='{"classification":"SIMULATED"}', sources=[],
    )


def make_scenario(**changes):
    data = scenario_data()
    data.update(changes)
    # The test builder derives manifest keys only, never production fingerprints.
    keys = required_source_keys(data)
    data["sources"] = [dict(kind=kind, key=key, version="fixture-1", content_hash="a"*64)
                       for kind, key in sorted(keys)]
    return OperationalScenario(**data)


def test_freeze_round_trip_and_replay_preserve_exact_operational_inputs():
    original = make_scenario()
    frozen = freeze_scenario(original)
    loaded = OperationalScenario.model_validate_json(frozen.canonical_json)
    assert freeze_scenario(loaded) == frozen
    assert len(frozen.content_hash) == 64
    assert loaded.series[1].demand[0].estimate == Decimal(10)


def test_collection_order_does_not_change_identity():
    original = make_scenario()
    changed = original.model_dump()
    for field in ("sites", "products", "series", "routes", "sources", "network_site_ids",
                  "network_product_ids", "excluded_sites", "excluded_products", "forecasts"):
        changed[field] = tuple(reversed(changed[field]))
    for site in changed["sites"]:
        site["reserves"] = tuple(reversed(site["reserves"]))
        site["receiving_capacity"] = tuple(reversed(site["receiving_capacity"]))
    assert freeze_scenario(OperationalScenario(**changed)) == freeze_scenario(original)


@pytest.mark.parametrize("field,value", [
    ("transfer_mode", "HUB_ONLY"), ("batch_handling_capacity", 21),
    ("assumptions_json", '{"classification":"SIMULATED","surge":"1.1"}'),
    ("allocation_days", 3), ("cost_unit_label", "different cost unit"),
])
def test_changed_operational_input_requires_new_identity(field, value):
    original = make_scenario()
    data = original.model_dump()
    data[field] = value
    if field == "transfer_mode":
        for series in data["series"]:
            series["transfer_mode"] = value
    assert freeze_scenario(OperationalScenario(**data)).content_hash != (
        freeze_scenario(original).content_hash
    )


@pytest.mark.parametrize("field,value", [
    ("transfer_mode", None), ("transfer_mode", "default"),
    ("allocation_days", 0), ("allocation_days", 4), ("allocation_days", True),
    ("allocation_start", DAY+timedelta(days=6)),
    ("planning_timezone", "Invalid/Zone"), ("batch_handling_capacity", -1),
    ("batch_handling_capacity", 0.5),
])
def test_invalid_operational_choices_rejected(field, value):
    with pytest.raises(ValidationError):
        make_scenario(**{field: value})


@pytest.mark.parametrize("modify", [
    lambda d: d["sites"].pop(),
    lambda d: d["excluded_sites"].pop(),
    lambda d: d["sites"].append(d["sites"][0]),
    lambda d: d["series"].pop(),
    lambda d: d["series"][0].update(organization_id=uid(999)),
    lambda d: d["series"][0].update(base_unit="bottle"),
    lambda d: d["series"][0].update(timezone="UTC"),
    lambda d: d["series"][0].update(calendar_version_id=uid(999)),
    lambda d: d["series"][0]["demand"].pop(),
    lambda d: d["sites"][0]["reserves"].pop(),
    lambda d: d["sites"][1]["receiving_capacity"].pop(),
    lambda d: d["routes"][0].update(destination_id=uid(999)),
    lambda d: d["routes"][0].update(destination_id=uid(1)),
    lambda d: d["routes"][0].update(transit_days=-1),
    lambda d: d["routes"][0]["unit_costs"].pop(),
])
def test_incomplete_scope_and_inconsistent_references_rejected(modify):
    data = scenario_data()
    modify(data)
    with pytest.raises(ValidationError):
        make_scenario(**data)


@pytest.mark.parametrize("text", [
    '{"x":0.1}', '{"x":NaN}', '{"x":1,"x":2}', '[]', '{ "x":1}',
])
def test_opaque_policy_or_assumptions_must_be_canonical_exact_json(text):
    with pytest.raises(ValidationError):
        make_scenario(assumptions_json=text)


def test_source_manifest_must_cover_every_dependency_without_duplicates():
    original = make_scenario().model_dump()
    original["sources"] = original["sources"][:-1]
    with pytest.raises(ValidationError):
        OperationalScenario(**original)
    original = make_scenario().model_dump()
    original["sources"] = (*original["sources"], original["sources"][0])
    with pytest.raises(ValidationError):
        OperationalScenario(**original)


def test_freshness_reports_changes_without_rewriting_historical_snapshot():
    frozen = freeze_scenario(make_scenario())
    before = frozen.canonical_json
    current = list(frozen.inputs.sources)
    assert assess_freshness(frozen, tuple(current), as_of_day=DAY).is_stale is False
    first = current[0]
    current[0] = first.model_copy(update={"version": "fixture-2"})
    report = assess_freshness(frozen, tuple(current), as_of_day=DAY)
    assert report.is_stale
    assert [(r.kind, r.key, r.reason) for r in report.changes] == [
        (first.kind, first.key, "CHANGED")
    ]
    assert frozen.canonical_json == before
    assert freeze_scenario(frozen.inputs) == frozen


def test_missing_and_new_dependencies_are_stale():
    frozen = freeze_scenario(make_scenario())
    current = list(frozen.inputs.sources)
    old = current.pop()
    added = old.model_copy(update={"key": "new-scoped-dependency"})
    current.append(added)
    report = assess_freshness(frozen, tuple(current), as_of_day=DAY)
    assert {r.reason for r in report.changes} == {"MISSING", "ADDED"}


def test_invalid_copy_cannot_bypass_freeze_validation():
    original = make_scenario().model_copy(update={"allocation_days": 99})
    with pytest.raises(ValidationError):
        freeze_scenario(original)


def test_elapsed_dispatch_date_changes_current_status_not_replay():
    frozen = freeze_scenario(make_scenario())
    report = assess_freshness(frozen, frozen.inputs.sources, as_of_day=DAY+timedelta(days=1))
    assert report.is_stale and report.window_elapsed
    assert report.changes == ()
    assert freeze_scenario(frozen.inputs) == frozen


def test_historical_hash_tampering_and_duplicate_live_tokens_rejected():
    from dataclasses import replace

    frozen = freeze_scenario(make_scenario())
    with pytest.raises(ValueError, match="fingerprint"):
        assess_freshness(replace(frozen, content_hash="0"*64), frozen.inputs.sources, as_of_day=DAY)
    with pytest.raises(ValueError, match="duplicate"):
        assess_freshness(frozen, (*frozen.inputs.sources, frozen.inputs.sources[0]), as_of_day=DAY)


def test_content_digest_change_without_version_bump_is_still_stale():
    frozen = freeze_scenario(make_scenario())
    current = list(frozen.inputs.sources)
    current[0] = current[0].model_copy(update={"content_hash": "b"*64})
    report = assess_freshness(frozen, tuple(current), as_of_day=DAY)
    assert report.is_stale
    assert report.changes[0].reason == "CHANGED"


def test_policy_and_forecast_payloads_are_frozen_and_affect_identity():
    original = make_scenario()
    changed = original.model_dump()
    changed["policy"]["canonical_json"] = '{"status":"FIXTURE_ONLY","weight":"0.5"}'
    assert freeze_scenario(OperationalScenario(**changed)).content_hash != (
        freeze_scenario(original).content_hash
    )
    changed = original.model_dump()
    changed["forecasts"][0]["canonical_json"] = (
        '{"actual_provider":"SIMULATED_FIXTURE","input_version":"changed"}'
    )
    assert freeze_scenario(OperationalScenario(**changed)).content_hash != (
        freeze_scenario(original).content_hash
    )


def test_forecast_reference_and_actual_provider_must_match():
    data = scenario_data()
    data["forecasts"].pop()
    with pytest.raises(ValidationError):
        make_scenario(**data)
    data = scenario_data()
    data["forecasts"][0]["canonical_json"] = '{"actual_provider":"different"}'
    with pytest.raises(ValidationError):
        make_scenario(**data)


def test_zero_capacity_and_high_reserve_are_valid_inputs_for_zero_transfer_case():
    # Hard feasibility is a candidate property. Scarcity alone is not bad input.
    data = scenario_data()
    data["batch_handling_capacity"] = 0
    data["routes"][0]["handling_capacity"] = 0
    for site in data["sites"]:
        for row in site["reserves"]:
            row["quantity"] = 100
    frozen = freeze_scenario(make_scenario(**data))
    assert frozen.inputs.batch_handling_capacity == 0
    assert frozen.inputs.sites[0].reserves[0].quantity == 100


def test_reduced_fixture_requires_its_explicit_exclusion_reasons():
    # Small contract fixtures explicitly exclude four; they are not primary-demo evidence.
    data = scenario_data()
    assert len(data["excluded_sites"]) == 4
    data["excluded_sites"] = []
    with pytest.raises(ValidationError):
        make_scenario(**data)


def test_numeric_scale_and_decimal_context_do_not_change_scenario_identity():
    from decimal import localcontext

    data = scenario_data()
    for series in data["series"]:
        for point in series["demand"]:
            point["estimate"] = Decimal("10.000") if series["site_id"] != uid(1) else Decimal("-0")
    with localcontext() as context:
        context.prec = 2
        alternate = freeze_scenario(make_scenario(**data))
    assert alternate == freeze_scenario(make_scenario())


def test_nested_snapshot_cannot_be_mutated_after_freeze():
    from dataclasses import FrozenInstanceError

    frozen = freeze_scenario(make_scenario())
    with pytest.raises(ValidationError):
        frozen.inputs.sites[0].reserves[0].quantity = 999
    with pytest.raises(FrozenInstanceError):
        frozen.content_hash = "0"*64


def add_lot(data, series_index=1, n=1, source_kind="ON_HAND"):
    series = data["series"][series_index]
    series["lots"].append(dict(
        lot_id=uid(1000+n), organization_id=uid(99), site_id=series["site_id"],
        product_id=uid(10), base_unit="meal", quantity=10,
        source_kind=source_kind, source_id=f"stock-source-{n}", source_version="fixture-1",
        available_at=datetime(2026, 10, 24, 4, tzinfo=UTC), eligibility="ELIGIBLE",
        expiry=dict(kind="DATED", expires_on=DAY+timedelta(days=2)),
    ))
    return series["lots"][-1]


def test_lot_sources_and_offsets_round_trip_without_changing_identity():
    original = scenario_data()
    add_lot(original)
    frozen = freeze_scenario(make_scenario(**original))
    assert ("LOT", str(uid(1001))) in required_source_keys(frozen.inputs)
    alternate = scenario_data()
    stock = add_lot(alternate)
    stock["available_at"] = stock["available_at"].astimezone(timezone(timedelta(hours=-4)))
    assert freeze_scenario(make_scenario(**alternate)) == frozen


def test_same_supply_cannot_be_duplicated_across_sites():
    data = scenario_data()
    add_lot(data, series_index=1, n=1, source_kind="CONFIRMED")
    second = add_lot(data, series_index=2, n=2, source_kind="CONFIRMED")
    second["source_id"] = "stock-source-1"
    with pytest.raises(ValidationError, match="source identity"):
        make_scenario(**data)


def test_actual_lot_inventory_and_route_changes_create_new_identity():
    data = scenario_data()
    add_lot(data)
    original = freeze_scenario(make_scenario(**data))
    stock = data["series"][1]["lots"][0]
    stock["quantity"] = 9
    assert freeze_scenario(make_scenario(**data)).content_hash != original.content_hash
    data["routes"][0]["transit_days"] = 1
    changed = freeze_scenario(make_scenario(**data))
    assert changed.content_hash != original.content_hash


def test_freshness_requires_explicit_plain_evaluation_day():
    frozen = freeze_scenario(make_scenario())
    with pytest.raises(TypeError, match="date"):
        assess_freshness(frozen, frozen.inputs.sources, as_of_day=datetime.now(UTC))


def test_jsonb_style_object_serialization_reconstructs_same_canonical_identity():
    import json

    frozen = freeze_scenario(make_scenario())
    # Stand-in only for JSONB's key/whitespace reordering, not a database test.
    storage_json = json.dumps(json.loads(frozen.canonical_json), indent=2, sort_keys=False)
    assert freeze_scenario(OperationalScenario.model_validate_json(storage_json)) == frozen
