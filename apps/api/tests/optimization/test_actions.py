# covers: V1-A16
"""Decision actions: action and why text, proven vs inferred, and the remove-one effect (W1-S06).

Hand values come from data/demo/or-v3/README.md.
"""

from decimal import Decimal
from uuid import UUID

import pytest

from app.schemas.v1_planning import (
    NON_ADDITIVE_LABEL,
    ActionEffect,
    DecisionActions,
    ORInputV3,
)
from app.services.optimization.actions import decision_actions, remove_one_effect, units_label
from app.services.optimization.methods import run_method
from app.services.optimization.projection import project_v3
from app.services.optimization.v3 import pack, quantities_of
from app.services.optimization.verify import verify_plan
from tests.optimization.test_retail_oracle import load

COMPARISON = UUID("00000000-0000-4000-8000-0000000000d1")


def actions_for(name, method="RETAIL_OPTIMIZED", measure="UNITS"):
    s, _ = load(name)
    result = run_method(s, method, measure)
    return s, result, decision_actions(s, result, comparison_id=COMPARISON)


def test_action_text_format():
    _, _, actions = actions_for("retail-expiry-transfer")
    (action,) = actions.actions
    assert action.action_text == (
        "Move 6 cases of Yogurt from Store A to Store B, ship on Nov 2, arrives Nov 3."
    )


def test_why_text_from_frozen_inputs():
    """Baseline: B sells its 6 units on Nov 2-3 and then loses 3/day for 5 days (15 cases).
    A can ship 13 cases and still sell its own 7 (README); 7 of its a1 cases expire Nov 4."""
    _, _, actions = actions_for("retail-expiry-transfer")
    assert actions.actions[0].why_text.startswith(
        "Store B runs out on Nov 4 (projected unmet 15 cases over 7 days); "
        "Store A has 13 cases beyond its protected need; 7 of them expire Nov 4."
    )


def test_explanation_kind_proven_binding_vs_inferred():
    """Optimized ships 6: a 7th a1 case can't sell before expiry, so the limit is proven.
    Soonest-expiry-first on lost-vs-waste ships B's 2 lost sales, and a 3rd unit is still
    feasible (README: y = 3 is the optimum), so its reason is only inferred."""
    _, _, proven = actions_for("retail-expiry-transfer")
    assert proven.actions[0].explanation_kind == "proven_binding"
    assert proven.actions[0].why_text.endswith(
        "One more unit is infeasible: it could not be used in time at the receiver."
    )
    _, _, inferred = actions_for("retail-lost-vs-waste", method="SOONEST_EXPIRY_FIRST")
    assert inferred.actions[0].explanation_kind == "inferred"
    assert "infeasible" not in inferred.actions[0].why_text


def total(rows, loc, product_id, field):
    return sum(
        getattr(d, field) for d in rows if (d.location_id, d.product_id) == (loc, product_id)
    )


def test_effect_equals_independent_reprojection():
    """Remove each transfer from the usd-no-flip plan, keep the other one's batches exactly."""
    s, result, actions = actions_for("retail-usd-no-flip", measure="USD")
    packed = pack(s, quantities_of(result.transfers))
    prices = {p.id: Decimal(p.unit_value_usd) for p in s.products}
    for action in actions.actions:
        removed = next(p for p in packed if p.transfer.id == action.id)
        t = removed.transfer
        rest = tuple(p for p in packed if p.transfer.id != action.id)
        with_plan, without = project_v3(s, packed).days, project_v3(s, rest).days

        sender = total(with_plan, t.from_location_id, t.product_id, "unmet") - total(
            without, t.from_location_id, t.product_id, "unmet"
        )
        receiver = total(with_plan, t.to_location_id, t.product_id, "unmet") - total(
            without, t.to_location_id, t.product_id, "unmet"
        )
        expired = sum(
            total(with_plan, loc, t.product_id, "expired")
            - total(without, loc, t.product_id, "expired")
            for loc in (t.from_location_id, t.to_location_id)
        )
        effect = action.effect
        assert (effect.product_id, effect.sender_unmet_delta) == (t.product_id, sender)
        assert (effect.receiver_unmet_delta, effect.expired_delta) == (receiver, expired)
        assert Decimal(effect.usd_delta) == prices[t.product_id] * (sender + receiver + expired)
        assert action.effect == remove_one_effect(s, result, action.id)
    # README: lettuce 4 units remove 4 expiries and 4 lost sales; oil 10 remove 10 lost sales
    by_product = {a.effect.product_id: a.effect for a in actions.actions}
    assert (by_product["P"].receiver_unmet_delta, by_product["P"].expired_delta) == (-4, -4)
    assert (by_product["Q"].receiver_unmet_delta, by_product["Q"].usd_delta) == (-10, "-100.00")


def test_effect_names_the_product_unit():  # CR-w1-web-5
    s, _, actions = actions_for("retail-usd-no-flip")
    units = {p.id: p.unit for p in s.products}
    assert {(a.effect.product_id, a.effect.unit) for a in actions.actions} == set(units.items())


@pytest.mark.parametrize(
    ("unit", "n", "label"),
    [
        ("each", 2, "each"),
        ("lb", 3, "lb"),
        ("kg", 5, "kg"),
        ("case", 2, "cases"),
        ("Case", 2, "Cases"),
        ("box", 2, "boxes"),
        ("case", 1, "case"),
    ],
)
def test_units_label_pluralizes_only_known_count_nouns(unit, n, label):
    """The unit is the product's own string (CR-w1-web-5): never inflect an unknown one."""
    assert units_label(unit, n) == label


def full_replay(s, transfers, t):
    """Oracle for proven_binding: verify the whole network's plan with one more unit on t."""
    more = tuple(
        x.model_copy(update={"quantity": x.quantity + 1}) if x.id == t.id else x for x in transfers
    )
    try:
        more = tuple(p.transfer for p in pack(s, quantities_of(more)))
    except ValueError:
        pass  # verify_plan reports the packing failure itself
    return verify_plan(s, more).violations


def full_effect(s, transfers, t):
    """Oracle for the effect: re-project the whole network without t, other batches kept."""
    packed = pack(s, quantities_of(transfers))
    rest = tuple(p for p in packed if p.transfer.id != t.id)
    with_plan, without = project_v3(s, packed).days, project_v3(s, rest).days
    ends = (t.from_location_id, t.to_location_id)
    sender, receiver = (
        total(with_plan, loc, t.product_id, "unmet") - total(without, loc, t.product_id, "unmet")
        for loc in ends
    )
    expired = sum(
        total(with_plan, loc, t.product_id, "expired")
        - total(without, loc, t.product_id, "expired")
        for loc in ends
    )
    return sender, receiver, expired


def saturated(s, transfers, kind, seed=None):
    """The scenario with one kind of shared limit (or all) set to the plan's own load, so the plan
    still fits. Exact (no seed): one more unit has to break it. With a seed, every limit gets
    0-3 handling units of spare (half of them none), and each storage limit is drawn from its
    location's plan or no-transfer stock, never below what the plan needs, so some days sit
    below the no-transfer stock, where the verifier allows max(limit, no-transfer stock)."""
    import random
    from collections import defaultdict

    from app.schemas.v1_planning import CapacityV3
    from app.services.optimization.verify import cost_minor

    report = verify_plan(s, transfers)
    assert report.passed
    rng = random.Random(seed)

    def spare():
        return 0 if seed is None else rng.choice((0, 0, 0, 1, 2, 3))

    h = {p.id: p.handling_units_per_unit for p in s.products}
    routes = {(r.from_location_id, r.to_location_id): r for r in s.routes}
    route, dispatch, receiving, stock, arriving = (defaultdict(int) for _ in range(5))
    for p in report.packed:
        x = p.transfer
        load = x.quantity * h[x.product_id]
        route[x.from_location_id, x.to_location_id] += load
        dispatch[x.from_location_id] += load
        arriving[x.to_location_id, x.arrival_date] += load
    for (loc, _), load in arriving.items():
        receiving[loc] = max(receiving[loc], load)
    plan_stock, base_stock = defaultdict(int), defaultdict(int)
    for rows, into in ((report.days, plan_stock), (project_v3(s).days, base_stock)):
        for d in rows:
            into[d.location_id, d.day] += d.on_hand * h[d.product_id]
    for loc in sorted({loc for loc, _ in plan_stock}):
        days = sorted(day for at, day in plan_stock if at == loc)
        if seed is None:
            stock[loc] = max(plan_stock[loc, day] for day in days)
            continue
        needed = max(
            (plan_stock[loc, d] for d in days if plan_stock[loc, d] > base_stock[loc, d]),
            default=0,
        )
        drawn = rng.choice([v for d in days for v in (plan_stock[loc, d], base_stock[loc, d])])
        stock[loc] = max(needed, drawn)
    limits = {
        name: {k: v + spare() for k, v in sorted(loads.items())}
        for name, loads in (
            ("route", route),
            ("dispatch", dispatch),
            ("receiving", receiving),
            ("storage", stock),
        )
    }
    every = kind == "all"
    update = {}
    if kind in ("route", "all"):
        update["routes"] = tuple(
            r.model_copy(update={"capacity_per_batch": limits["route"][key]}) if key in route else r
            for key, r in routes.items()
        )
    if kind in ("dispatch", "receiving", "storage", "all"):
        update["capacities"] = tuple(
            CapacityV3(
                location_id=loc.id,
                **{
                    field: limits[field].get(loc.id) if kind == field or every else None
                    for field in ("dispatch", "receiving", "storage")
                },
            )
            for loc in s.locations
        )
    if kind in ("global", "all"):
        update["global_handling"] = sum(dispatch.values()) + spare()
    if kind in ("cost", "all"):
        spent = sum(
            cost_minor(
                routes[p.transfer.from_location_id, p.transfer.to_location_id],
                p.transfer.quantity,
                h[p.transfer.product_id],
            )
            for p in report.packed
        )
        per_unit = cost_minor(s.routes[0], 1, 1)  # every test route has one price
        assert spent.denominator == per_unit.denominator == 1
        update["cost_budget_minor"] = int(spent + spare() * per_unit)
    out = ORInputV3.model_validate(s.model_copy(update=update).model_dump())
    assert verify_plan(out, transfers).passed
    return out


LIMIT_KINDS = ("route", "dispatch", "receiving", "storage", "global", "cost", "all")


@pytest.mark.parametrize(
    ("kind", "seed"),
    [(None, None)] + [(k, None) for k in LIMIT_KINDS] + [(k, 1) for k in LIMIT_KINDS],
)
@pytest.mark.parametrize(
    ("name", "method"),
    [
        ("retail-usd-no-flip", "RETAIL_OPTIMIZED"),
        ("pantry-four-methods", "EGP_PI_INSPIRED"),
        ("pantry-four-methods", "MOST_URGENT_FIRST"),
        ("bench-retail", "SOONEST_EXPIRY_FIRST"),
        ("bench-retail", "RETAIL_OPTIMIZED"),
        ("bench-pantry", "EQUAL_SHARE"),
        ("bench-pantry", "CLASSICAL_GP"),
    ],
)
def test_actions_equal_the_full_network_replay(name, method, kind, seed):
    """Every action's kind, binding reasons and effect equal a replay of the whole network, also
    when a shared limit is exactly saturated by the plan, has a little spare (seed), or sits
    below the no-transfer stock (storage, seed)."""
    from app.services.optimization.actions import BINDING
    from tests.optimization.test_scale_v1 import bench_scenario

    if name.startswith("bench-"):
        s = bench_scenario(14, 10, name.removeprefix("bench-"))
    else:
        s = load(name)[0]
    priced = tuple(r.model_copy(update={"cost_per_handling_unit_usd": "0.37"}) for r in s.routes)
    s = ORInputV3.model_validate(s.model_copy(update={"routes": priced}).model_dump())
    result = run_method(s, method, "UNITS")
    assert result.verified and result.transfers, result.failure_reason
    if kind is not None:
        s = saturated(s, result.transfers, kind, seed)
    codes = set()
    for a in decision_actions(s, result, comparison_id=COMPARISON).actions:
        t = next(x for x in result.transfers if x.id == a.id)
        violations = full_replay(s, result.transfers, t)
        if violations:
            reasons = "; ".join(dict.fromkeys(BINDING.get(v, v) for v in violations))
            assert a.explanation_kind == "proven_binding", (a.id, violations)
            assert a.why_text.endswith(f" One more unit is infeasible: {reasons}."), a.why_text
        else:
            assert a.explanation_kind == "inferred", (a.id, a.why_text)
        effect = a.effect
        assert (
            effect.sender_unmet_delta,
            effect.receiver_unmet_delta,
            effect.expired_delta,
        ) == full_effect(s, result.transfers, t)
        codes |= set(violations)
    print("CODES", name, method, kind, seed, sorted(codes))


def test_no_total_effect_field():
    assert not any("total" in name for name in DecisionActions.model_fields)
    assert not any("total" in name for name in ActionEffect.model_fields)


def test_non_additive_label_text():
    _, _, actions = actions_for("retail-usd-no-flip")
    assert (
        actions.non_additive_label
        == NON_ADDITIVE_LABEL
        == ("effect of this action given the rest of the plan; effects don't add up across actions")
    )
    assert actions.comparison_id == COMPARISON and actions.method == "RETAIL_OPTIMIZED"


def test_usd_effect_absent_when_usd_unavailable():
    s, _ = load("retail-expiry-transfer")
    s = s.model_copy(
        update={"products": (s.products[0].model_copy(update={"unit_value_usd": None}),)}
    )
    result = run_method(s, "RETAIL_OPTIMIZED", "UNITS")
    actions = decision_actions(s, result, comparison_id=COMPARISON)
    assert actions.actions[0].effect.usd_delta is None
    assert actions.actions[0].effect.receiver_unmet_delta == -6


def test_unverified_result_has_no_actions():
    s, result, _ = actions_for("retail-expiry-transfer")
    with pytest.raises(ValueError, match="RESULT_NOT_VERIFIED"):
        decision_actions(
            s,
            result.model_copy(update={"verified": False, "transfers": ()}),
            comparison_id=COMPARISON,
        )


def test_pantry_actions_explain_the_window():
    """EGP plans P1 2, P2 2 (README). Why text counts unmet inside the 2-day window; the hub's
    4 cases are all shipped, so one more unit is proven infeasible; Pantry has no USD effect."""
    _, _, actions = actions_for("pantry-four-methods", method="EGP_PI_INSPIRED")
    by_text = {a.action_text: a for a in actions.actions}
    assert set(by_text) == {
        "Move 2 cases of Canned beans from Central Hub to Pantry 1, ship on Nov 2, arrives Nov 3.",
        "Move 2 cases of Canned beans from Central Hub to Pantry 2, ship on Nov 2, arrives Nov 3.",
    }
    p1 = next(a for a in actions.actions if "Pantry 1," in a.action_text)
    assert p1.why_text == (
        "Pantry 1 runs out on Nov 3 (projected unmet 3 cases over 2 days); "
        "Central Hub has 4 cases beyond its protected need. "
        "One more unit is infeasible: the sender has no more eligible stock."
    )
    assert p1.explanation_kind == "proven_binding"
    assert (p1.effect.receiver_unmet_delta, p1.effect.usd_delta) == (-2, None)
