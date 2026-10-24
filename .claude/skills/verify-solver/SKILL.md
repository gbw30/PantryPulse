---
name: verify-solver
description: "Verify PantryPulse V4 allocation: paired CLASSICAL_GP and EGP_PI_INSPIRED runs on one feasible region, active AP/RP terms, lot/FEFO and capacity invariants, native statuses and replay."
---

V4 authority: docs/architecture/0001-v4-research-first.md, plus the `egp-pi-model` and `cpsat-patterns` skills for the formulation and encoding rules. The three-site data/demo/golden-allocation.json covers the superseded shortage-first model. If it is still tested, keep it passing, but never cite it as V4 evidence. Run solver tests in Docker (`npm run test:api:docker`); OR-Tools is blocked natively on this host.

Use independent arithmetic, not solver-generated summaries. Check, by acceptance ID:

1. **Paired runs (FR-21, TEST-EGP-06):** both methods share one input hash, lot set, requests, dates, routes, capacities and evaluation policy. Only the goal terms differ. Recompute both vectors through the pure evaluator.
2. **Research terms active (FR-24–26, TEST-EGP-02–05):** the model has AP/RP indicator variables reified in both directions, with nonzero penalties. Ablating gamma_AP or gamma_RP changes the research-fixture result. W, Z and the beta blend match a hand calculation, with equality unflagged and singleton groups rejected.
3. **Oracle:** the ADR two-beneficiary case gives classical a=1, and research a=2 (gamma_RP=0.1) and a=1 (gamma_RP=1), both by enumeration and by CP-SAT. Derive at least one new small case of your own that the builder didn't supply.
4. **Feasibility invariants:** stock conservation; no allocation beyond eligible, unreserved lot quantity; FEFO among interchangeable eligible lots; a lot expiring on D is unusable on D; arrival before use; donor reserve against its own forecast demand (FR17); receiving and handling capacity at exact bound and bound+1; no self-transfer, relay or overdelivery; category units never summed.
5. **Edge cases:** zero targets excluded from denominators; zero stock and unavoidable shortage give a feasible plan with explicit unmet slack, never INFEASIBLE; contradictory hard constraints give INFEASIBLE; UNKNOWN and MODEL_INVALID return no vector; FEASIBLE is not shown as OPTIMAL.
6. **Comparison and failure (FR-28, FR-30, TEST-EGP-07):** the six-beneficiary seed changes at least one assignment, with metrics and direction of change reported honestly. A forced research-solve failure shows method-unavailable, never the classical result relabeled. NO_ACTION and greedy baselines, if present, use the same snapshot.
7. **Replay (FR-15):** a stored snapshot reproduces feasibility and objective values, not necessarily an identical tied vector. Seed, worker count, limits, ortools version and policy version are recorded.

Report native status, objective decomposition, bound/gap, violations found and the exact commands with PASS/FAIL/UNVERIFIED per acceptance ID.
