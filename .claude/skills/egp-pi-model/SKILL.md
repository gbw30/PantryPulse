---
name: egp-pi-model
description: "Build or review PantryPulse's CLASSICAL_GP and EGP_PI_INSPIRED allocation models: V4 section 11.7 formulation, reified AP/RP flags, weighted/Chebyshev blend, fixed-point scaling, the shared feasible region and the TEST-EGP fixtures. Use when touching apps/api/app/services/optimization or its tests."
---

The formula authority is docs/architecture/0001-v4-research-first.md, sections "Proposed V4 mathematical contract", "Shared hard constraints" and "Independent oracle and implementation gate". The underlying requirement is V4 section 11.7 (docs/pantrypulse/SPEC-V4.snapshot.txt). This skill is the working checklist. Where it disagrees with ADR 0001, follow the ADR and report the conflict to the lead.

## Gate first

Do not write solver code until the lead has recorded the ADR 0001 gate items: full-paper mapping, an independent enumeration oracle, a frozen coefficient/scaling/category policy, the FEFO encoding, the same-feasibility proof, AP/RP ablations and the deterministic six-beneficiary research fixture. If an item is open, stop and report it. By hour 20 the research engine must execute; otherwise it is reported as incomplete.

## Module boundaries

- `constraints.py` builds the single feasible region: lots, FEFO, reserves, ETA/use dates, receiving and handling capacity, no self-transfer, no relay, no overdelivery. Both methods call it with the same immutable, content-hashed input.
- `policy.py` holds attributes, coefficients, groups, thresholds and scales, versioned with provenance (SIMULATED in the demo).
- `classical_gp.py` and `egp_pi_inspired.py` differ only in their goal terms.
- `metrics.py` is a pure evaluator that recomputes every reported number from the returned vector. It never reads solver internals and never influences a solve.

## Encoding rules

- Use integers only. Keep exact ratios and integer unit counts beside every scaled value.
- Per positive-target goal (beneficiary i, category p): target r is a constant, fulfilled f in [0, r], unmet u = r - f. A zero target has a null service ratio, zero deficit and no flags, and is excluded from every denominator.
- Weight v = 1 + lambda * sum(c_k * a_k), held as a rational vn/vd. Scaled deficit q = floor(S*v*u/r), encoded exactly as `q*vd*r <= S*vn*u <= q*vd*r + vd*r - 1`. Quantization is part of the approximation, so test it against exact rational arithmetic. The ADR leaves open whether to keep floor quantization or switch to exact cross multiplication; use whichever the lead records.
- AP flag b is true iff q > A, where A is the integer-scaled tau_AP. Reify both directions (`q >= A+1` if b, `q <= A` if not b) so a false flag cannot dodge a penalty. Equality is unflagged.
- RP flag is true iff `N_g*q_i - sum_g(q) > N_g*T` for the group g, reified both directions. Groups contain the positive-target beneficiaries of the same category, including the beneficiary itself, with at least two members. Reject undefined or singleton groups (API 422).
- Excess share per category, with cap = cap_num/cap_den: `E = max(0, cap_den*sum(b) - cap_num*N)` via max-equality. Its value is E/(N*cap_den). It is a soft goal: scarce supply still yields unmet slack, never infeasibility.
- Blend: W = sum(q), Z = max(q) via max-equality, beta = bn/bd, so `bd*B = bn*W + (bd-bn)*Z`. The research objective adds gamma_AP*AP_excess + gamma_RP*RP_excess + epsilon_cost*cost + epsilon_waste*waste, with both gammas positive. Multiply every term by one documented common denominator, assert integrality, and prove every coefficient-times-domain sum fits int64.
- CLASSICAL_GP: the same constraint builder, the conventional policy weights (no vulnerability term), no AP/RP terms, and the same beta and epsilon coefficients. Evaluate both outputs with the same evaluation policy in `metrics.py`.
- Never sum meal and bottle quantities. Normalize and aggregate by category exactly as the frozen policy says.

CP-SAT mechanics (reification syntax, statuses, determinism, bounds) are in the `cpsat-patterns` skill.

## Required tests (write them first)

- **Oracle:** the ADR two-beneficiary table. Requests (2,2), supply 2, v=(2,1), beta=0.5, tau_AP=0.75, tau_RP=0.25, caps 0. Research picks a=2 when gamma_AP=1, gamma_RP=0.1, and a=1 when gamma_RP=1. Classical (v=1, beta=0.5) picks a=1. Assert these with brute-force enumeration that is independent of CP-SAT, then assert that CP-SAT matches.
- **TEST-EGP-01:** normalized attributes produce the hand-calculated coefficients; provenance separates SIMULATED from observed; changing a weight changes the objective.
- **TEST-EGP-02:** AP flags and excess penalty match manual values below, at and above the threshold. Equality is unflagged.
- **TEST-EGP-03:** RP group means come from the same scenario, flags move with the allocation, and singleton or empty groups are rejected.
- **TEST-EGP-04:** the CP-SAT model contains active AP/RP indicator variables with nonzero penalties. Ablation: setting gamma_AP or gamma_RP to 0 must change the result on the research fixture.
- **TEST-EGP-05:** W and Z are reported separately and combined by beta at the configured scale.
- **TEST-EGP-06:** paired runs share the input hash and feasible region; conservation and capacity hold for both; results are reproducible.
- **TEST-EGP-07:** the six-beneficiary seed changes at least one assignment between methods. Report unmet units, worst service ratio, AP/RP shares, waste and cost with direction of change. Don't force an improvement claim.
- Property tests over random small feasible inputs: conservation, allocations within eligible lots, FEFO order, and evaluator agreement with the solver's own numbers.

## Never

- Compute AP/RP flags only after the solve and call them part of the model.
- Return the classical result labeled as EGP when the research solve fails (FR-30). Report method-unavailable instead.
- Claim exact EGP-PI reproduction or real-world fairness gains. See `research-claims-check`.
- Hide identical outcomes. If the methods tie on the seed, adjust the fixture transparently and record why.
