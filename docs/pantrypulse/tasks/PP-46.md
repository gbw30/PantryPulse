# PP-46 — Inventory snapshot HTTP API

Owner: lead, authorized by the user's request to start the next independent API.
Base: `db94a95b55d3ad472520137a741753b8f41482af`, workspace `D:/Hackathon`, branch VP.

Expose `GET /api/v1/inventory/sites/{site_id}/products/{product_id}` with the
existing presenter session. Return a coherent current PostgreSQL snapshot of
physical stock, usable stock and disjoint exclusion quantities, positive-balance
lots, explicit base unit, site-local evaluation date and saved inventory version.
No version row means `null`, never a fabricated version or a write during GET.
Expired stock is excluded only after its site-local expiry date. Explicit
non-expiring stock remains usable; held/ineligible/unknown stock is excluded.
Usable physical stock is not a donor budget, reserve calculation or reservation.

Bound one response to 500 positive lots; reject oversized snapshots explicitly
instead of publishing incomplete totals. Tenant scope comes from authentication.
Missing/cross-tenant IDs return 404. Use repeatable read and a statement timeout.
No inference, worker dependency, schema changes or production data writes.

Write boundary: new inventory schema/repository/router/tests/docs, router
registration/error mapping, Next proxy allowlist and generated contracts.
Dependencies: operational schema, presenter access and existing Next proxy.
Acceptance: failing tests first; expiry/timezone/exclusion/precision unit tests;
authenticated HTTP + actual PostgreSQL checks in a disposable schema; proxy test;
offline OpenAPI/TypeScript drift checks; Ruff and web type/lint checks.
Independent review remains a release gate; self-tests are bounded implementation
evidence. Do not push or deploy as part of this task. Two failed distinct fixes
trigger diagnosis rather than repeated patching.

## Evidence — 2026-10-25

Implemented locally, uncommitted and unpushed. See [API flow](../INVENTORY-API-FLOW.md).
Failing-first test collection confirmed the missing repository before implementation.
Focused unit tests: 7 passed. Full non-integration backend regression: 824 passed,
11 Linux process tests skipped, 147 integration tests deselected. New actual
PostgreSQL/HTTP tests: 5 passed in a generated disposable schema in the selected
Neon database, including a committed concurrent version/balance update. The first
DB run found an invalid other-tenant fixture missing a required current calendar;
the fixture was corrected before the successful full rerun. Existing persistent
demo data was not modified.

Next proxy: 2 tests passed. Backend Ruff, full web ESLint, web TypeScript,
OpenAPI drift and generated TypeScript drift passed. No browser UI, live Uvicorn
smoke, independent review, Linux worker or deployment claim for this change.
