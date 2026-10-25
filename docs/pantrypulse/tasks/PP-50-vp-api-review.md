# PP-50 — VP API integration review

User requested reviewing VP and preparing its APIs and related development for a
clean merge into main on October 25, 2026. Lead/integrator owns this review on
`codex/vp-api-integration`, based on main `9df7c51` and VP `35615a6`.

Review inventory reads/adjustments, receipt history/posting/reconciliation, supply
commands, history imports, dashboard/shortages, and planning additions. Preserve
main's connected workspace, original migration histories, authoritative stock
ledger, authentication, CSRF, generated contracts and Linux CI evidence.

The user approved converging VP planning on main: retain its contracts, storage,
verifier and budgets, and adapt the additional plan/review APIs.

Acceptance: focused failing regressions for demonstrated issues, isolated
PostgreSQL migration/transaction/tenant/idempotency checks, real Linux queue and
process checks for retained planning changes, full combined backend suite, proxy
tests, contract drift, lint/types/build and the existing browser journey. Record
source identities, retained changes, findings and remaining limitations in the
review report. Prepare a reviewable integration branch/PR; final merge requires
the appropriate authorization and passing final evidence.

Local exit gates completed: 1207 backend tests with no skips; 11 production-browser
tests; 18 configuration and six proxy tests; static/build/contract checks and
retained benchmark replay. See the integration report and source manifest.

Prepared PR: [#78](https://github.com/gbw30/PantryPulse/pull/78); final published-head CI is the merge gate.
