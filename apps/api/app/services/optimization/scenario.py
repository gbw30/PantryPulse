"""Freeze and replay complete operational inputs without forecasts or mutable reads."""

from datetime import timedelta

from app.schemas.or_inputs import (
    CandidateKey,
    DemandModifier,
    ORInputPackage,
    ORPolicy,
    ORScenarioPayload,
    ProductReference,
)
from app.schemas.planning_primitives import TransferMode
from app.services.optimization.canonical import canonical_bytes, operational_hash
from app.services.optimization.decisions import DECISION_IDS
from app.services.optimization.forecast_adapter import adapt_series
from app.services.transfer_modes import check_mode_route


def usable(lot) -> bool:
    # OR-DEC-001 [PROVISIONAL]: unknown expiry excluded only at operational adapter.
    return lot.eligibility == "ELIGIBLE" and lot.expires_on is not None


# OR-DEC-015 [PROVISIONAL]: only supplied revisions/frozen replay; no source-store reads.
def freeze_scenario(
    package: ORInputPackage,
    policy: ORPolicy,
    *,
    transfer_mode: TransferMode | str,
    planning_days: int,
    modifiers: tuple[DemandModifier, ...],
    intent: str,
    expected_source_revision: str | None,
) -> ORScenarioPayload:
    package = ORInputPackage.model_validate(package.model_dump())
    policy = ORPolicy.model_validate(policy.model_dump())
    if intent == "CURRENT" and expected_source_revision != package.source_revision_token:
        raise ValueError("SOURCE_REVISION_MISMATCH")
    demand = adapt_series(package.forecasts, modifiers)
    coeffs = {c.attribute_id for c in policy.coefficients}
    if any({x.attribute_id for x in a.scores} != coeffs for a in package.vulnerability_attributes):
        raise ValueError("ATTRIBUTE_POLICY_COVERAGE")
    # OR-DEC-007 [PROVISIONAL]: positive targets determine same-product membership.
    beneficiaries = {s.id for s in package.sites if s.role == "BENEFICIARY"}
    for product in package.products:
        group = [
            s
            for s in demand
            if s.site_id in beneficiaries
            and s.product_id == product.id
            and sum(p.units for p in s.days[:planning_days]) > 0
        ]
        if len(group) == 1:
            raise ValueError("SINGLETON_RP_GROUP_UNSUPPORTED")
        if any(sum(p.units for p in s.days[:planning_days]) > 100_000 for s in group):
            raise ValueError("GOAL_TARGET_UNSUPPORTED")
    sites = {s.id: s for s in package.sites}
    allowed = [
        r
        for r in package.routes
        if check_mode_route(
            transfer_mode,
            r.source_id,
            sites[r.source_id].role,
            r.destination_id,
            sites[r.destination_id].role,
            r.enabled,
        ).allowed
        and r.eta_days < planning_days
    ]
    order = tuple(
        CandidateKey(route_id=r.id, product_id=p.id)
        for source in sorted(sites, key=str)
        for p in sorted(package.products, key=lambda x: str(x.id))
        for r in sorted(
            (r for r in allowed if r.source_id == source),
            key=lambda x: (-x.eta_days, str(x.destination_id)),
        )
    )
    # OR-DEC-004 [PROVISIONAL]: operational identity freezes restricted route loading order.
    cost_reference = 0
    for lot in package.inventory:
        if usable(lot) and lot.dispatchable and lot.expires_on > package.first_planning_date:
            prices = [
                c.cost_minor
                for r in allowed
                if r.source_id == lot.site_id
                for c in r.costs
                if c.product_id == lot.product_id
            ]
            cost_reference += lot.free_units * max(prices, default=0)
    last_day = package.first_planning_date + timedelta(days=6)
    references = tuple(
        ProductReference(
            product_id=p.id,
            units=sum(
                lot.free_units
                for lot in package.inventory
                if lot.product_id == p.id and usable(lot)
            )
            + sum(
                a.units
                for a in package.confirmed_arrivals
                if a.product_id == p.id and usable(a) and a.available_on <= last_day
            ),
        )
        for p in package.products
    )
    scenario = ORScenarioPayload(
        package=package,
        policy=policy,
        transfer_mode=transfer_mode,
        planning_days=planning_days,
        intent=intent,
        modifiers=modifiers,
        demand=demand,
        loading_order=order,
        cost_reference=cost_reference,
        waste_references=references,
        decision_ids=DECISION_IDS,
        policy_hash=operational_hash(policy),
        operational_hash="",
    )
    return scenario.model_copy(
        update={
            "operational_hash": operational_hash(scenario.model_dump(exclude={"operational_hash"}))
        }
    )


def verify_scenario(scenario: ORScenarioPayload) -> None:
    scenario = ORScenarioPayload.model_validate(scenario.model_dump())
    actual = operational_hash(scenario.model_dump(exclude={"operational_hash"}))
    if actual != scenario.operational_hash:
        raise ValueError("SCENARIO_HASH_MISMATCH")
    rebuilt = freeze_scenario(
        scenario.package,
        scenario.policy,
        transfer_mode=scenario.transfer_mode,
        planning_days=scenario.planning_days,
        modifiers=scenario.modifiers,
        intent=scenario.intent,
        expected_source_revision=scenario.package.source_revision_token,
    )
    # OR-DEC-009 [PROVISIONAL]: derivation uses the same unordered-collection semantics
    # as the canonical content identity; serialization must not invalidate replay.
    if canonical_bytes(rebuilt) != canonical_bytes(scenario):
        raise ValueError("SCENARIO_DERIVATION_MISMATCH")
