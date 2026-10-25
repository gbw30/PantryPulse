"""Exact goal/objective attachments; physical constraints are already fixed."""

from collections import defaultdict
from fractions import Fraction

from app.services.optimization.constraints import floor_variable
from app.services.optimization.numerics import compile_objective


def attach(physical, *, research):
    m = physical.model
    scenario = physical.problem.scenario
    policy = scenario.policy
    q_by_goal = {}
    product_groups = defaultdict(list)
    attributes = {
        a.site_id: {v.attribute_id: v.score_bp for v in a.scores}
        for a in scenario.package.vulnerability_attributes
    }
    for (sid, pid), (target, fulfilled) in physical.goals.items():
        if not target:
            continue
        weight = Fraction(1)
        if research:
            weight += Fraction(policy.lambda_percent, 100) * sum(
                Fraction(c.percent * attributes[sid][c.attribute_id], 100 * 10000)
                for c in policy.coefficients
            )
        q = floor_variable(
            m,
            10000 * weight.numerator * (target - fulfilled),
            weight.denominator * target,
            20000 if research else 10000,
            f"q:{sid}:{pid}",
        )
        q_by_goal[sid, pid] = q
        product_groups[pid].append(q)
    z = m.new_int_var(0, 20000 if research else 10000, "Z")
    m.add_max_equality(z, list(q_by_goal.values()) or [0])
    beta = Fraction(policy.beta_percent, 100)
    terms = [(q, beta / 10000) for q in q_by_goal.values()]
    terms.append((z, (1 - beta) / 10000))
    ap_flags, rp_flags, excesses = {}, {}, {}
    if research:
        # OR-DEC-006/007 [PROVISIONAL]: current positive-target product groups; two-way flags.
        for (sid, pid), q in q_by_goal.items():
            group = product_groups[pid]
            n = len(group)
            ap = m.new_bool_var(f"ap:{sid}:{pid}")
            m.add(q >= policy.ap_threshold + 1).only_enforce_if(ap)
            m.add(q <= policy.ap_threshold).only_enforce_if(~ap)
            relative = n * q - sum(group)
            rp = m.new_bool_var(f"rp:{sid}:{pid}")
            m.add(relative >= n * policy.rp_threshold + 1).only_enforce_if(rp)
            m.add(relative <= n * policy.rp_threshold).only_enforce_if(~rp)
            ap_flags[sid, pid], rp_flags[sid, pid] = ap, rp
        for pid, group in product_groups.items():
            n = len(group)
            for kind, flags, cap, gamma in (
                ("ap", ap_flags, policy.ap_cap_bp, policy.gamma_ap_percent),
                ("rp", rp_flags, policy.rp_cap_bp, policy.gamma_rp_percent),
            ):
                excess = m.new_int_var(0, 10000 * n, f"excess:{kind}:{pid}")
                m.add_max_equality(
                    excess,
                    [
                        0,
                        10000
                        * sum(flag for (sid, product), flag in flags.items() if product == pid)
                        - cap * n,
                    ],
                )
                terms.append((excess, Fraction(gamma, 100 * len(product_groups) * 10000 * n)))
                excesses[kind, pid] = excess
    # OR-DEC-008 [PROVISIONAL]: classical excludes all vulnerability/AP/RP terms.
    terms.append((physical.q_cost, Fraction(policy.epsilon_cost_bp, 10000 * 10000)))
    active_waste = [ref for ref in scenario.waste_references if ref.units]
    for ref in active_waste:
        terms.append(
            (
                physical.q_waste[ref.product_id],
                Fraction(policy.epsilon_waste_bp, 10000 * 10000 * len(active_waste)),
            )
        )
    return compile_objective(
        m, terms, {"q": q_by_goal, "Z": z, "ap": ap_flags, "rp": rp_flags, "excess": excesses}
    )
