# Integrated operational and planning APIs

The reviewed VP candidate converges on current main. See
[VP API integration](VP-API-INTEGRATION.md) for decisions, migration compatibility,
contract replacements and exact evidence. Generated OpenAPI is the request/response
authority; the old raw VP planning endpoints are superseded.

Start the API and production worker using the [current local compute procedure](../setup/LOCAL-COMPUTE.md).
Use a dedicated demo/test schema, current presenter credentials, matching allowed
Origin and CSRF token, and an Idempotency-Key for writes. Quantities and versions in
operational request bodies use exact decimal strings. Never post fictional data to
a production database. The explicit demo loader creates a new isolated schema and
uses audited stock commands; it does not reset an existing database.

| Area | `/api/v1` routes |
|---|---|
| Catalog | GET operational-catalog, forecast-catalog, planning-catalog |
| Inventory | GET inventory/sites/{site_id}/products/{product_id}; POST same path /adjustments |
| Receipt history | POST receipts; GET receipts/{id}; POST receipts/{id}/revisions |
| Receipt stock | POST receipts/{id}/post or /reconcile; POST inventory/lots/{id}/declarations |
| Supply | POST/GET supplies; GET supplies/{id}; POST supplies/{id}/confirmation |
| History | POST imports/demand, imports/demand/csv, imports/donation-coverage |
| Dashboard | GET dashboard/summary and shortages/{forecast_run_id} |
| Frozen planning | POST planning-assumptions (new immutable version); POST scenarios; GET scenarios/{id} |
| Comparison | POST comparisons or scenarios/{id}/compare-methods; GET comparisons/{id} |
| Single method | POST scenarios/{id}/plans; GET allocation-jobs/{job_id}/results and plans/{id} |
| Simulation review | POST plans/{id}/review with expected_result_hash |
| Jobs | GET jobs/{id}; POST jobs/{id}/cancel or /retry |
| Methodology/history | GET allocation-methodology; GET legacy-planning/{scenarios,plans,comparisons}/{id} |

Receipt history never creates physical stock implicitly. Explicit posting and
reconciliation use inventory/supply version expectations and the existing audited
ledger service. A failed reconciliation leaves a visible factual-history mismatch.
Missing demand remains null; imports are atomic and limited to 100 rows. CSV is
UTF-8, at most 60 KB, with headers
`source_record_key,site_id,product_id,day,expected_revision,requested,fulfilled,unmet`.

Generate a committed planning-ready forecast, choose immutable simulated assumptions
and an explicit transfer mode, then freeze a scenario from authoritative database
sources. Plan/compare submits return durable 202 acceptance. Poll jobs and read saved
results; retry keeps the same frozen input/settings. Search defaults to 120 seconds
per method and accepts 1–300 seconds. A new budget means a new computation.

Review records simulation decisions only. Main's connected workspace remains
supported; no general stock/import management screen is introduced here. Forecast
provenance, OPTIMAL/FEASIBLE, bounds/gaps, partial failures and stale/historical labels
remain honest. Outstanding confirmed supply without declared expiry is explicitly
unsupported by the connected allocation adapter.

Atomic imports return accepted/rejected counts. Row validation or transaction
errors provide zero-based record indices and field/error codes, without echoing
submitted values. Historical idempotency replays preserve their saved result shape.
