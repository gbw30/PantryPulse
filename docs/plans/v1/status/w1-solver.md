# Status — `w1-solver`

**Lane:** `w1-solver` · **Branch:** `lane/w1-solver` · **Base SHA:** `39090104222e6a67b60f8d9fa0c9e798c68a38d7` · **Last update:** `2026-11-07` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W1-S01 | in progress (`usd-flip` escalated, see Escalations) | — | — |
| W1-S02 | todo (Pantry baselines need CR-w1-solver-1) | — | — |
| W1-S03 | todo | — | — |
| W1-S04 | todo (Pantry methods need CR-w1-solver-1) | — | — |
| W1-S05 | todo | — | — |
| W1-S06 | todo | — | — |
| W1-S07 | todo | — | — |

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- (none yet)

## Gotchas

- `ORInputV3` (`apps/api/app/schemas/v1_planning.py:206`) uses string IDs and v1 caps, so it cannot be fed to the v2 pipeline (`ORInputPackage`, UUID IDs). The v3 methods get a v3-native path that reuses the pure FEFO kernel (`services/optimization/kernel.py`).

## Change requests

### CR-w1-solver-1 — Pantry allocation window and EGP policy in the frozen v3 scenario
- **File(s):** `apps/api/app/schemas/v1_planning.py` (`ORInputV3`, `ScenarioOptions`); the scenario builder in `apps/api/app/services/networks/` that freezes it; regenerated contracts in `packages/contracts`.
- **Exact change (orchestrator's proposal, 2026-11-07):** `ORInputV3` gains `planning_days: int` (1..3, required in PANTRY, absent in RETAIL, validated like `retail_weights`) and `policy: ORPolicy` (`app/schemas/or_inputs.py:422`; required in PANTRY, absent in RETAIL). `ScenarioOptions` takes both; the policy defaults to the connected-flow values and is recorded in the frozen scenario.
- **Why:** `ORInputV3` has neither field. v2 carries both explicitly (`or_inputs.py:515` `planning_days` 1..3; `ORScenarioPayload.policy`). BD-50 requires an explicit 1–3-day window, and V1-SPEC §6.2 requires λ/β/coefficients to be shown and editable, so they must be frozen with the scenario rather than hardcoded in the solver. Pantry need (window unmet), BD-51 (consumption inside the window), the at-risk screen for Pantry, and the CLASSICAL_GP/EGP_PI_INSPIRED objectives all read them.
- **Unblocks:** W1-S02 (EQUAL_SHARE, MOST_URGENT_FIRST), W1-S04 (Pantry five-method comparison), W1-S05 (Pantry at-risk screen and Pantry benchmark), W1-S06/S07 Pantry cases. Retail work proceeds meanwhile.
- **Status:** open (orchestrator taking it to Gabriel). Field-dependent code reads `scenario.planning_days` and `scenario.policy` as proposed; nothing in this lane touches the contract.

## Escalations

- 2026-11-07 — W1-S01 `retail-usd-flip` — spec ambiguity ([ORCHESTRATION.md §5](../ORCHESTRATION.md) item 4). The wave file asks for a fixture whose optimal RETAIL_OPTIMIZED transfer changes between units and USD. Under the W0 decision (`decisions/W0-optimizer-decomposition.md` §1–2, V1-SPEC §6.2) each product is solved alone. Its USD objective is `price_p × (w_exp × expired_p + w_lost × lost_p)`, a positive multiple of its units objective, so the argmin is the same. Shared capacity is split in advance by need × handling units, not by value. So no plan can flip between the measures. Smallest case: one product, any scenario, so the USD objective = price × the units objective. Two products sharing one route capacity give the same result, because the split doesn't depend on the measure. Options for the lead: (a) keep the fixture as a "no flip under per-product solving" regression, with the hand-derived monolithic flip recorded in the README for reference; (b) split shared capacity in USD mode by need × handling × unit value (a change to the decision's split rule). The other four fixtures proceed.
