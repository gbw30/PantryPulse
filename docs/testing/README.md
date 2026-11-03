# PantryPulse testing kit

**Checkout scope:** `design/overview-intake` at `a4573b5` plus this uncommitted kit.
Newer `origin/main` (`5add760`) contains connected workflows absent here. Missing
features below refer to this checkout; consult the [branch diagnostics](BRANCH-DIAGNOSTICS-2026-10-25.md)
before concluding they need to be implemented from scratch.

The kit tests the implemented app and records the remaining product acceptance gaps.
The browser currently displays static design fixtures; FastAPI exposes process health only.
Passing prototype tests does not establish the complete import → forecast → allocation →
review/reset journey required by [SPEC-V5 §16](../pantrypulse/SPEC-V5.md).

## Install and run

Use the repository's Node/npm versions (Node 24.16+, npm 11.13+) and Python 3.12.
From the repository root:

```powershell
npm ci
uv sync --frozen --directory apps/api
npm run test:e2e:install
npm test
```

`npm test` runs configuration tests, frontend unit/component tests, the native API suite,
browser tests and the story inventory. Native Windows reports PostgreSQL/Linux checks
as **skipped / NOT RUN** if their prerequisites are unavailable.

For the complete implemented backend, including real PostgreSQL and Linux processes,
start Docker Desktop with Linux containers and run:

```powershell
npm run test:all
```

This uses a separate `pantrypulse-tests` Compose project. Its PostgreSQL database is
named `pantrypulse_test`, has ephemeral storage and no published ports. Only public
source/fixtures and the test report directory are mounted; existing app/worker stacks,
demo credentials and databases are not used. The runner removes its own test containers
and network after success or failure. It builds the existing API image without the
optional forecast/model extra. No model weights are downloaded.

If the runner is forcibly killed, clean up only its disposable stack:

```powershell
docker compose -f compose.test.yaml down
```

## Focused commands

| Command | Purpose |
|---|---|
| `npm run test:unit:web` | Vitest and React Testing Library; no server required |
| `npm run test:unit:watch --workspace @pantrypulse/web` | Interactive unit-test watch mode |
| `npm run test:coverage` | V8 coverage with HTML and LCOV artifacts |
| `npm run test:api` | Existing Python helpers/forecasting/jobs/worker/API suite; report skips |
| `npm run test:docker` | Entire API suite on isolated PostgreSQL/Linux; skips fail |
| `npm run test:integration` | PostgreSQL tests against explicitly supplied `PP_TEST_DATABASE_URL`; skips fail |
| `npm run test:api:strict` | Entire native API suite; any skipped check fails |
| `npm run test:e2e` | All Chromium stories, smoke, layout and accessibility tests |
| `npm run test:e2e:stories` | Browser tests tagged `@story` |
| `npm run test:e2e -- user-stories.spec.ts` | One browser spec |
| `npm run test:e2e:report` | Open the latest Playwright HTML report |
| `npm run test:config` | Hook/gate tests and story-inventory integrity tests |
| `npm run diagnose` | Check local documentation links, heading targets, gate command paths and merge-conflict blocks; findings return exit 1 |
| `npm run test:stories` | Validate and report story evidence/gaps, without claiming execution |
| `npm run test:stories:strict` | Fail until every documented story is fully implemented and covered |

Also run `npm run typecheck`, `npm run lint`,
`uv run --frozen --directory apps/api ruff check .` and `npm run build`.
The older `.claude` full gate still references unfinished generated-domain-contract
checks and an obsolete migration-test path. This kit does not replace those requirements
with no-ops; the new CI workflow runs the real existing tests directly.

## What is tested

| Layer | Behavioral evidence |
|---|---|
| Frontend unit/component | Selected-day status transitions, past versus next deficit, unknown versus zero data, singular/plural units, local dates/DST/month boundaries, accessible marker names, map fallback placement, fixture conservation, seven-day example arithmetic, hub supply-only semantics, chart text/table alternatives, inspector empty/zero/hub states, retry, abort-on-unmount and stale success/error suppression |
| Python unit/offline | Existing strict planning primitives, both topology modes, demand rounding, fixed-point overflow, native solver statuses, history/revisions/receipts, provider failure/fallback, forecast validation, frozen handoff, evaluation and queue policies |
| Independent projection oracle | Twenty deterministic small inputs enumerate all legal lot-consumption choices independently of production FEFO. Check maximum dated service, arrivals/expiry/held/unknown eligibility, stock conservation, nonnegativity and unchanged inputs. This validates offline projection, not an allocation solver |
| PostgreSQL/Linux integration | Real migration upgrade/downgrade/integrity, transaction/concurrency/idempotency, queue ownership/admission/recovery, supervisor deadlines, cancellation, descendant cleanup and worker-loss/retry behavior |
| Browser | Root routing; six beneficiaries plus hub; full deficit → inspector → table → product-change journey on desktop/mobile; date progression; missing history; search/no-match recovery; unavailable adapter/retry; disabled unfinished workflows; illustrative proposal/residual/explanations; repeatable fixture reload; mobile navigation/search; bounded zoom/pan/fit; explicit/reduced motion; light/dark themes; optional 3D and WebGL fallback |
| Accessibility/layout | Existing axe scans, keyboard/focus return, readable chart tables, no horizontal overflow, marker/popover/inspector fit at 1440×900, 1280×720 and 390×844 |
| API process smoke | Playwright starts a real FastAPI process and checks health/OpenAPI plus the current 404 for unimplemented allocation. The browser's static data is not connected to this API |

The async Next.js page is exercised in Chromium. jsdom shims cover missing browser APIs
only in unit tests; they are not layout or accessibility evidence. Global coverage is
diagnostic and does not substitute for story/invariant checks. Real-model qualification,
full product scenarios and human visual/accessibility review remain separate gates.

## User-story traceability

[user-stories.json](user-stories.json) maps every inherited story (US-01–12 and US-15–18)
to its source documentation, current V5 acceptance IDs, test files and unmet criteria.
The source documentation has no US-13 or US-14. V5's six beneficiaries plus hub supersede
the historical three-location criterion. V5's simulation-only review semantics supersede
historical wording suggesting dispatch/approval.

Story-tagged browser tests assert the behavior available today. A disabled navigation
control or API 404 is evidence of an unavailable feature, never completion of its story.
The strict story gate intentionally fails while any story is `partial` or `blocked`.

When implementing a missing workflow:

1. Resolve its V5 contract and write the API/database tests for state changes and failures.
2. Add a browser journey through the real UI/API/database; use isolated synthetic data.
3. Assert resulting persisted state, invariants, provenance and error/retry behavior.
4. Add the evidence files to the story inventory. Mark complete only after all acceptance
   criteria pass; remove the gap text only when it is resolved.

## Isolation and reports

Playwright owns local Next.js and FastAPI test processes on ports **3100** and **8011**.
`PLAYWRIGHT_PORT` and `PLAYWRIGHT_API_PORT` override them. `.next-e2e` keeps its build
output separate from a developer server. Server reuse is disabled unless explicitly
enabled with `PLAYWRIGHT_REUSE_SERVER=1`; use that only for this exact checkout.
Browser locale/timezone are fixed to `en-US` / `America/New_York`.

The PostgreSQL tests require a dedicated database whose name ends in `_test` and only
reset their own test schemas. Never supply a development, demo or production URL.
Tests run serially inside a single API process; do not share a test database across
concurrent suite runs.

Generated evidence is ignored by Git:

- `apps/web/playwright-report/index.html`: browser report.
- `apps/web/test-results/`: JUnit, screenshots, retained failure traces and video.
- `artifacts/testing/web-coverage/index.html` and `lcov.info`: frontend unit coverage.
- `artifacts/testing/api-linux.xml`: full Docker API results.
- `artifacts/testing/story-coverage.json`: evidence inventory with timestamp, commit and
  SHA-256 hashes of referenced documentation/tests, including uncommitted files.

[The CI workflow](../../.github/workflows/tests.yml) installs locked dependencies,
runs lint/types/build/unit/browser checks and the entire API suite against its PostgreSQL
service on Linux with `--require-no-skips`. It uploads results on success or failure.
It inventories unfinished stories without claiming product completion. CI execution
itself is unverified until the workflow runs on GitHub.
