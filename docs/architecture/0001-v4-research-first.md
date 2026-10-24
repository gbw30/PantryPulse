# ADR 0001: V4 research-first architecture

## Accepted backend design update: BD-30

The [backend checkpoint](../pantrypulse/BACKEND-DESIGN-CHECKPOINT.md) records accepted design, not implemented or verified domain behavior. Scenario creation requires explicit `transfer_mode`, without a default:

| Transfer mode | Eligible recommendations |
|---|---|
| `HUB_ONLY` | Hub-to-beneficiary transfers only. Pantry inventory reduces local need; no pantry-to-pantry transfers. |
| `HUB_AND_PANTRY` | Hub transfers plus eligible pantry surplus transfers. Protect sending pantry demand and applicable reserves through dated projections; enforce route eligibility, capacity, arrival timing, lot eligibility and expiry. Incoming stock cannot be forwarded within the same allocation batch. |

Freeze mode and all inputs at scenario creation in a validated, versioned, content-hashed JSONB package with provenance/source references. Changing mode or inputs requires a new scenario. Include `transfer_mode` in scenario, result, comparison and methodology metadata separately from allocation `method`. Both `CLASSICAL_GP` and `EGP_PI_INSPIRED` support both modes. Paired comparison uses the same frozen scenario, mode, inputs and operational constraints; only defined method objectives differ.

The two main computation workflows are:

1. Demand forecasting uses historical daily pantry/product demand to predict the next seven days. Historical observations, current inventory and saved forecast results remain separate database concepts. Forecast demand represents predicted need, never net shortage; do not subtract inventory from stored forecasts. Retain already specified baseline guidance; unresolved minimum-history/fallback details remain OPEN-13.
2. Allocation and comparison use a selected saved forecast, eligible current stock, qualifying confirmed arrivals and frozen assumptions. Dated projection derives shortages and eligible surplus while respecting demand timing, expiry, capacity and donor protection. Pantry surplus is not simply stock minus aggregate demand.

Forecasting, allocation and paired comparison are background jobs: submission returns `202 Accepted` and a job reference; separate reads expose persisted status and committed results. Two workflows do not mean exactly two HTTP endpoints. Keep inventory, scenario, job, result and comparison operations. Exact wire contracts/job states remain OPEN-29/30.

OPEN-01 product choice is resolved. Snapshot schema, reserve/event rules, routes/capacity, API details and independent validation remain OPEN-19/21/22/29/34. OPEN-02 benefit attribution and OPEN-03 supplier-budget priority remain deferred. Plan review records actor, plan/version and time without reserving, dispatching or changing stock. Forecast donations create neither physical inventory nor confirmed supply. Draft supplier proposals remain included and conditional, outside the confirmed-resource primary comparison. The main demo still requires at least six beneficiaries plus hub(s); smaller examples do not change this. Research adaptation limits and independent validation remain required. Hosting/model setup stays paused.

Date: 2026-10-23. Accepted for scaffold; mathematical implementation remains gated.

## Authority and findings

[V4](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.951hp1xdarlq) is authoritative. The [snapshot](../pantrypulse/SPEC-V4.snapshot.txt) records tab/revision identity; tables are linearized and diagrams omitted.

Initial repository: V1 orchestration kit, Compose database, three-site golden fixture, staged ENVIRONMENT.md edits, and an untracked nested PantryPulse/ copy with another kit and Next starter. Preserve those files. Canonical application paths are apps/web and apps/api at the outer Git root; the nested copy is not a workspace.

V4 extensions supersede inherited examples, including those still inside V4:
- Six beneficiary institutions plus one hub initially, optionally two hubs; two categories.
- Lot-aware expiry and FEFO are P0; aggregate donor budgets are insufficient.
- CLASSICAL_GP versus EGP_PI_INSPIRED is the primary P0 comparison; no-action/greedy are supplemental.
- Section 11's research objective supersedes the older shortage-first lexicographic objective, which could erase the fairness trade-off.
- Fixed proxy weights approximate endogenous research weights. Procurement and dispatch remain simulation-only.

## Research validation boundary

Rampazo et al., *An extended goal programming framework incorporating poverty measures: application to food bank logistics*, [DOI 10.1111/itor.70252](https://doi.org/10.1111/itor.70252).

The [publisher listing](https://onlinelibrary.wiley.com/doi/full/10.1111/itor.70252) and [author institution record](https://researchportal.port.ac.uk/en/publications/an-extended-goal-programming-framework-incorporating-poverty-meas/) confirm September 11, 2026 publication. The institutional abstract describes poverty-sensitive deviations, endogenous vulnerability weights and multi-period FEFO inventory. This verifies the research premise, not our implementation or competition acceptance.

Full-text retrieval timed out in this task. Sections 2.1.3, 3 and Appendices A/C still require equation-level review before complex solver work. The formulas below follow V4's bounded adaptation, not independently verified published equations (8)–(38). No solver features have been implemented.

## Modular architecture

One Next.js App Router frontend; one FastAPI application. Python owns validation, policy, metrics, feasibility, forecasting and SQLAlchemy persistence. Pydantic/OpenAPI generates TypeScript after research schemas are validated. No duplicate frontend optimizer or microservice split.

| Path | Responsibility |
|---|---|
| apps/web/src/app | Presentation and method comparison |
| apps/web/src/components/ui | shadcn components when needed |
| apps/api/app/routers, schemas | Versioned routes, strict request/result contracts |
| apps/api/app/models, repositories | ORM and transactional persistence |
| apps/api/app/services/inventory | Lot ledger, FEFO, dated projections |
| apps/api/app/services/optimization/constraints.py | Shared feasible region |
| optimization/policy.py | Attribute weights, groups, scales |
| optimization/classical_gp.py | Conventional normalized GP |
| optimization/egp_pi_inspired.py | Reified AP/RP and W/Z objective |
| optimization/metrics.py | Independent result evaluation |
| apps/api/app/services/forecasting | Seasonal naive; lazy Chronos adapter |
| apps/api/migrations, tests | Alembic, unit and PostgreSQL tests |
| packages/contracts | Generated OpenAPI/TS boundary |
| data/demo | Simulated immutable fixtures |

Only process health is implemented in the API. Domain directories establish boundaries, not functionality. Bound solver execution; isolate optional model inference in a terminable subprocess. Never load/download models or infer on startup/GET.

PostgreSQL 16 locally on 127.0.0.1:55432; Neon later using server-only psycopg/TLS. No hosted resources provisioned. Domain migrations follow research contract validation; SQLite cannot validate PostgreSQL behavior.

Environment finding: Windows Application Control rejected a pandas native DLL imported by OR-Tools. A Docker API development profile uses the same uv.lock on Python 3.12.13/Linux, without changing host policy. It copies source on build and exposes only 127.0.0.1:8000. Native health tests alone cannot prove solver availability. The container is a development image with test tools, not a production image.

## Proposed V4 mathematical contract

For positive target request r at institution i/category p: fulfilled f is integer in [0,r], unmet u=r-f, delta=u/r. Count eligible local service and incoming allocation exactly once. Zero targets have service ratio null, deficit zero, no flags, and are excluded from all deprivation/group denominators.

At least two institutional attributes a in [0,1], simulated in demo; coefficients c>=0 sum to 1. v=1+lambda*sum(c*a), initially lambda=1 to bound v in [1,2]. z=v*delta; W=sum(z); Z=max(z); B=beta*W+(1-beta)*Z.

AP flag iff z>tau_AP. RP flag iff z-mean(group z)>tau_RP. Equality is unflagged. Default group: positive-target beneficiaries of the same category, including self, minimum two members. Reject undefined/singleton groups. Per category F=sum(flags)/N; excess=max(0,F-cap). Research objective: B+gamma_AP*AP_excess+gamma_RP*RP_excess+epsilon_cost*normalized_cost+epsilon_waste*normalized_waste. Both gamma values are positive.

Classical uses ordinary policy weights independent of vulnerability/AP/RP, the same conventional blend and ancillary coefficients. Research metrics evaluate BOTH outputs with the same evaluation policy without influencing the classical solve. Category aggregation/normalization must be frozen before coding; never sum meal/bottle quantities into an unlabeled total.

Proposed numeric policy for validation: S=10,000; rational v; q=floor(S*v*u/r). AP uses q>A; RP uses N*q-sum(q)>N*T, integer thresholds A/T. Reify both directions so false flags cannot evade penalties. Retain exact ratios alongside q. Quantization is part of the approximation; test equality and near-boundary behavior against exact rational arithmetic. Before coding either accept this policy and its error bounds or choose exact rational cross multiplication with bounded denominators. Prove coefficient/domain bounds fit int64.

Excess shares are soft goals, not hard caps: scarce supply still permits unmet slack. UNKNOWN/MODEL_INVALID return no vector; FEASIBLE does not imply optimality. Report objective bounds/gap and decomposition.

## Shared hard constraints

Same immutable content-hashed lots, requests, dates, supplies, routes, capacities and evaluation policy for both methods. One early batch over a 1–3-day allocation window; seven-day projections. No relay/reuse of inbound stock.

Preserve stock, active reservations, protected donor demand/reserves, product/unit compatibility, arrival/use dates, receiving and handling capacity, no self-transfer and no overdelivery. Expiry date D excludes use on D under disclosed demo policy. Enforce FEFO among otherwise interchangeable eligible lots; sorting display or a small cost preference is insufficient. Record exceptions for earlier lots unable to reach a receiver in time. Independently verify every solution through a pure ledger/projection evaluator.

Shipment is not automatically fulfillment. Demand rounds up per dated scenario value. Daily lost-sales unmet must not sum overlapping cumulative deficits. Donation forecasts remain uncertain and separate from confirmed arrivals; stock is never counted twice.

## Independent oracle and implementation gate

Hand-check a two-beneficiary one-category case: requests (2,2), supply 2, v=(2,1), beta=0.5, AP threshold 0.75, RP threshold 0.25, allowed shares 0. For first-beneficiary allocation a:

| a | z | W | Z | AP share | RP share | B |
|---|---|---|---|---|---|---|
| 0 | (2,0) | 2 | 2 | 0.5 | 0.5 | 2 |
| 1 | (1,0.5) | 1.5 | 1 | 0.5 | 0 | 1.25 |
| 2 | (0,1) | 1 | 1 | 0.5 | 0.5 | 1 |

With gamma_AP=1 and gamma_RP=0.1 research favors a=2; gamma_RP=1 favors a=1. Classical v=1/beta=0.5 favors a=1. This is hand arithmetic, not a solver result or the six-beneficiary demo. Add a separate AP threshold-crossing oracle, then six recipients/two categories with meaningful groups and unique objective differences rather than arbitrary ties.

Gate before solver work: full-paper mapping; independent enumeration; coefficient/scaling/category policy; FEFO encoding; same-feasibility proof; AP/RP-specific ablations; deterministic research fixture.

Replay stores dataset hash/version, as-of date, horizon, forecast source/cutoff, inventory version, eligible lots, attributes/provenance, groups, policy/scales, solver/package versions, seed, one worker, limits, vector and metrics. Record method separately from shared operational input hash. One worker/seed improves repeatability; it does not promise identical ties across solver versions.

