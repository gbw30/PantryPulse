# V4 prioritized implementation plan

## Accepted backend design update: BD-30

The [backend checkpoint](BACKEND-DESIGN-CHECKPOINT.md) records accepted design, not implemented or verified domain behavior. Scenario creation requires explicit `transfer_mode`, without a default:

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

See [architecture/research gate](../architecture/0001-v4-research-first.md). This scaffold is not a working allocation platform.

| Priority / target | Deliverable | Exit evidence |
|---|---|---|
| 0 / foundation | Root apps, npm/uv locks, Windows scripts, health and web shell | Frozen install; lint/typecheck/build; pytest and Playwright smoke; database readiness separately |
| 1 / hours 0–6 | Read paper 2.1.3/3 and Appendices A/C; policy, group, scale, threshold, FEFO contracts | Equation mapping, independent hand/enumerated oracle, overflow bounds |
| 2 / hours 6–12 | Six-beneficiary/one-hub/two-category simulated fixture; required-mode/frozen-scenario schemas; ledger/FEFO; shared constraints for both modes; CLASSICAL_GP | Conservation, expiry/ETA/use, reserves, receiving/handling capacity and baseline objective tests |
| 3 / hours 12–20 | EGP_PI_INSPIRED with active reified AP/RP, excess shares, W/Z blend and independent metrics | TEST-EGP-01–07, nonzero penalties, paired input hash/mode/feasibility for both modes, interpretable distinct seed, AP/RP ablations |
| 4 / hours 20–26 | SQLAlchemy/Alembic, snapshots/policies/goals/metrics, deterministic reset, paired API and generated TS | PostgreSQL upgrade/downgrade, paired contracts, stale 409, isolated reset, replay |
| 5 / hours 26–30 | Requested demand/donation seasonal baseline, CSV import, manual correction audit, seven-day projection | Missingness/leakage/fallback provenance tests; supply counted once; daily unmet arithmetic |
| 6 / hours 30–40 | Paired comparison, six-beneficiary table, thresholds/attributes/AP-RP chart, donation-cancel replan | Method difference visible within first 30 seconds; accessible controls; stale prior plan |
| 7 / hours 40–48 | Full solver/DB/API/Playwright journey, performance, deployment and recording | Measured runtime; deployed working comparison; reproducible backup demo and limits |

Chronos is an optional dependency extra and follows research proof, with lazy loading, bounded inference and labeled fallback. Supplier proposal and no-action/greedy comparators follow the central comparison. Real purchasing/dispatch, maps, routing, production reservations, RL and advanced model ensembles are deferred.

By hour 20 the research engine must execute; otherwise mark it incomplete and prioritize AP/RP. Do not drop CSV validation, controlled corrections or replay from supporting P0.

| V4 requirement | Planned evidence |
|---|---|
| FR-21/28 | Same snapshot, paired runs, comparison UI |
| FR-22 | Normalization/weights/provenance oracle |
| FR-23 | Fulfillment ledger and zero-demand semantics |
| FR-24/25 | AP/RP reification, equality/group cases, share penalties |
| FR-26 | Scaled W/Z objective decomposition |
| FR-27 | Per-beneficiary metrics and explanations; distinguish proven binding constraints from inferred bottlenecks |
| FR-29 | DOI/date attribution and inspired-subset limits |
| FR-30 | Explicit research method-unavailable; no silent classical substitution |

Before solver code: confirm full-text mapping, freeze quantization/thresholds and int64 bounds, choose category aggregation, validate the six-beneficiary seed and AP/RP ablations, and finalize hard FEFO prefix/eligibility constraints. ADR defaults allow validation to proceed without a preference questionnaire; they remain pending mathematical verification.

