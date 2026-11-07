# covers: V1-A16
"""Decision actions: action and why text, proven vs inferred, and the remove-one effect (W1-S06).

Hand values come from data/demo/or-v3/README.md.
"""

from decimal import Decimal
from uuid import UUID

import pytest

from app.schemas.v1_planning import NON_ADDITIVE_LABEL, ActionEffect, DecisionActions
from app.services.optimization.actions import decision_actions, remove_one_effect
from app.services.optimization.methods import run_method
from app.services.optimization.projection import project_v3
from app.services.optimization.v3 import pack, quantities_of
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
