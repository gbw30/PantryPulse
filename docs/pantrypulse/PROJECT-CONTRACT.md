# PantryPulse project contract

> Superseded where conflicting with the authoritative V4 tab. Start with [ADR 0001](../architecture/0001-v4-research-first.md) and the [V4 implementation plan](IMPLEMENTATION-PLAN.md). In particular, use six beneficiaries plus hub(s), hard lot/FEFO constraints, and paired CLASSICAL_GP/EGP_PI_INSPIRED with active AP/RP objectives. The three-site and shortage-first rules below are historical.

Status: proposed implementation contract derived from source spec v1.0 and the supplied orchestration research. Product requirements below come from the spec; details labeled decision resolve gaps for the 48-hour build. Record accepted changes in an ADR before changing shared schemas.

## Scope and product behavior

One simulated network contains North Community Pantry, Central Community Pantry and South Community Pantry. There are two resource categories, shelf-stable meals and bottled water. Use explicit unit labels such as meal and bottle. Aim for 60–120 historical daily observations per site/category; seed 90 as an implementation choice. Forecast seven future site-local dates. Plan transfers within the next 24–72 hours. The user sees stock, forecasts, first projected deficit, feasible transfers, remaining unmet demand and a changed-scenario comparison.

P0 includes site inventory, manual adjustments with reasons, CSV demand import with row errors, seven-day forecasts, fallback, deterministic projection, labeled uncertainty, immutable scenarios, OR-Tools allocation, explanation, before/after comparison, failure states, persisted replay inputs and demo reset. Maps, routing, accounts, notifications, Gemini scenario chat, calibrated stockout probabilities and real dispatch are deferred. Do not drop CSV import or reproducibility just because the main demo works.

Decision D01 resolves a source priority conflict: the MVP overview mentions approval, while FR-16 and the actual approval endpoint are P1. P0 uses **Mark reviewed — simulation** and records a review event with no stock reservation, physical movement or claim of commitment. A P0 plan remains draft/stale/cancelled. Implement an approved state only with P1 atomic reservations and a separate completion event. If the human chooses to promote approval to P0, add the transaction/concurrency/idempotency tests before exposing that control.

## Architecture and ownership

Use Next.js App Router, React/TypeScript, Tailwind, customized shadcn/Radix primitives, Motion for React and Recharts. FastAPI/Pydantic owns all domain validation. SQLAlchemy/Alembic and PostgreSQL own persisted data. Chronos-2 and the seasonal-naive baseline implement one provider interface. OR-Tools and pure projection functions remain Python modules in the API service. No microservice split for the MVP.

Recommended layout:

```text
apps/web/                         Next.js and frontend tests
apps/api/app/main.py              FastAPI entry point
apps/api/app/routers/             /api/v1 routes
apps/api/app/schemas/             Pydantic contracts
apps/api/app/models/              ORM models
apps/api/app/repositories/        persistence helpers
apps/api/app/services/forecasting/
apps/api/app/services/inventory/
apps/api/app/services/optimization/
apps/api/tests/                   unit and DB integration tests
apps/api/migrations/              Alembic
packages/contracts/openapi.json
packages/contracts/src/schema.d.ts
data/demo/                       deterministic fixtures and provenance
docs/pantrypulse/                 accepted contracts and evidence
```

Lead owns all schemas, migrations, lockfiles, manifests, shared tokens, generated contracts and CI. Forecast owns forecasting plus projection. Solver/data owns allocation and plan repositories; lead owns inventory mutations and migration integration. Frontend owns user interface and scenario interaction. Approve exact file boundaries in every task packet; a service directory label alone is not an exclusive lock.

## Identity and data contracts

Use UUID primary IDs. Golden unit-test fixtures may use readable aliases; seed generation maps them to stable UUIDs. Keep UTC timestamps separate from site-local operational DATE fields. Demo sites use America/New_York as a documented choice. Day boundaries must use the site's zone, not server UTC. Store a fixed demo anchor date separately from the real creation timestamp.

| Entity | Required fields and constraints |
|---|---|
| Organization | id, name, is_demo, created_at; exactly one network for MVP |
| Site | id, organization_id, name, timezone, priority_weight > 0, optional nonnegative receiving limit |
| Resource category | id, name, unit; optional integer handling coefficient for aggregate capacity |
| Inventory lot | id, site_id, category_id, quantity_on_hand >= 0 integer, expires_on nullable, received_at, data_source |
| Demand observation | unique site/category/date; requested nullable, fulfilled >= 0, unmet nullable; if all supplied requested = fulfilled + unmet; source_type |
| Scheduled supply | site/category/date/quantity/status; confirmed contributes by default, expected only in an explicit scenario |
| Forecast run | id, provider/requested provider/actual model/checkpoint revision, cutoff, generated_at, horizon, status, fallback flag/reason, dataset version and provenance |
| Forecast point | unique run/site/category/date, p50 finite >= 0, p10/p90 nullable, interval_method; quantiles ordered where present |
| Scenario | id, forecast_run_id, name, validated overrides, created_at; no mutation of history or baseline run |
| Allocation plan | id, scenario_id, inventory_version, solver_status, plan_status, snapshot hash, unmet by category, cost, assumptions, solver parameters, generated_at |
| Plan transfer | plan/from/to/category/quantity > 0/planned date/estimated cost/status; from != to |
| Inventory movement | site/category/optional lot, signed quantity, reason, transfer id, timestamp, idempotency key |
| Reservation P1 | transfer/lot/quantity/status; available excludes active reservations exactly once |

Source spec indexes and uniqueness constraints remain required: demand site/category/date; inventory site/category/expiration; forecast run/site/category/date; plan transfers by plan; supplies by site/category/date. Include database CHECK constraints for count validity. Requests still require backend validation; DB integrity is an additional layer.

## Forecast provider contract

Input is six separately identified daily series with site-local dates, historical target and explicit missingness flags. Requested demand is the preferred target. Fulfilled counts alone are a censored proxy; retain and show that warning. Reject duplicate observations by key and nonfinite/negative input. Never silently repair source demand. Record an imputation policy if one is accepted; fit it only on past observations.

Output is a run with seven dated points for each eligible series, actual provider/checkpoint, training/context cutoff, source label, horizon, optional quantiles, interval method and fallback reason. Provider outcomes are queued/running/succeeded/failed; fallback success is succeeded with fallback metadata. Unsupported series need an explicit per-series status, rather than being silently omitted.

Decision D02: seasonal naive requires a valid observation on the previous matching weekday for each output. Use the seven most recent daily values as a repeating weekly pattern only when those dates are complete. If insufficient, use a documented trailing seven available-observation mean with a minimum of three valid observations; otherwise label insufficient_data. These thresholds are MVP choices and must be tested. Do not fill gaps with zero or invent uncertainty around the baseline. If baseline has no tested interval method, quantiles are null and interval_method is none.

Chronos runs behind a lazy adapter with a measured time/memory budget. Provider import/download/load/predict failures invoke the permitted baseline fallback. A timeout must terminate or contain the work; abandoning a request while inference continues indefinitely is not a bounded implementation. Prefer precomputed, fingerprinted model results for the prepared demo and baseline live replanning if hardware is limited. A cached forecast identifies the actual provider and its timestamp; never relabel a baseline as Chronos.

Model integration tests establish shape, dates, leakage boundaries and failure handling. Accuracy requires a separate chronological holdout, identical evaluation windows and MAE/WAPE/bias compared to the baseline. WAPE is sum absolute errors / sum observed demand; a zero denominator returns unavailable with a reason, not infinity or a fabricated zero. Quantile coverage is evaluated only on held-out observations. Keep raw model quantiles distinct from calibrated intervals and policy buffers.

## Projection and inventory accounting

Decision D03 uses **lost sales**, not backlog, for unmet demand: unserved requests on one day are recorded as unmet and are not automatically requested again tomorrow. For each site/category/day, add eligible arrivals at the start of day, subtract committed outbound transfers that depart that day, then serve that day's projected demand. Let A[t] be available stock after those events. Then:

```text
served[t] = min(max(A[t], 0), demand[t])
unmet[t] = demand[t] - served[t]
end_stock[t] = max(A[t] - demand[t], 0)
total_unmet = sum(unmet[t])
```

Reject a commitment schedule that drives A[t] below zero before demand. Keep a separate signed cumulative net-balance series for the first theoretical deficit date; never sum its negative values as daily unmet units. Example: stock 40, demand 50 then 40 gives daily unmet 10 and 40, total 50. Signed balances -10 and -50 do **not** mean 60 unmet units.

Arrivals count only on/after their eligibility date. Expired stock is excluded. Decision D04 treats a lot expiring on D as ineligible on D; show this demo policy, not a food-safety assurance. If expiries occur inside the horizon, deterministic daily eligibility must remove stock by date even when the optimizer uses aggregated donor budgets. P1 lot-level dispatch remains deferred. If that removal is unsupported, disallow within-horizon expiry fixtures and state the limitation.

Reservations reduce transferable availability. An approved incomplete transfer remains physical stock at origin and a commitment in the projection; do not subtract it once as a reservation and again from physical stock. Completion atomically moves physical stock and releases the reservation/commitment. Scenarios never physically move stock. Adjustments increment inventory version and stale incompatible plans. Use the same snapshot/status inclusion rules for every before/after comparison.

Central projection uses p50. Conservative mode uses p90 where available or an explicit user buffer; neither yields a stockout probability. Risk labels are no projected deficit, potential deficit under conservative assumptions, projected deficit under central assumptions, or insufficient data. Sum of daily p90 values is a conservative scenario, not a calibrated aggregate interval.

## Allocation contract and formulation

Decision D05 restricts P0 to one transfer batch arriving before first-day demand, no relay or repeated use of inbound transfers, over a stated 1–3-day horizon. Do not claim full scheduling or routing. Site closures affect demand and route availability according to explicit scenario fields; disabling a route does not erase a site's needs.

For site i, category c: eligible physical stock S; confirmed supplies available by batch dispatch; local protected demand D over the allocation window; end-of-window minimum reserve R. Compute donor budget conservatively as max(0, stock available at dispatch - protected local demand - reserve). Later donor receipts do not increase this P0 early-batch budget, though they still appear in daily projections. This deliberately conservative feasible region must be disclosed when claiming optimality. A receiver with unavoidable unmet demand is not forced to meet an impossible end-stock reserve; reserve is a donor-protection policy unless the human explicitly chooses a stronger hard constraint.

Integer variable x[i,j,c] >= 0 exists only for allowed non-self routes. Outgoing <= donor budget. Inbound <= receiving capacity. Total sum(a[c] * x) <= handling capacity, where a[c] is a documented integer conversion. Do not sum bottles and meals as comparable food quantities. The source spec's generic max_total_transfer_units becomes a shared **handling-unit** budget with documented coefficients; category quantities remain separate.

Demand used by the integer solver is ceil(scenario_multiplier * forecast_daily_point) per day; retain unrounded forecast values for charts/evaluation and store this rounding rule in the snapshot. CP-SAT objective weights/costs are integer-scaled with documented scales. Confirm ranges do not overflow. Use finite domains from available stock/capacity, not arbitrary huge bounds.

Minimize a policy-weighted shortage score first, then movement cost/avoidable transfers. Site/category weights make the priority policy explicit; the score does not make bottles and meals interchangeable, and UI unmet quantities remain separated by category. Prefer two solve stages: fix the best primary objective only if stage 1 proves OPTIMAL, then minimize cost. If stage 1 is only FEASIBLE, return that status and incumbent; do not assert a globally optimal shortage/cost tradeoff. If stage 2 times out, retain the validated incumbent and report cost optimality as unproven. Retain native statuses OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN and MODEL_INVALID; extend the source spec's response enum for the last error status, or map it to a structured implementation error. Never extract unproven variable values from UNKNOWN/MODEL_INVALID.

After solve, independently check the transfer vector and recompute daily before/after projections. Partial shortage is modeled explicitly with unmet slack, so a network with no resources generally has a feasible zero-transfer plan with remaining need. INFEASIBLE is reserved for contradictory hard constraints. Failed/unknown plans offer retry/change-assumptions controls and no false recommendation.

Replay stores immutable dataset/forecast/scenario/supply/inventory snapshots, eligible-lot policy, versions, routes, unit scales, priorities, model/solver versions, seed, worker count, limits, arrival assumptions and input hash. Tie solutions can differ; assert feasibility and objective equivalence, unless deterministic tie-breaking was actually implemented. A single-thread seed improves repeatability without promising identical output across versions.

## API contract

All application routes use /api/v1 and JSON except multipart CSV upload. Errors use `{ "error": { "code": "...", "message": "...", "details": {} }, "request_id": "..." }`. Every mutation has a request ID. Approval/completion additionally require an idempotency key. Translate framework validation errors into the same envelope.

| Method and route | Required behavior |
|---|---|
| GET /dashboard/summary | Latest committed data, counts/by-category quantities/risk/latest run/provenance; no inference on read |
| GET /sites | Three sites within active organization |
| GET /sites/{id}/inventory | Physical, eligible, reserved if P1, and scheduled incoming stock by category |
| POST /inventory/adjustments | site/category/delta/reason/expected_inventory_version; transaction, nonnegative check, movement, increment version, stale plans; 201 |
| GET /demand/history | Filter site/category/start/end, chronological order and provenance |
| POST /demand/import | Multipart CSV with required source headers, specific row errors and accepted/rejected counts; duplicate keys rejected |
| POST /forecast-runs | organization/horizon/model/allow_fallback; 202 queued or 201 already completed; UI reads returned status |
| GET /forecast-runs/{id} | Actual provider/status/error/fallback/evaluation metadata |
| GET /forecast-runs/{id}/points | Dated points, quantile method and per-series availability |
| GET /shortages | forecast/scenario/planning mode/snapshot; first deficit, quantity and horizon/category assumptions |
| POST /scenarios | name/forecast_run_id/validated overrides; baseline unchanged; 201 |
| GET /scenarios/{id} | Immutable overrides, linked plans |
| POST /scenarios/{id}/plans | planning_days/priority policy/handling budget/solver time limit; persisted result with native status and validated vector; 201 |
| GET /plans/{id} | Snapshot/version/status/assumptions/transfers/before-after metrics |
| POST /demo/reset | Dedicated demo organization only, presenter authorization and rate limiting, reset audit; returns dataset version |
| POST /plans/{id}/approve P1 | Expected inventory version, idempotency key, atomic reservation, 409 conflict |
| POST /transfers/{id}/complete P1 | Idempotent, transactional paired movement and reservation release |

P0 simulated review can be stored as POST /plans/{id}/review with decision/note, explicitly no stock effect; this route is an implementation extension. If omitted, keep review purely a UI action and do not claim persistent approval.

Decision D06: allow scenario demand multiplier 0–3 inclusive, nonnegative integer supply/capacity overrides, positive bounded priority weights and known IDs only. Reject NaN, infinity, unknown fields and dates outside the chosen window. These bounds are demo policies, not universal operational limits. Public job submission has a short concurrency limit and timeout; expose run status and disable repeated clicks while pending. Preserve server validation regardless of UI constraints.

CSV headers are site_id,category_id,demand_date,requested_units,fulfilled_units,unmet_units,source_type. Set upload size/row limits and reject unexpected columns rather than guessing mappings. Decision D07: valid nonduplicate rows can be accepted while invalid rows are returned, atomically storing each accepted batch with an import ID; report row numbers. Do not overwrite existing history. Test repeated uploads.

## UI contract

Overview answers which site is at risk, when and what action can help. Show category filter, visible scenario identity, inventory/demand/unmet metrics by category, seven-day timeline, site statuses and main plan CTA. Site detail has stock, history, forecast, balance, incoming/outgoing and relevant transfers. Explorer shows quantiles, cutoff, method and central/conservative controls. Planner shows origin/destination/category/quantity, constraints, before/after horizon and solver status. Scenario editor shows draft versus applied assumptions and a deliberate Recalculate action.

Every async action has idle/loading/success/empty/error states. Add stale plan after changed inventory or assumptions; degraded forecast state; insufficient data; FEASIBLE without optimal proof; INFEASIBLE and UNKNOWN. Keep last successful data visible with its timestamp while a new run executes. Use request sequence IDs or abort logic so a slow old response cannot replace a newer scenario. Never animate mock numbers as if they came from a solve.

## Performance and trust targets

Spec targets are cached dashboard reads below one second in ordinary conditions and seeded solves below five seconds; measure on the demo host and report percentiles/run count where useful. Bound forecasting separately; no hosting guarantee is implied. All displayed product benefit is projected/simulated, compared on the same data, category, horizon and assumptions. No observed real-world impact or guaranteed food-safety claims. Expose model, data and solver limitations in a concise details drawer with readable defaults.
