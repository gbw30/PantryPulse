---
name: cpsat-patterns
description: "OR-Tools CP-SAT modeling rules for PantryPulse: integer encodings, reification, max and floor constraints, int64 bounds, solve parameters for replay, native status handling and independent verification. Use when writing or reviewing any CP-SAT model in apps/api."
---

PantryPulse pins `ortools` 9.15.6755 in apps/api/uv.lock. Check API names against that version with the context7 tool (`/google/or-tools`) rather than memory; examples below use the snake_case API that 9.15 provides. On this Windows host, Application Control blocks OR-Tools natively, so run solver code and tests in Docker: `npm run dev:api:docker`, then `npm run test:api:docker`.

## Model hygiene

- Give every variable a tight domain from the data (0..request, 0..eligible lot quantity). No arbitrary huge bounds.
- Prefer `only_enforce_if` over hand-written big-M. If a big-M is unavoidable, derive it from the variable domains and test both sides of the boundary.
- No floats in constraints or the objective. Scale rationals to integers and record the scale in the policy and the snapshot.
- Before solving, assert that every |coefficient| times its domain, summed, stays far below 2**63.

## Encodings

```python
from ortools.sat.python import cp_model

m = cp_model.CpModel()
# Reified strict threshold, both directions: b <=> q > A
b = m.new_bool_var("ap_flag")
m.add(q >= A + 1).only_enforce_if(b)
m.add(q <= A).only_enforce_if(~b)

# Maximum (Chebyshev term)
z_max = m.new_int_var(0, q_upper, "z_max")
m.add_max_equality(z_max, q_terms)

# Exact floor of a linear expression over a positive constant D:
# q = floor(expr / D)  <=>  q*D <= expr <= q*D + D - 1
m.add(q * D <= expr)
m.add(expr <= q * D + D - 1)

# Nonnegative excess: E = max(0, expr)
m.add_max_equality(E, [0, expr])  # linear expressions and constants are accepted
```

These four encodings and the ADR 0001 two-beneficiary oracle were checked against ortools 9.15.6755 in the API container on 2026-10-24: classical picks a=1; research picks a=2 with no penalties or gamma_RP=0.1, and a=1 with gamma_RP=1.

## Solve parameters for replay

```python
solver = cp_model.CpSolver()
solver.parameters.num_workers = 1        # repeatability; record it
solver.parameters.random_seed = SEED     # from the snapshot
solver.parameters.max_time_in_seconds = TIMEOUT
status = solver.solve(m)
```

Store the ortools version, seed, worker count, time limit and model hash in the plan snapshot. One worker with a fixed seed improves repeatability; it does not promise identical ties across solver versions, so replay tests assert feasibility and objective equality, not an identical vector.

## Status handling

- Keep the native status (`solver.status_name(status)`): OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, MODEL_INVALID.
- Read variable values only for OPTIMAL or FEASIBLE. UNKNOWN and MODEL_INVALID return no vector.
- Report `solver.objective_value`, `solver.best_objective_bound` and the gap. FEASIBLE is never relabeled OPTIMAL.
- MODEL_INVALID is an implementation error: log `m.validate()` output and fail the request with a structured error.
- INFEASIBLE means contradictory hard constraints, not scarce supply. Unavoidable shortage is unmet slack. To explain a real INFEASIBLE, add assumption literals and read `sufficient_assumptions_for_infeasibility()`.
- Two-stage (lexicographic) solves fix the stage-1 objective only when stage 1 is proven OPTIMAL. The V4 research objective is a single weighted objective, so use two stages only where the frozen policy requires them.

## Independent verification

- A pure-Python evaluator recomputes conservation, FEFO, capacities, deficits, flags and objective terms from the returned vector, and must agree with the solver.
- For tiny instances, enumerate every allocation and check that CP-SAT's objective equals the enumerated optimum.
- Run the encodings' boundary tests at exactly the threshold, one unit below and one unit above.
