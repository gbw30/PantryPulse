# Local API implementation on VP

The local backend includes authentication, persisted forecast jobs, inventory,
audited stock adjustments, receipt history/posting/reconciliation, lot declarations,
supplies, history imports, dashboard/shortages, and saved allocation workflows.
Supplier procurement remains paused. Commit and publication history is tracked on VP.

## Start and explore

In a VS Code PowerShell terminal:

```powershell
cd D:\Hackathon\apps\api
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --env-file .env
```

Restart an existing server to load the new routers. Open
[Swagger](http://127.0.0.1:8000/docs). Login through presenter/login with the private
local credentials. The session cookie authenticates subsequent requests. Writes
also require the returned X-CSRF-Token, an allowed Origin and an Idempotency-Key.
Use the same key only when replaying the identical request. IDs and versions come
from API reads; do not invent them. Operational quantities/versions use decimal
strings. Swagger request models show required fields.

The dedicated demo schema is migrated through pp49_0006. Public schema was not
changed. Never run migrations against a different schema without selecting it
deliberately. No stock was created solely for this smoke check.

## Route groups

All paths below have the prefix `/api/v1`.

| Area | Routes and behavior |
| --- | --- |
| Catalog | GET operational-catalog provides actual site/product/donor/source IDs |
| Receipt history | POST receipts; GET receipts/{id}; POST receipts/{id}/revisions |
| Receipt stock | POST receipts/{id}/post; POST receipts/{id}/reconcile |
| Eligibility | POST inventory/lots/{id}/declarations |
| Supply | POST/GET supplies; GET supplies/{id}; POST supplies/{id}/confirmation |
| History imports | POST imports/demand, imports/demand/csv, imports/donation-coverage |
| Dashboard | GET dashboard/summary; GET shortages/{forecast_run_id} |
| Planning inputs | POST or/input-packages/from-sources or or/input-packages; GET or/input-packages/{id}; POST or/policies; GET or/policies/{id} |
| Scenarios | POST/GET scenarios; GET scenarios/{id} |
| Allocation | POST scenarios/{id}/plans or compare-methods; GET plans/{id}, comparisons/{id}, allocation-jobs/{job_id}/results |
| Review | POST plans/{id}/review records a decision without moving stock |
| Methodology | GET allocation-methodology documents modes and limitations |

Create receipt history first, then explicitly post it to stock. Corrections save
history independently; reconciliation can reject a negative balance and leave a
visible mismatch. Voids follow the same audited rule. A downward correction never
silently reconfirms future supply. Stock with a stated expiry is usable through
that date; explicit non-expiring stock is allowed and unknown expiry is excluded.

Demand CSV accepts UTF-8, at most 100 rows/60KB, with these headers:
`source_record_key,site_id,product_id,day,expected_revision,requested,fulfilled,unmet`.
Empty nullable quantities remain missing. JSON imports also enforce revisions and
atomicity; donation coverage is an explicit complete-reporting declaration.

## Planning flow and limits

Complete a saved seven-day forecast, capture actual sources with explicit route,
capacity, reserve and policy inputs, create a scenario, submit a plan or method
comparison, poll its job and read the saved result. Select HUB_ONLY for hub-to-
pantry or HUB_AND_PANTRY to also permit pantry-to-pantry transfers. Transfer mode
and CLASSICAL_GP/EGP_PI_INSPIRED method are separate choices.

One transfer batch serves an explicit 1–3-day window in a shared planning timezone.
Donors protect attained service across all seven days plus configured reserves.
Every transferred unit must add receiving service within the window. Source
versions are checked at admission/publication; stale saved records remain readable.
Planning and review simulate allocations without reservations or ledger changes.

Source capture currently requires the full active network, at most 14 sites and
two products, and explicit bounded resources. It validates forecast/current units,
calendars, ledger consistency and outstanding-supply scope. Supplies currently
lack expiry declarations and therefore remain unknown/unusable for planning.
Hub zero demand is an explicit planning convention, never a fabricated ML row.
Executable packages/scenarios use v2. Policy coefficients remain explicit draft
inputs. Fixed route loading order limits the feasible region; no unrestricted
optimality or exact research-paper reproduction is claimed.

Native OR-Tools has run successfully in local tests. Actual queued execution still
requires a live supervised Linux worker; without its heartbeat, submission returns
503 COMPUTE_UNAVAILABLE. Direct handler tests do not replace that end-to-end check.
The frontend proxy supports these routes, but the dashboard UI still needs actual
API binding. Chronos provider implementation, browser journey, independent review
and deployment/release verification remain outstanding.
