"""Exact independent objective/common metrics from replay, never solver internals."""

from fractions import Fraction

from app.schemas.or_inputs import Rational
from app.schemas.or_outputs import GoalMetric, GroupMetric, Metrics
from app.services.fixed_point import SCALE, quantize_weighted_deficit


def vulnerability(scenario, site_id) -> Fraction:
    attributes = next(a for a in scenario.package.vulnerability_attributes if a.site_id == site_id)
    scores = {a.attribute_id: a.score_bp for a in attributes.scores}
    weighted = sum(
        Fraction(c.percent * scores[c.attribute_id], 100 * 10_000)
        for c in scenario.policy.coefficients
    )
    return 1 + Fraction(scenario.policy.lambda_percent, 100) * weighted


def evaluate(scenario, projection, assignments) -> Metrics:
    policy, package = scenario.policy, scenario.package
    beneficiaries = {s.id for s in package.sites if s.role == "BENEFICIARY"}
    rows, group_metrics, warnings = [], [], []
    goals = {}
    for demand in scenario.demand:
        if demand.site_id not in beneficiaries:
            continue
        target = sum(p.units for p in demand.days[: scenario.planning_days])
        window = {p.day for p in demand.days[: scenario.planning_days]}
        fulfilled = sum(
            p.served
            for p in projection.days
            if p.site_id == demand.site_id and p.product_id == demand.product_id and p.day in window
        )
        deficit = Fraction(target - fulfilled, target) if target else Fraction(0)
        v = vulnerability(scenario, demand.site_id)
        z = v * deficit
        goals[demand.site_id, demand.product_id] = (
            target,
            fulfilled,
            deficit,
            v,
            z,
            quantize_weighted_deficit(z),
            quantize_weighted_deficit(deficit),
        )
    ap_total = rp_total = Fraction(0)
    for product in package.products:
        active = {
            key: values for key, values in goals.items() if key[1] == product.id and values[0] > 0
        }
        n = len(active)
        sumq = sum(v[5] for v in active.values())
        sumz = sum((v[4] for v in active.values()), Fraction(0))
        ap_count = rp_count = 0
        for key, values in goals.items():
            if key[1] != product.id:
                continue
            target, fulfilled, deficit, weight, z, q, q0 = values
            # OR-DEC-007 [PROVISIONAL]: current-candidate product mean, strict equality.
            ap = bool(target and q > policy.ap_threshold)
            rp = bool(target and n * q - sumq > n * policy.rp_threshold)
            exact_ap = bool(target and z > Fraction(policy.ap_threshold, SCALE))
            exact_rp = bool(target and z - sumz / n > Fraction(policy.rp_threshold, SCALE))
            if ap != exact_ap or rp != exact_rp:
                warnings.append(f"EXACT_QUANTIZED_FLAG_DISAGREEMENT:{key[0]}:{key[1]}")
            ap_count += ap
            rp_count += rp
            rows.append(
                GoalMetric(
                    site_id=key[0],
                    product_id=key[1],
                    target=target,
                    fulfilled=fulfilled,
                    unmet=target - fulfilled,
                    service_ratio=Rational.of(Fraction(fulfilled, target)) if target else None,
                    deficit=Rational.of(deficit),
                    vulnerability=Rational.of(weight),
                    weighted_deficit=Rational.of(z),
                    q=q,
                    q0=q0,
                    ap=ap,
                    rp=rp,
                    exact_ap=exact_ap,
                    exact_rp=exact_rp,
                )
            )
        if n:
            eap = max(0, SCALE * ap_count - policy.ap_cap_bp * n)
            erp = max(0, SCALE * rp_count - policy.rp_cap_bp * n)
            ap_total += Fraction(eap, SCALE * n)
            rp_total += Fraction(erp, SCALE * n)
            group_metrics.append(
                GroupMetric(
                    product_id=product.id,
                    size=n,
                    ap_count=ap_count,
                    rp_count=rp_count,
                    ap_excess_numerator=eap,
                    rp_excess_numerator=erp,
                )
            )
    if group_metrics:
        ap_total /= len(group_metrics)
        rp_total /= len(group_metrics)
    qvalues = [g.q for g in rows if g.target]
    q0values = [g.q0 for g in rows if g.target]
    w, z = Fraction(sum(qvalues), SCALE), Fraction(max(qvalues, default=0), SCALE)
    w0, z0 = Fraction(sum(q0values), SCALE), Fraction(max(q0values, default=0), SCALE)
    cost = sum(t.cost_minor for t in assignments)
    qcost = (SCALE * cost // scenario.cost_reference) if scenario.cost_reference else 0
    wastes, qwastes = [], []
    for ref in scenario.waste_references:
        waste = sum(d.expired for d in projection.days if d.product_id == ref.product_id)
        wastes.append((ref.product_id, waste))
        qwastes.append((ref.product_id, SCALE * waste // ref.units if ref.units else 0))
    active_waste = [
        q for (pid, q), ref in zip(qwastes, scenario.waste_references, strict=True) if ref.units
    ]
    mean_waste = (
        Fraction(sum(active_waste), SCALE * len(active_waste)) if active_waste else Fraction(0)
    )
    beta = Fraction(policy.beta_percent, 100)
    ancillary = (
        Fraction(policy.epsilon_cost_bp, SCALE) * Fraction(qcost, SCALE)
        + Fraction(policy.epsilon_waste_bp, SCALE) * mean_waste
    )
    classical = beta * w0 + (1 - beta) * z0 + ancillary
    research = (
        beta * w
        + (1 - beta) * z
        + Fraction(policy.gamma_ap_percent, 100) * ap_total
        + Fraction(policy.gamma_rp_percent, 100) * rp_total
        + ancillary
    )
    # OR-DEC-008 [PROVISIONAL]: equal classical weights; common normalized ancillary terms.
    return Metrics(
        goals=tuple(rows),
        groups=tuple(group_metrics),
        cost_minor=cost,
        q_cost=qcost,
        waste_by_product=tuple(wastes),
        q_waste_by_product=tuple(qwastes),
        W=Rational.of(w),
        Z=Rational.of(z),
        W0=Rational.of(w0),
        Z0=Rational.of(z0),
        ap_excess=Rational.of(ap_total),
        rp_excess=Rational.of(rp_total),
        classical_objective=Rational.of(classical),
        research_objective=Rational.of(research),
        warnings=tuple(warnings),
    )
