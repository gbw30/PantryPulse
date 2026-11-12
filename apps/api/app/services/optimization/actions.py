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
from collections.abc import Callable
from dataclasses import dataclass, field
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
from app.services.optimization.verify import product_violations, residual_shares

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


@dataclass
class _Plan:
    """One verified plan, indexed once, so each action replays only its own product (each
    location × product series is independent once packed; shared limits are sums)."""

    s: ORInputV3
    packed: tuple
    by_product: dict  # product id -> its packed transfers
    plan_rows: dict  # product id -> its projected rows with the plan
    base_rows: dict  # product id -> its no-transfer rows
    rows: dict  # scenario row field -> product id -> rows
    rooms: Callable
    subs: dict = field(default_factory=dict)
    shares: dict = field(default_factory=dict)

    @classmethod
    def of(cls, s, result):
        if not result.verified:
            raise ValueError("RESULT_NOT_VERIFIED")
        packed = pack(s, quantities_of(result.transfers))
        plan, base = project_v3(s, packed).days, project_v3(s).days

        def group(items, key=lambda r: r.product_id):
            out = defaultdict(list)
            for r in items:
                out[key(r)].append(r)
            return out

        fields = ("batches", "demand", "inbound", "reserves")
        return cls(
            s,
            packed,
            group(packed, lambda x: x.transfer.product_id),
            group(plan),
            group(base),
            {f: group(getattr(s, f)) for f in fields},
            residual_shares(s, packed, plan, base),
        )

    def sub(self, product_id):
        """only_product(s, product_id), from the index."""
        if product_id not in self.subs:
            product = next(p for p in self.s.products if p.id == product_id)
            self.subs[product_id] = self.s.model_copy(
                update={"products": (product,)}
                | {f: tuple(rows[product_id]) for f, rows in self.rows.items()}
            )
        return self.subs[product_id]

    def room(self, product_id):
        if product_id not in self.shares:
            self.shares[product_id] = self.rooms(product_id)
        return self.shares[product_id]


def decision_actions(
    scenario: ORInputV3, result: MethodResult, *, comparison_id, ids=None
) -> DecisionActions:
    """Every action of the plan, or only those in ids (export of a selection)."""
    plan = _Plan.of(scenario, result)
    wanted = None if ids is None else set(ids)
    actions = tuple(
        _action(plan, x.transfer) for x in plan.packed if wanted is None or x.transfer.id in wanted
    )
    days = dates(scenario)
    return DecisionActions(
        comparison_id=comparison_id,
        method=result.method,
        actions=actions,
        plan_window_start=days[0],
        plan_window_end=days[window_days(scenario) - 1],
        effect_window_start=days[0],
        effect_window_end=days[-1],
    )


def _action(plan, t) -> DecisionAction:
    why, kind = _why(plan, t)
    return DecisionAction(
        id=t.id,
        action_text=action_text(plan.s, t),
        why_text=why,
        explanation_kind=kind,
        effect=_effect(plan, t),
    )


def remove_one_effect(scenario: ORInputV3, result: MethodResult, transfer_id: str) -> ActionEffect:
    plan = _Plan.of(scenario, result)
    t = next((x.transfer for x in plan.packed if x.transfer.id == transfer_id), None)
    if t is None:
        raise KeyError(transfer_id)
    return _effect(plan, t)


def _effect(plan, t) -> ActionEffect:
    s, p = plan.s, t.product_id
    ends = (t.from_location_id, t.to_location_id)
    rest = tuple(x for x in plan.by_product[p] if x.transfer.id != t.id)
    without = project_v3(plan.sub(p), rest, locations=set(ends)).days  # only the two ends change
    delta = defaultdict(int)
    for sign, rows in ((1, plan.plan_rows[p]), (-1, without)):
        for d in rows:
            if d.location_id in ends:
                delta["unmet", d.location_id] += sign * d.unmet
                delta["expired"] += sign * d.expired
    sender, receiver = delta["unmet", ends[0]], delta["unmet", ends[1]]
    product = next(x for x in s.products if x.id == p)
    usd = None
    if s.mode == "RETAIL" and product.unit_value_usd is not None:
        usd = money(Decimal(product.unit_value_usd) * (sender + receiver + delta["expired"]))
    return ActionEffect(
        product_id=p,
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


def _why(plan, t) -> tuple[str, str]:
    s, p = plan.s, t.product_id
    names = {loc.id: loc.name for loc in s.locations}
    unit = next(x for x in s.products if x.id == p).unit
    window = dates(s)[: window_days(s)]
    base = plan.base_rows[p]
    short = [d for d in base if d.location_id == t.to_location_id and d.day in window and d.unmet]
    if short:
        unmet = sum(d.unmet for d in short)
        first = (
            f"{names[t.to_location_id]} runs out on {_day(short[0].day)} "
            f"(projected unmet {unmet} {units_label(unit, unmet)} over {len(window)} days)"
        )
    else:
        first = f"{names[t.to_location_id]} can use the units before they expire"
    spare = surplus(plan.sub(p), p, t.from_location_id)
    parts = [
        first,
        f"{names[t.from_location_id]} has {spare} {units_label(unit, spare)} "
        "beyond its protected need",
    ]
    sender = [d for d in base if d.location_id == t.from_location_id and d.expired]
    if sender:
        parts[-1] += f"; {sum(d.expired for d in sender)} of them expire {_day(sender[0].day)}"
    why = "; ".join(parts) + "."
    # One more unit on this route, against the room the rest of the plan leaves in every limit
    grown = quantities_of(x.transfer for x in plan.by_product[p])
    grown[p, t.from_location_id, t.to_location_id] += 1
    violations = product_violations(
        plan.sub(p), p, grown, plan.room(p), base, changed_sender=t.from_location_id
    )
    if not violations:
        return why, "inferred"
    reasons = "; ".join(dict.fromkeys(BINDING.get(v, v) for v in violations))
    return f"{why} One more unit is infeasible: {reasons}.", "proven_binding"


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
