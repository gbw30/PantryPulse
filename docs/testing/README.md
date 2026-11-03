# Testing the current application

Updated October 25, 2026 for main `647f6a8`. Tests cover connected forecasts/planning, operational transactions, all product views and the independent OR model/verifier. This page replaces earlier scaffold-only and uncommitted-testing-kit assumptions.

## Current commands

| Command from repository root | Meaning |
| --- | --- |
| `npm run test:config` | Hook, quality-runner and compute-helper behavior |
| `npm run typecheck`, `npm run lint` | Current web static checks |
| `npm run test:unit --workspace @pantrypulse/web` | Proxy/unit behavior using Node's test runner; not Vitest |
| `npm run contracts:check --workspace @pantrypulse/web` | Offline application/OpenAPI/TypeScript drift |
| `npm run build` | Production Next build |
| `uv run --frozen --directory apps/api ruff check .` | Backend lint |
| `npm run test:api` | Entire pytest suite; Linux/DB prerequisites matter |
| `npm run test:e2e` | Chromium; connected cases require explicit opt-in and services |
| `node scripts/quality/run.cjs quick` | Types/lint/backend suite; 600-second group budget, 360-second backend timeout |
| `node scripts/quality/run.cjs full` | Quick plus frontend units/build/contracts and real migration tests |
| `node scripts/quality/run.cjs e2e` | Browser gate, including its configured environment requirements |

The root has no canonical `npm test`, `test:all`, `test:docker`, `test:stories` or Vitest coverage script. Those belong to an earlier uncommitted kit in another checkout. Do not copy its commands into main's instructions.

## CI jobs are different gates

`.github/workflows/pantrypulse-ci.yml` runs two jobs in parallel on PRs and main pushes:

- **verify:** two-minute static/unit merge check: locked npm installation, config tests, web types/lint/units and pinned Ruff. It does not run backend pytest, contract drift, production build or browser journeys.
- **full:** 25-minute ceiling: isolated PostgreSQL/Linux/backend suite, no-skips evidence check, solver-budget evidence, contract drift, production build, cached Chromium and real browser/proxy/API/database/worker journeys. A second no-skips check covers browser evidence.

PR #99 makes concurrency cancellation apply to superseded pull-request runs; main runs are allowed to finish.

The workflow records full as no longer gating merges. Repository branch protection is external state, not established by this Markdown. A successful verify, a merge or a Vercel status is not evidence that full passed. Inspect both jobs for the exact candidate SHA; a timeout/skip/failure remains unresolved for release.

## Linux and dedicated PostgreSQL

Use the workflow as the executable reference. Supply `PP_TEST_DATABASE_URL` and `PP19_TEST_DATABASE_URL` for a dedicated direct `*_test` database, and explicitly opt into `PP19_TEST_SCHEMA_ISOLATION=1`. Never use presenter/demo/production URLs. Integration fixtures create/reset only their own test schemas. Keep concurrent suites isolated.

Native Windows cannot run Linux's `resource` API, `/proc` process containment and real worker-loss tests. A skipped or unsupported test is NOT RUN, not a pass. `npm run check` includes pytest and therefore is not guaranteed to complete as a native Windows full gate. A simple CP-SAT/database runtime probe is not equivalent to the domain suite.

## Connected browser journey

Set `PP_RUN_CONNECTED=1` only after explicitly migrating/seeding an isolated synthetic schema and starting its actual API and production Linux supervisor. Configure presenter credentials, server-only proxy token/origin, database schema, allowed browser origin and local cookie policy consistently. In CI, `PP_E2E_PRODUCTION=1` uses a completed production build. The source workflow shows exact ordering and private environment propagation.

Current journeys use Scenario Lab; `/optimization` redirects. They cover persisted forecasts, both methods, revised scenarios, stale responses, cancellation/retry, actual partial-result behavior, live Overview and operational APIs. Mocked response/a11y/layout tests verify their bounded UI behavior, not PostgreSQL state changes or model accuracy. The 390px Scenario Lab journey is retained at a 90-second test timeout by PR #97.

`PLAYWRIGHT_PORT` chooses the web port. Outside CI the configuration may reuse an existing server: ensure it is the intended checkout/backend. Two Next dev servers cannot share one checkout's `.next/dev/lock` merely by choosing different ports. Do not run connected tests against a presenter's recording session.

## Chronos and evidence

Default CI dependencies exclude the optional heavy forecast extra. Ordinary unit/API tests exercise contracts and failure boundaries; they are not new real-model runs. Explicit real-model smoke and guarded dataset/holdout qualification procedures are in [Chronos jobs](../forecasting/CHRONOS-JOBS.md) and [qualification](../forecasting/QUALIFICATION.md). Do not reopen the inspected final holdout to tune settings or claim that fallback outputs are Chronos predictions.

Historical counts in task packets, XML and JSON remain bound to their original source/environment. Documentation changes do not rerun those gates. Record SHA, dataset/configuration identity, command, timestamp, result and artifact for a new release. Full/E2E/visual checks, five rehearsals and actual target smoke are all separate from the two-minute merge check.

## Windows-specific checks

Generated TypeScript was previously identical after CRLF normalization despite a local byte-based drift failure. Diagnose the actual diff; never rewrite generated contracts by hand or silently ignore substantive drift. Docker tests can also target stale copied images: inspect mounts/image/commit before trusting them. Prefer isolated current-source Linux verification over rebuilding/stopping another active stack.
