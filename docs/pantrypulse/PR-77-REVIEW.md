# PR #77 review and main documentation reconciliation

Reviewed October 25, 2026. The original compute candidate `9c7775a` was integrated
with main `1e713c9` (connected OR PR #76) at `6fe77ac`. This review concerns local/Fly
configuration and current documentation; it does not deploy services or qualify
Chronos as an application forecast provider.

## Findings corrected

1. **P1 — local shutdown could interrupt an accepted comparison.** The compute
   overlay allowed only 330 seconds after SIGTERM while current main permits a
   690-second comparison and 720-second supervisor drain. Local stop grace is now
   725 seconds. The new configuration regression failed at `330 >= 690 + 35`
   before the correction and passed afterwards; it derives the required window
   from the production runtime profile so later budget drift is detected.
2. **P2 — migration recipe could target the wrong schema.** A bare Alembic command
   does not select the application's `PP_DATABASE_SCHEMA`. The connected local
   recipe now invokes the explicit new-schema loader with a direct local URL and
   the complete repository fixture mount. It was executed successfully against
   `ppor_demo_pr77_review` in the disposable review database. No live public/demo
   schema was migrated or reset.
3. **P2 — current-state documentation contradicted merged source.** Current
   entrypoints, setup/provider guides, migration/forecast guidance and agent
   instructions now reflect `forecast.v1`/`or-comparison.v2`, `ppor_0005`, the
   connected workspace/proxy, active CI and separate standalone model evidence.
   Dated scaffold/VP/forecast/optimization evidence retains its original scope.
   [CURRENT-STATUS.md](CURRENT-STATUS.md) indexes the supported source/runtime split.

## Local verification

| Check | Result |
|---|---|
| New stop-grace regression | Failed before the fix; passed after it |
| Full Linux backend/PostgreSQL/OR/process-control suite, six-CPU/two-GiB test container | **1,141 passed, zero skipped**; one existing Starlette/httpx deprecation warning |
| Initial two-CPU full run | 1,140 passed; one watchdog fixture failed waiting for a descendant to appear before the short test deadline |
| Unchanged watchdog test in isolation, same two-CPU cap | Passed; no production/test deadline was weakened |
| Configuration suite | **18 passed**, including the 11 compute helper guard cases |
| Corrected connected loader | Passed in a NEW isolated review schema; no computed results fabricated |

The initial timing failure is retained as a runtime-sensitive test limitation,
not relabeled a pass. The final full run/JUnit evidence is in ignored
`artifacts/pr77-review/backend-final.xml`; the initial run and private demo inputs
remain in the same ignored folder. Test containers use their own private network
and disposable PostgreSQL database, never the running development database.

Current source CI is `.github/workflows/pantrypulse-ci.yml`. Inspect the exact
review/merge commit's run; prior Vercel statuses were ignored builds and do not
substitute for application checks. No main merge changes the old branch-scoped
Vercel preview or running laptop images automatically.

## Remaining deployment limits

Fly login, platform validation, target selection and deployment remain pending.
Its configured 300-second platform stop window cannot finish a possible
690-second comparison: drain/confirm an idle lane before deployment. Local worker
CPU/RAM remain six/eight GiB; Fly uses four/eight, with separate API resources.
Cross-host takeover is unqualified. Preserve manual retry, containment recovery
and immutable publication. No existing task was stopped to perform this review.
