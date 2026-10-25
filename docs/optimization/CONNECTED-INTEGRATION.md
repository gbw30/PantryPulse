# Connected OR integration — approved October 25, 2026

This document records the user's approved scope expansion from the OR-only work
to a connected, isolated simulated application. It supersedes conflicting
OR-only ownership, no-proxy, storage-withdrawal and 15/25/60-second guidance for
this integration. It does not retroactively change the meaning of old evidence.
The integration starts from main `aadd2d2` and OR head `465d026`; merge `505296f`
retains the finalized computational branch without restoring withdrawn workflows.

## Accepted execution contract

| Setting | Default | Maximum |
|---|---:|---:|
| Native search per method | 120 seconds | 300 seconds |
| Method wall allowance | 150 seconds | 330 seconds |
| Sequential comparison allowance | 330 seconds | 690 seconds |
| Queue expiry | 1,800 seconds | 1,800 seconds |

Search accepts integral seconds from 1 through 300. Method allowance is search +
30; comparison allowance is twice the method allowance + 30. Both methods use
the same frozen settings, one solver worker and seed 0. The lane advertises maximum
capabilities, while each comparison stores its actual selected deadlines in
`or-solver-settings-v2`, job identity and replay input. Old capability advertisements
fail admission until the supervisor is restarted. There remains one active and
two waiting jobs. Forecast 270/300-second boundaries are unchanged.

Shutdown drain allows the largest operation ceiling plus 30 seconds (720 total);
the supplied container configuration gives 725 seconds. Existing two-second
termination/publication reserves and ownership/cancellation fences remain inside
the frozen deadline. Retries preserve the original scenario and settings. A new
budget is a new computation against the saved scenario.

## Versioned computation and bounded domain

`or-input-v2`, `or-scenario-v2`, projection, method result, independent verifier
and comparison v2 use inclusive expiry: DATED stock can serve on its expiry date
and expires before service on the next date. NON_EXPIRING is an explicit usable
declaration; UNKNOWN is excluded. This applies to FEFO, candidate generation,
native constraints, projection and independent replay.

Old `data/demo/or-v1` fixtures and qualification JSON are historical and unchanged.
`scripts/or/upgrade_fixtures.py` explicitly produces newly hashed v2 fixtures;
v1 snapshots cannot pass v2 replay validation. Policy mathematics remains the
branch's provisional research formulation. Its editable simulated preset is not
evidence of real-world policy validity or social benefit.

The supported core remains at most 12 beneficiaries, two hubs, two products,
256 lots/arrivals, seven projected dates, and one first-day dispatch batch within
an explicit 1–3-day allocation window. Both transfer modes remain explicit.
Unsupported shape, numerical precision/bounds, singleton relative-deprivation
groups, overlapping commitments and inconsistent capacities are rejected.
The application follows the existing forecast network requirement (at least six
beneficiaries). This is an adapter to the bounded core, not an expansion of it.

## Application and source authority

`/optimization` connects presenter login, committed forecast selection/generation,
scenario capture, durable comparison, saved results and revised scenarios. The
Next route remains a thin allowlisted transport; FastAPI owns tenant authentication,
CSRF, validation and queue admission. OpenAPI and generated TypeScript are the
public machine contract. No API accepts client-supplied stock, source commitment,
tenant identity, forecast output, verification result or arbitrary solver commands.

Scenario creation uses one PostgreSQL REPEATABLE READ view of a committed,
planning-ready forecast, tenant catalog, stock ledger/lot balances, inventory and
supply versions, calendars and immutable assumptions. A server-computed source
revision must match the displayed catalog token; conflicts return 409. Forecasts
must cover today's first planning date and current scope. Newly committed demand
corrections invalidate a stale forecast. Hub demand is an explicitly labeled zero
derivation; donation predictions never become physical stock. Unreconciled stock,
ledger mismatches and confirmed supplies without an expiry declaration are rejected.
The operational supply schema currently lacks that declaration, so the connected
adapter rejects outstanding confirmed supply; offline core arrivals remain supported.

Migration `ppor_0005` follows `pp45_0004`; all predecessor migrations remain intact.
Four tenant-owned tables save immutable assumption versions, frozen scenarios,
comparison results and per-method verification records. Database triggers reject
updates/deletes. Assumption and scenario revisions retain parent IDs. Scenario
command replay is idempotent, including concurrent submissions. Saved reads compute
stale/historical labels without changing the saved payload or invoking inference.

`or-comparison.v2` runs sequentially in the existing durable worker's Linux process
boundaries. Each result is replay-verified; a valid result survives a failed, timed
out or invalid partner. A readable partial comparison is a successful durable
publication with comparison outcome PARTIAL and `planning_ready=false`. No verified
method means failed publication. Cancellation and lost ownership cannot publish.

The workspace exposes native OPTIMAL/FEASIBLE states, objectives, bounds/gaps,
elapsed time, partial failures, per-product unmet demand, service/waste detail,
transfer explanations and frozen provenance. No progress percentages or shared
objective ranking are invented. Policy edits save a new version; applying them
requires a new scenario. Operational dispatch and inventory mutation are absent.

## Isolated demo and verification commands

The explicit seed command creates a **new** `ppor_demo_*` schema, refuses reuse,
loads fictional history relative to the database's current local date, posts
fictional receipts through audited stock commands and saves simulated assumptions.
It creates no fake forecasts/results and never resets an existing database.

```sh
export DATABASE_URL_UNPOOLED='postgresql+psycopg://…/isolated_demo_database'
uv run --frozen --directory apps/api python scripts/load_optimization_demo.py \
  --schema ppor_demo_presenter --output /absolute/path/demo-request.json
# Configure presenter access as in docs/pantrypulse/FORECAST-API-FLOW.md.
export PP_DATABASE_SCHEMA=ppor_demo_presenter
uv run --frozen --directory apps/api python -m app.workers.supervisor \
  --registry production --schema ppor_demo_presenter
```

Actual Linux CI is `.github/workflows/pantrypulse-ci.yml`. It runs the locked
backend suite with isolated PostgreSQL and fails on any skipped test, then lint,
types, contract drift, build, proxy tests and the connected browser journey.
The previous placeholder full-gate commands now resolve to executable tests.
`PP_RUN_CONNECTED=1` enables the browser journey only when the isolated API, database,
worker and presenter credentials are configured. Skipping it is not acceptance.

Dense benchmark command, Linux only:

```sh
apps/api/.venv/bin/python scripts/or/benchmark_budgets.py --output evidence.json
```

The sweep freezes each dense scenario once, runs both methods at 15/30/60/120/300
seconds with identical settings, and records native status, exact objective,
bound/gap, search/wall runtime, peak RSS, full scenario and code/settings hashes.
Results are machine/runtime-specific; longer time does not promise optimality.
Final evidence and limitations are recorded in [FINALIZATION.md](FINALIZATION.md).

Hosting, Chronos, supplier planning, visitor access, broad scenario support,
general import/data-management UI and production resets remain outside this change.
