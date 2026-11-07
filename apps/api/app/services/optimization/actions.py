"""Decision actions: action, why, and the remove-one effect (W1-S06, V1-SPEC §6.5).

Every text and number is derived from the frozen scenario and the verified plan:
- why: the receiver's projected shortfall and the sender's protected surplus and expiring stock,
  all from the no-transfer projection;
- explanation kind: proven_binding when the independent verifier rejects the same plan with one
  more unit on this route (the limit is named), otherwise inferred;
- effect: re-project the plan without this one transfer, every other transfer keeping its exact
  batches (no re-optimization). Effects are never summed across actions.
"""

from collections import defaultdict
from decimal import Decimal

from app.schemas.v1_planning import (
    ActionEffect,
    DecisionAction,
    DecisionActions,
    MethodResult,
    ORInputV3,
)
from app.services.optimization.baselines import surplus
from app.services.optimization.projection import project_v3
from app.services.optimization.v3 import dates, money, pack, quantities_of, window_days
from app.services.optimization.verify import verify_plan

BINDING = {  # verifier code -> what one more unit would break
    "TRANSFER_NOT_CONSUMED_IN_WINDOW": "it could not be used in time at the receiver",
    "DONOR_PROTECTION": "the sender would fall short of its own forecast or reserve",
    "SOURCE_OVERDRAWN": "the sender has no more eligible stock",
    "BASELINE_NEED_OVERDELIVERY": "it would exceed the receiver's projected need",
    "ROUTE_CAPACITY": "route capacity",
    "DISPATCH_CAPACITY": "the sender's dispatch capacity",
    "RECEIVING_CAPACITY": "the receiver's receiving capacity",
    "STORAGE_CAPACITY": "storage capacity",
    "GLOBAL_HANDLING_CAPACITY": "network handling capacity",
    "TRANSPORT_COST_BUDGET": "the transport cost budget",
}


def decision_actions(
    scenario: ORInputV3, result: MethodResult, *, comparison_id
) -> DecisionActions:
    s = scenario
    if not result.verified:
        raise ValueError("RESULT_NOT_VERIFIED")
    packed = pack(s, quantities_of(result.transfers))
    with_plan = project_v3(s, packed).days
    baseline = project_v3(s).days
    actions = tuple(
        DecisionAction(
            id=p.transfer.id,
            action_text=action_text(s, p.transfer),
            why_text=why,
            explanation_kind=kind,
            effect=_effect(s, packed, with_plan, p.transfer.id),
        )
        for p in packed
        for why, kind in (_why(s, baseline, result.transfers, p.transfer),)
    )
    return DecisionActions(comparison_id=comparison_id, method=result.method, actions=actions)


def remove_one_effect(scenario: ORInputV3, result: MethodResult, transfer_id: str) -> ActionEffect:
    if not result.verified:
        raise ValueError("RESULT_NOT_VERIFIED")
    packed = pack(scenario, quantities_of(result.transfers))
    if transfer_id not in {p.transfer.id for p in packed}:
        raise KeyError(transfer_id)
    return _effect(scenario, packed, project_v3(scenario, packed).days, transfer_id)


def _effect(s, packed, with_plan, transfer_id) -> ActionEffect:
    t = next(p.transfer for p in packed if p.transfer.id == transfer_id)
    without = project_v3(s, tuple(p for p in packed if p.transfer.id != transfer_id)).days
    ends = (t.from_location_id, t.to_location_id)
    delta = defaultdict(int)
    for sign, rows in ((1, with_plan), (-1, without)):
        for d in rows:
            if d.product_id == t.product_id and d.location_id in ends:
                delta["unmet", d.location_id] += sign * d.unmet
                delta["expired"] += sign * d.expired
    sender, receiver = delta["unmet", ends[0]], delta["unmet", ends[1]]
    product = next(p for p in s.products if p.id == t.product_id)
    usd = None
    if s.mode == "RETAIL" and product.unit_value_usd is not None:
        usd = money(Decimal(product.unit_value_usd) * (sender + receiver + delta["expired"]))
    return ActionEffect(
        product_id=t.product_id,
        unit=product.unit,
        sender_unmet_delta=sender,
        receiver_unmet_delta=receiver,
        expired_delta=delta["expired"],
        usd_delta=usd,
    )


def action_text(s, t) -> str:
    names = {loc.id: loc.name for loc in s.locations}
    product = next(p for p in s.products if p.id == t.product_id)
    return (
        f"Move {t.quantity} {units_label(product.unit, t.quantity)} of {product.name} "
        f"from {names[t.from_location_id]} to {names[t.to_location_id]}, "
        f"ship on {_day(t.ship_date)}, arrives {_day(t.arrival_date)}."
    )


def _why(s, baseline, transfers, t) -> tuple[str, str]:
    names = {loc.id: loc.name for loc in s.locations}
    product = next(p for p in s.products if p.id == t.product_id)
    unit = product.unit
    window = dates(s)[: window_days(s)]
    receiver = [
        d
        for d in baseline
        if (d.location_id, d.product_id) == (t.to_location_id, t.product_id) and d.day in window
    ]
    short = [d for d in receiver if d.unmet]
    if short:
        unmet = sum(d.unmet for d in short)
        first = (
            f"{names[t.to_location_id]} runs out on {_day(short[0].day)} "
            f"(projected unmet {unmet} {units_label(unit, unmet)} over {len(window)} days)"
        )
    else:
        first = f"{names[t.to_location_id]} can use the units before they expire"
    spare = surplus(s, t.product_id, t.from_location_id)
    parts = [
        first,
        f"{names[t.from_location_id]} has {spare} {units_label(unit, spare)} "
        "beyond its protected need",
    ]
    sender = [
        d
        for d in baseline
        if (d.location_id, d.product_id) == (t.from_location_id, t.product_id) and d.expired
    ]
    if sender:
        parts[-1] += f"; {sum(d.expired for d in sender)} of them expire {_day(sender[0].day)}"
    why = "; ".join(parts) + "."
    more = [
        x.model_copy(update={"quantity": x.quantity + 1}) if x.id == t.id else x for x in transfers
    ]
    violations = verify_plan(s, _repacked(s, more)).violations
    if not violations:
        return why, "inferred"
    reasons = "; ".join(dict.fromkeys(BINDING.get(v, v) for v in violations))
    return f"{why} One more unit is infeasible: {reasons}.", "proven_binding"


def _repacked(s, transfers):
    try:
        return tuple(p.transfer for p in pack(s, quantities_of(transfers)))
    except ValueError:
        # can't even pack one more unit: report it through the verifier's own code
        return tuple(transfers)


COUNT_NOUNS = frozenset(
    {"bag", "box", "bottle", "bucket", "bundle", "can", "carton", "case", "container", "crate"}
    | {"jar", "pack", "packet", "pallet", "sack", "tin", "tray", "tub", "unit"}
)


def units_label(unit: str, n: int) -> str:
    """The product's own unit; only known count nouns are pluralized, anything else verbatim."""
    if n == 1 or unit.lower() not in COUNT_NOUNS:
        return unit
    return unit + ("es" if unit.lower().endswith("x") else "s")


def _day(d) -> str:
    return f"{d:%b} {d.day}"
