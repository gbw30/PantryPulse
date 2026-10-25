"""Independent expected physical/numeric facts for the provisional OR boundary."""

import json
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.or_inputs import (
    DemandModifier,
    ORInputPackage,
    ORScenarioPayload,
    Rational,
    ResidualCapacity,
)
from app.schemas.or_outputs import Candidate, RouteQuantity
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.canonical import canonical_bytes, operational_hash
from app.services.optimization.forecast_adapter import adapt_series
from app.services.optimization.kernel import KernelLot, project_kernel
from app.services.optimization.packing import pack
from app.services.optimization.scenario import freeze_scenario, verify_scenario
from app.services.optimization.verify import verify

DATA = Path(__file__).resolve().parents[4] / "data/demo/or-v2"


def snapshot(name="six-beneficiary-v2"):
    return ORScenarioPayload.model_validate_json((DATA / f"{name}.snapshot.json").read_text())


def refreeze(s, **changes):
    p = changes.pop("package", s.package)
    return freeze_scenario(
        p,
        changes.pop("policy", s.policy),
        transfer_mode=changes.pop("transfer_mode", s.transfer_mode),
        planning_days=changes.pop("planning_days", s.planning_days),
        modifiers=changes.pop("modifiers", s.modifiers),
        intent=s.intent,
        expected_source_revision=p.source_revision_token,
        **changes,
    )


def quantities(problem, vector):
    return tuple(
        RouteQuantity(route_id=c.route_id, product_id=c.product_id, units=n)
        for c, n in zip(problem.candidates, vector, strict=True)
    )


def test_full_fixture_exact_metrics_and_independent_checker():
    # OR-DEC-006 [PROVISIONAL]: default coefficients; OR-DEC-008 comparator.
    # OR-DEC-006 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    problem = prepare_problem(snapshot())
    for vector, objective, method in [
        ((1,) * 12, Fraction(163, 50), "CLASSICAL_GP"),
        ((2, 2, 1, 1, 0, 0) * 2, Fraction(1393, 300), "EGP_PI_INSPIRED"),
    ]:
        q = quantities(problem, vector)
        transfers = pack(problem, q)
        checked = verify(problem, Candidate(route_quantities=q, assignments=transfers), method)
        assert checked.passed, checked.violations
        result = checked.metrics
        actual = (
            result.classical_objective if method == "CLASSICAL_GP" else result.research_objective
        )
        assert actual.fraction() == objective
        assert result.cost_minor == 12
        assert all(waste == 0 for _, waste in result.waste_by_product)


def test_lost_sales_not_overlapping_cumulative_need():
    # OR-DEC-001 [PROVISIONAL]: dated deterministic lost sales, no backlog.
    # OR-DEC-001 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    s = snapshot()
    start = s.package.first_planning_date
    days, lots = project_kernel(
        tuple((start + timedelta(days=i), d) for i, d in enumerate((50, 40, 0, 0, 0, 0, 0))),
        (KernelLot("one", 40, start, start + timedelta(days=7), False),),
    )
    assert [d.unmet for d in days[:2]] == [10, 40]
    assert sum(d.unmet for d in days) == 50
    assert sum(lots[0].consumed) == 40


def test_late_arrival_cannot_serve_yesterday():
    s = snapshot()
    start = s.package.first_planning_date
    days, _ = project_kernel(
        ((start, 5), (start + timedelta(days=1), 2)),
        (KernelLot("incoming", 7, start + timedelta(days=1), start + timedelta(days=2), True),),
    )
    assert [(d.served, d.unmet, d.on_hand) for d in days] == [(0, 5, 0), (2, 0, 5)]


def test_modifier_applied_before_single_daily_ceiling():
    # OR-DEC-010 [PROVISIONAL]: 0.2*2=0.4 ->1, never scale ceiled 1 to2.
    # OR-DEC-010 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    s = snapshot()
    forecast = s.package.forecasts[-1]
    forecast = forecast.model_copy(
        update={
            "days": tuple(p.model_copy(update={"central_literal": "0.2"}) for p in forecast.days)
        }
    )
    choice = DemandModifier(
        site_id=forecast.site_id,
        product_id=forecast.product_id,
        mode="CENTRAL",
        multiplier="2",
        buffer_fraction=None,
    )
    (result,) = adapt_series((forecast,), (choice,))
    assert {p.units for p in result.days} == {1}
    assert {Decimal(p.unrounded_literal) for p in result.days} == {Decimal("0.4")}


def test_true_fraction_above_integer_and_constant29():
    s = snapshot()
    f = s.package.forecasts[-1]
    c = DemandModifier(
        site_id=f.site_id,
        product_id=f.product_id,
        mode="CENTRAL",
        multiplier="1",
        buffer_fraction=None,
    )
    for literal, target in [("29", 29), ("29.000000000000001", 30)]:
        modified = f.model_copy(
            update={
                "days": tuple(p.model_copy(update={"central_literal": literal}) for p in f.days)
            }
        )
        (result,) = adapt_series((modified,), (c,))
        assert {p.units for p in result.days} == {target}


def test_conservative_quantile_and_buffer_provenance():
    s = snapshot()
    f = s.package.forecasts[-1]
    choice = DemandModifier(
        site_id=f.site_id,
        product_id=f.product_id,
        mode="CONSERVATIVE",
        multiplier="1",
        buffer_fraction=None,
    )
    with pytest.raises(ValueError, match="BUFFER"):
        adapt_series((f,), (choice,))
    choice = choice.model_copy(update={"buffer_fraction": "0.5"})
    (result,) = adapt_series((f,), (choice,))
    assert result.days[0].units == 3 and result.days[0].method == "EXPLICIT_BUFFER"
    modified = f.model_copy(
        update={
            "days": tuple(p.model_copy(update={"p90_literal": "4"}) for p in f.days),
            "interval_method": "MODEL_QUANTILES",
        }
    )
    (result,) = adapt_series((modified,), (choice,))
    assert {p.units for p in result.days} == {4}
    assert {p.method for p in result.days} == {"MODEL_UPPER_QUANTILE"}


def test_mode_required_and_immutable_replay_identity():
    # OR-DEC-002/009/015 [PROVISIONAL]: explicit modes, exact frozen historical identity.
    # OR-DEC-002 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    s = snapshot()
    verify_scenario(s)
    raw = s.model_dump()
    raw.pop("transfer_mode")
    with pytest.raises(ValidationError):
        ORScenarioPayload.model_validate(raw)
    other = refreeze(s, transfer_mode="HUB_AND_PANTRY")
    assert other.operational_hash != s.operational_hash
    tampered = s.model_copy(update={"planning_days": 2})
    with pytest.raises(ValueError, match="HASH"):
        verify_scenario(tampered)
    with pytest.raises(ValueError, match="REVISION"):
        freeze_scenario(
            s.package,
            s.policy,
            transfer_mode=s.transfer_mode,
            planning_days=3,
            modifiers=s.modifiers,
            intent="CURRENT",
            expected_source_revision="changed",
        )


def test_canonical_collections_sorted_dates_preserved_no_floats():
    # OR-DEC-009 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    s = snapshot()
    p = s.package
    a = canonical_bytes(p)
    assert a == canonical_bytes(p.model_copy(update={"inventory": p.inventory[::-1]}))
    assert operational_hash({"days": [1, 2]}) != operational_hash({"days": [2, 1]})
    with pytest.raises(ValueError, match="Float"):
        canonical_bytes({"n": 0.2})
    assert Rational(numerator=2, denominator=4).fraction() == Fraction(1, 2)


def test_duplicate_source_unit_organization_and_quantity_rejections():
    # OR-DEC-020 [PROVISIONAL]: supplied source structure/coverage only.
    # OR-DEC-005 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    p = snapshot().package
    raw = p.model_dump()
    raw["inventory"] += (raw["inventory"][0],)
    with pytest.raises(ValidationError, match="DUPLICATE"):
        ORInputPackage.model_validate(raw)
    for changes, expected in [
        ({"free_units": True}, "valid integer"),
        ({"unit": "WRONG"}, "UNIT_MISMATCH"),
        ({"committed_units": 1}, "COMPONENT_MISMATCH"),
        ({"commitment_overlaps_demand": True}, "OVERLAP_UNSUPPORTED"),
    ]:
        raw = p.model_dump()
        raw["inventory"][0].update(changes)
        with pytest.raises(ValidationError, match=expected):
            ORInputPackage.model_validate(raw)
    raw = p.model_dump()
    raw["sites"][0]["organization_id"] = UUID(int=999)
    with pytest.raises(ValidationError, match="CROSS_ORGANIZATION"):
        ORInputPackage.model_validate(raw)


def test_invalid_quantities_and_tampered_assignment_rejected():
    p = prepare_problem(snapshot())
    q = quantities(p, (1,) * 12)
    packed = pack(p, q)
    t = packed[0].model_copy(update={"unit": "WRONG"})
    checked = verify(p, Candidate(route_quantities=q, assignments=(t,) + packed[1:]))
    assert not checked.passed and "PACKING_FEFO_LINEAGE_MISMATCH" in checked.violations
    with pytest.raises(ValueError, match="BOUND"):
        pack(p, (q[0].model_copy(update={"units": 100}),))


def test_zero_vector_valid_and_withheld_service_claim_rejected():
    p = prepare_problem(snapshot())
    checked = verify(p, Candidate(route_quantities=(), assignments=()))
    assert checked.passed
    fake = checked.metrics.model_copy(update={"cost_minor": 1})
    checked = verify(p, Candidate(route_quantities=(), assignments=(), claimed_metrics=fake))
    assert not checked.passed and "CLAIMED_METRICS_MISMATCH" in checked.violations


def test_expiry_and_unknown_expiry_operational_exclusion():
    s = snapshot()
    p = s.package
    changed = p.model_copy(
        update={
            "inventory": tuple(
                lot.model_copy(update={"expires_on": None, "expiry_kind": "UNKNOWN"})
                for lot in p.inventory
            )
        }
    )
    changed = refreeze(s, package=changed)
    problem = prepare_problem(changed)
    assert not any(c.upper for c in problem.candidates)
    assert len(problem.baseline.exclusions) == 2
    assert sum(r.units for r in changed.waste_references) == 0
    assert verify(problem, Candidate(route_quantities=(), assignments=())).passed


def test_singleton_positive_group_rejected():
    # OR-DEC-007 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    s = snapshot("ap-ablation-v2")
    p = s.package
    fs = tuple(
        f.model_copy(
            update={"days": tuple(d.model_copy(update={"central_literal": "0"}) for d in f.days)}
        )
        if f.site_id == p.sites[-1].id
        else f
        for f in p.forecasts
    )
    with pytest.raises(ValueError, match="SINGLETON"):
        refreeze(s, package=p.model_copy(update={"forecasts": fs}))


def test_shared_handling_capacity_is_joint_across_products():
    # OR-DEC-017 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    s = snapshot()
    caps = s.package.capacities
    changed = refreeze(
        s,
        package=s.package.model_copy(
            update={
                "capacities": caps.model_copy(
                    update={
                        "global_handling": ResidualCapacity(
                            original=17, fixed_used=0, residual=17, source_revision="sim-v2"
                        )
                    }
                )
            }
        ),
    )
    p = prepare_problem(changed)
    q = quantities(p, (1,) * 12)
    checked = verify(p, Candidate(route_quantities=q, assignments=pack(p, q)))
    assert not checked.passed and "GLOBAL_HANDLING_CAPACITY" in checked.violations


def test_pantry_surplus_topology_and_harmful_donor_future_protection():
    # OR-DEC-003 [PROVISIONAL]: own future service cannot depend on proposed inbound.
    # OR-DEC-003 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    s = snapshot("pantry-surplus-v2")
    pantry = s.package.sites[1].id
    product = s.package.products[0].id
    p = prepare_problem(s)
    route = next(c for c in p.candidates if c.source_id == pantry and c.product_id == product)
    q = (RouteQuantity(route_id=route.route_id, product_id=product, units=2),)
    assert verify(p, Candidate(route_quantities=q, assignments=pack(p, q))).passed
    hub_only = prepare_problem(refreeze(s, transfer_mode="HUB_ONLY"))
    assert not any(c.source_id == pantry for c in hub_only.candidates)
    harmful = prepare_problem(snapshot("harmful-donor-v2"))
    checked = verify(harmful, Candidate(route_quantities=q, assignments=pack(harmful, q)))
    assert not checked.passed and "DONOR_NO_INBOUND_PROTECTION" in checked.violations


def test_long_route_skips_incompatible_early_expiry_then_short_route_uses_it():
    # OR-DEC-004 [PROVISIONAL]: loading order long ETA first; expiry exception is physical.
    # OR-DEC-004 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    p = prepare_problem(snapshot("eta-expiry-v2"))
    assert [c.eta_days for c in p.candidates] == [2, 0]
    q = quantities(p, (2, 2))
    transfers = pack(p, q)
    assert transfers[0].expires_on > transfers[1].expires_on
    assert verify(p, Candidate(route_quantities=q, assignments=transfers)).passed
    early, late = sorted(p.scenario.package.inventory, key=lambda lot: lot.expires_on)
    assert transfers[0].original_lot_id == late.id
    assert transfers[1].original_lot_id == early.id


@pytest.mark.parametrize(
    "value,multiplier,target,sparse",
    [
        (29.0, "1", 29, False),
        (0.2, "2", 1, False),
        (29.000000000000004, "1", 30, False),
        (29.0, "1", 29, True),
    ],
)
def test_merged_adapter_and_unknown_expiry_wrapper(value, multiplier, target, sparse):
    from app.services.forecasting.handoff import DemandChoice, freeze_handoff
    from app.services.forecasting.preparation import prepare
    from app.services.forecasting.schemas import ForecastPolicy, HistoryBundle
    from app.services.forecasting.service import forecast
    from app.services.inventory.projection import ProjectionLot, project_daily

    f = snapshot().package.forecasts[-1]
    raw = {
        "organization_id": f.organization_id,
        "dataset_id": UUID(int=777),
        "scope": [
            {
                "key": {
                    "organization_id": f.organization_id,
                    "site_id": f.site_id,
                    "product_id": f.product_id,
                    "target_type": "DEMAND",
                },
                "unit": f.unit,
                "timezone": f.timezone,
            }
        ],
        "demand": [],
    }
    for i in range(0, 14, 2) if sparse else range(14):
        day = f.cutoff - timedelta(days=i)
        raw["demand"].append(
            {
                "source": {
                    "organization_id": f.organization_id,
                    "dataset_id": UUID(int=777),
                    "logical_key": str(day),
                    "revision_id": UUID(int=800 + i),
                    "revision": 1,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
                "key": raw["scope"][0]["key"],
                "day": day,
                "requested_units": value,
                "fulfilled_units": value,
                "unmet_units": 0.0,
                "source_classification": "SIMULATED",
            }
        )
    bundle = HistoryBundle.model_validate(raw)
    inputs = prepare(
        bundle,
        data_cutoff_date=f.cutoff,
        snapshot_as_of=f.generated_at,
        policy=ForecastPolicy(
            policy_version="experimental-v1",
            sparse_window_days=14,
            sparse_min_samples=3,
            allow_fallback=sparse,
        ),
    )
    output = forecast(inputs)
    key = bundle.scope[0].key
    handoff = freeze_handoff(inputs, output, choices=(DemandChoice(key=key, mode="CENTRAL"),))
    lots = (
        ProjectionLot(
            lot_id=UUID(int=999),
            key=key,
            source_version="v1",
            unit=f.unit,
            units=100,
            available_on=f.cutoff,
            expires_on=None,
            eligibility="ELIGIBLE",
            supply_kind="ON_HAND",
        ),
    )
    assert sum(d.served for d in project_daily(handoff.selected[0], lots=lots)) == min(
        100, sum(day.units for day in handoff.selected[0].days)
    )
    from app.services.optimization.forecast_adapter import adapt_forecasts

    choice = DemandModifier(
        site_id=f.site_id,
        product_id=f.product_id,
        mode="CENTRAL",
        multiplier=multiplier,
        buffer_fraction=None,
    )
    (result,) = adapt_forecasts(
        handoff, (choice,), committed_result_ids=(output.series[0].result_id,), planning_ready=True
    )
    assert [p.units for p in result.days] == [target] * 7
    assert result.numeric_conversion == "LEGACY_FLOAT_LITERAL"
    metadata = json.loads(result.upstream_metadata_json)
    assert metadata["original_handoff_hash"] == handoff.content_hash
    assert metadata["result"]["actual_provider"]["name"] == (
        "MOVING_AVERAGE" if sparse else "SEASONAL_NAIVE"
    )
    with pytest.raises(ValueError, match="SOURCE_NOT_COMMITTED"):
        adapt_forecasts(handoff, (choice,), committed_result_ids=(), planning_ready=False)


def test_future_service_cannot_justify_new_transfer_or_repair_lost_demand():
    s = snapshot("ap-ablation-v2")
    package = s.package
    route = package.routes[0]
    late = route.model_copy(update={"eta_days": 1})
    changed = refreeze(s, package=package.model_copy(update={"routes": (late, package.routes[1])}))
    p = prepare_problem(changed)
    q = (RouteQuantity(route_id=late.id, product_id=package.products[0].id, units=1),)
    checked = verify(p, Candidate(route_quantities=q, assignments=pack(p, q)))
    assert not checked.passed
    assert "TRANSFER_NOT_CONSUMED_WITHIN_WINDOW" in checked.violations


def test_all_zero_groups_and_zero_stock_stay_feasible():
    s = snapshot("zero-stock-v2")
    fs = tuple(
        f.model_copy(
            update={"days": tuple(d.model_copy(update={"central_literal": "0"}) for d in f.days)}
        )
        for f in s.package.forecasts
    )
    s = refreeze(s, package=s.package.model_copy(update={"forecasts": fs}))
    p = prepare_problem(s)
    checked = verify(p, Candidate(route_quantities=(), assignments=()))
    assert checked.passed
    assert checked.metrics.groups == ()
    assert checked.metrics.W.fraction() == checked.metrics.Z.fraction() == 0
    assert all(g.service_ratio is None and not g.ap and not g.rp for g in checked.metrics.goals)


def test_residual_capacities_deduct_fixed_usage_once():
    # OR-DEC-017 [PROVISIONAL]: supplied residual already excludes committed handling.
    s = snapshot()
    cap = s.package.capacities.global_handling.model_copy(
        update={"original": 20, "fixed_used": 2, "residual": 18}
    )
    s = refreeze(
        s,
        package=s.package.model_copy(
            update={"capacities": s.package.capacities.model_copy(update={"global_handling": cap})}
        ),
    )
    p = prepare_problem(s)
    q = quantities(p, (1,) * 12)
    assert verify(p, Candidate(route_quantities=q, assignments=pack(p, q))).passed


def test_source_manifest_and_decimal_context_cannot_change_identity():
    from decimal import localcontext

    from app.schemas.or_inputs import decimal_literal

    s = snapshot()
    wrong = s.package.model_dump()
    wrong["source_manifest_hash"] = "f" * 64
    with pytest.raises(ValidationError, match="MANIFEST_HASH"):
        ORInputPackage.model_validate(wrong)
    literal = "12345.678900000000001"
    with localcontext() as ctx:
        ctx.prec = 4
        assert decimal_literal(literal) == "12345.678900000000001"
        assert canonical_bytes(Decimal(literal)) == b'"12345.678900000000001"'
