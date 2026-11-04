# PantryPulse gap report

**Date:** 2026-11-04 · **Tree:** branch `v1-local` at `c3ec1ed` (origin/main, through PR #94 and #100) · **Method:** read-only. Code was compared against [SPEC-V5](pantrypulse/SPEC-V5.md) (§§2, 12, 14, 16, 19) and [ACCEPTANCE-MATRIX](pantrypulse/ACCEPTANCE-MATRIX.md). No code was changed, and **no tests were run for this report**.

Status words:

- **Implemented** means the code path exists at the cited location.
- **Partial** means some of it exists and the named piece is missing.
- **Missing** means a grep found no code for it.

"Implemented" here means *present in source*. It does not mean freshly verified. The most recent execution evidence is the 2026-11-03 WSL run recorded in the vault: 1327 backend tests passed with 0 skipped, 20/20 config tests, `run.cjs full` 8/8, and 153/154 browser tests. The one browser failure was the flaky `overview-layout.spec.ts:216`. That run is not repeated here.

---

## 1. Summary

The bounded **simulated** product works end to end in source:

- seed an isolated schema
- presenter login
- baseline forecast job
- frozen scenario in either transfer mode
- paired CLASSICAL_GP vs EGP_PI_INSPIRED comparison with independent verification
- Recommendations and simulation-only review
- live Overview / Data Explorer / Scenario Lab / Methodology screens
- Linux CI that rejects skipped tests

The real gaps are:

1. **Release and operations (V5-A18):** no reset API, no five-rehearsal evidence, no release manifest, rollback or deployment.
2. **Supplier proposals (V5-A14):** accepted scope, PAUSED, zero code.
3. **Observability:** structured logs exist only in the worker. There is no request-level JSON logging and no log-redaction acceptance test for the API.
4. **Shortage contract (SPEC-8.6):** the response lacks first-deficit date, inbound supply, planning mode and risk label.
5. **Forecast evaluation and selection (V5-A06, D09):** offline only, with no `selection_reason` and no automatic selection.
6. **Chronos:** wired into the production registry behind a flag. Qualification failed its own gate (92% < 99% availability).
7. **P1 items** (reservations, completion, roles): not started, as the spec intends.
8. **Docs drift:** several "current" docs, including CLAUDE.md, contradict the code. See §6.

---

## 2. V5 consolidated acceptance matrix (SPEC-V5 §16.1)

| ID | Area | Status | Code evidence | Gap |
|---|---|---|---|---|
| V5-A01 | Foundation/primitives | Implemented | `apps/api/app/main.py:34,178` health; helpers in `app/services/*` (transfer modes, fixed point, demand rounding, solver status); tests `tests/test_fixed_point.py`, `test_transfer_modes.py`, `test_demand_targets.py`, `test_solver_outcomes.py` | none |
| V5-A02 | Historical truth (gaps/zeros/proxies/revisions/cutoff) | Partial | `services/forecasting/` (`align_history`, `validate_points`); `tests/forecasting/test_history.py`, `test_receipts.py` | Spec still lists operational import/revision policy as open (OPEN-07/13). Leakage tests exist only at forecasting-module level |
| V5-A03 | Stock transactions | Implemented | `routers/operations.py:86-175` (receipts, revisions, post, reconcile, lot declarations); `routers/inventory.py:29` adjustments with Idempotency-Key + CSRF; `tests/integration/test_stock_postgres.py`, `test_stock_adjustment_api_postgres.py` | P1 movement/reservation not implemented (by design) |
| V5-A04 | Baseline forecast | Implemented | `routers/forecasts.py:124` (202), `:227`, `:255`; worker `workers/forecasting.py:259` (`forecast.v1`); `tests/integration/test_forecast_api_postgres.py` | none |
| V5-A05 | Qualification/fallback, Chronos | Partial | Fallback chain in `services/forecasting/adapters/`; Chronos worker `workers/chronos_forecasting.py:91` registered in `workers/production.py:9`, gated by `PP_CHRONOS_ENABLED` (`services/chronos_runtime.py:26`) | Representative accuracy/calibration unqualified. Full-demo donation quantiles invalid; retail proxy 92% vs 99% gate ([QUALIFICATION](forecasting/QUALIFICATION.md)) |
| V5-A06 | Evaluation | Partial | `services/forecasting/evaluation.py:70` (experimental schema), `benchmark_evaluation.py`; scripts `apps/api/scripts/evaluate_forecasting.py`, `evaluate_retail_forecasting.py` | Offline only. No persisted evaluation, no selection policy (OPEN-18) |
| V5-A07 | Atomic publication/reuse | Implemented | `workers/publication.py`; `tests/integration/test_job_queue.py`, `test_worker_slice.py` | none |
| V5-A08 | Frozen scenarios | Implemented | `routers/optimization.py:59,65`; `schemas/or_inputs.py:511` (`or-scenario-v2`); `tests/test_scenario_contract.py` | none |
| V5-A09 | Projection/feasibility | Implemented | `services/inventory/` (`project_inventory`, FEFO `eligible_lots`); `services/optimization/constraints.py`, `verify.py`; `tests/optimization/test_or_v2.py`, `test_or_scope.py` | none |
| V5-A10 | Mathematical/research gate | Implemented (bounded) | `services/optimization/egp_pi_inspired.py`, `classical_gp.py`, `objective.py`, `numerics.py`; fixtures `data/demo/or-v2/ap-ablation-v2.*`, `rp-ablation-v2.*`; `tests/optimization/test_or_oracle.py`, `test_or_native_boundaries.py` | Policy coefficients are simulated. Spec OPEN-23/24 still say "OPEN" (doc not updated) |
| V5-A11 | Paired research comparison | Implemented | `routers/optimization.py:74,103`; `workers/optimization.py:226` (`or-comparison.v2`); `services/optimization/compare.py`, `verify.py` | Optimality not guaranteed (disclosed) |
| V5-A12 | Durable execution | Implemented (local) | `workers/supervisor.py`, `process_driver.py`, `recovery.py`; retry/cancel `routers/forecasts.py:161,201`; `tests/integration/test_supervisor.py`, `test_long_solver_runtime.py` | Hosted runtime (Fly) unqualified |
| V5-A13 | Public API and security | Partial | Presenter session/CSRF `routers/forecasts.py:65,70`; visitor read-only `services/presenter_access.py:162-181`; error envelope `main.py:39-50`; proxy `apps/web/src/app/api/v1/[...path]/route.ts`; generated contracts `packages/contracts` | No readiness/capability endpoint (§12.1 row). Full catalog (OPEN-29) and rate limits (OPEN-31) open |
| V5-A14 | Supplier proposals | **Missing** | grep for `supplier\|basket\|offer` in `apps/api/app` found nothing | PAUSED by user decision. Needs resumption or scope amendment |
| V5-A15 | User journey | Partial | E2E `apps/web/tests/e2e/forecasting-integration.spec.ts`, `scenario-lab.spec.ts`, `recommendations.spec.ts`; CI connected step `.github/workflows/pantrypulse-ci.yml:86-108` | Reset step missing (see A18). CSV import UI exists (`components/data-input/imports-section.tsx`) but spec still excludes "import UI" from PP-46 acceptance |
| V5-A16 | Research attribution | Implemented | `routers/planning.py:37` (`/allocation-methodology`); `apps/web/src/app/methodology/page.tsx`; `tests/e2e/methodology.spec.ts` | Run `research-claims-check` before any new copy |
| V5-A17 | Visual/accessibility | Partial | `tests/e2e/a11y.ts` (axe), `overview-layout.spec.ts`, `theme.spec.ts` | Human taste approval not recorded. One flaky layout test |
| V5-A18 | Release and operations | **Missing** | Demo loaders refuse to reset: `apps/api/scripts/load_optimization_demo.py:1`, `load_forecast_demo.py:30`. No reset route in `apps/api/app/routers/` | No reset API/transaction (OPEN-32), no five rehearsals, no release manifest/rollback/backup, no deployed smoke |

## 3. Historical acceptance matrix (ACCEPTANCE-MATRIX.md)

This matrix is marked historical. V5 §16.1 above governs. Rows are mapped to current code for traceability.

| Row | Status | Evidence / gap |
|---|---|---|
| FR-01 sites | Implemented (scope changed) | Row says "three named sites" (`ACCEPTANCE-MATRIX.md:11`); V5 requires ≥6 beneficiaries + hub. Fixture `data/demo/forecasting-v1.json`, `or-v2/six-beneficiary-v2.*`; up to 8 products (`schemas/optimization_api.py:34`) |
| FR-02 stock nonnegative | Implemented | SQL guards `migrations/versions/pp19_0001_guards.sql`; `tests/test_operational_schema.py`, `integration/test_operational_postgres.py` |
| FR-03 import | Implemented | `routers/operations.py:282,296,310` (JSON + CSV demand, donation coverage); UI `components/data-input/imports-section.tsx` |
| FR-04 forecast | Implemented | see V5-A04 |
| FR-05 fallback | Implemented | see V5-A05 |
| FR-06 projection | Implemented | `services/inventory/`; `tests/test_inventory_projection.py` |
| FR-07 shortage | Partial | `routers/dashboard.py:97`; see SPEC-8.6 below |
| FR-08 uncertainty | Implemented | `apps/web/src/components/data-explorer/forecast-chart.tsx` (quantiles only when the provider supplies them) |
| FR-09 scenario | Implemented | see V5-A08 |
| FR-10 optimization checker | Implemented | `services/optimization/verify.py`; `tests/optimization/test_or_oracle.py` |
| FR-11 explanation | Partial | `components/recommendations/action-plan.tsx`. Per-transfer benefit deliberately absent (OPEN-02 deferred) |
| FR-12 comparison | Implemented | see V5-A11 |
| FR-13 failure | Implemented | `services/solver_outcomes` (`classify_solver_status`); `tests/test_solver_outcomes.py`, `optimization/test_or_native_boundaries.py` |
| FR-14 reset | **Missing** | no reset route; seed-new-schema only |
| FR-15 replay | Implemented | `tests/optimization/test_or_v2.py` (objective replay per V5-A10 note) |
| FR-16 P1 approval | Missing (P1) | review is simulation-only: `routers/planning.py:205`, `components/recommendations/review-dialog.tsx:14` |
| FR-17 P1 completion | Missing (P1) | none |
| FR-18 P1 evaluation | Partial | offline `services/forecasting/evaluation.py` |
| FR-19 P1 roles | Missing (P1) | presenter + visitor only (`services/presenter_access.py`) |
| FR-20 P2 integrations | Missing (deferred) | none |
| SPEC-11.6 baselines (D08: no-redistribution/equal-share/greedy) | **Missing** | grep for `equal.?share\|greedy\|no.?redistribution` in `apps/api/app` found nothing. V5 §20 demotes these to supplemental (OPEN-34) |
| SPEC-9.7 model selection (D09) | **Missing** | grep for `selection_reason` in `apps/api/app` found nothing |
| SPEC-13.5 observability/audit | Partial | Audit tables `models/operational.py:351`, `models/or_records.py:322`, `models/jobs.py:96`; JSON logs only in `workers/supervisor.py:55-61`; request IDs in `main.py:63-95`. No API request/plan/409 structured logging; no captured-log secret test for the API (`tests/test_report_redaction.py` covers report redaction only) |
| SPEC-8.1 status codes | Implemented | `main.py:123-169` (400/422/413/503/500 envelope); 409 via stale inventory versions |
| SPEC-8.6 shortage response | Partial | `schemas/dashboard_api.py:43-65` has per-day demand/served/unmet/eligible_end, provider and fallback. **Missing:** first deficit date, inbound supply, central/conservative planning mode, risk label |
| SPEC-7 schema columns | Partial | site latitude/longitude present (`models/operational.py`, `pp19_0001_tables.sql`). grep found nothing for `objective_value`, `evaluation_json`, `data_source_label`, `selection_reason`, `error_message`. These are older-contract names; V5 may have superseded them, so verify before building |

## 4. Other SPEC-V5 areas

| Spec area | Status | Evidence / gap |
|---|---|---|
| §2.1 Population (≥6 beneficiaries, hub, 2+ products) | Implemented | fixtures above; `tests/test_multi_product.py` |
| §8 Both transfer modes, no default | Implemented | `tests/test_transfer_modes.py`; scenario schema `schemas/or_inputs.py` |
| §12.1 Shortages/policy/methodology/audit | Partial | Spec says "Not implemented" (`SPEC-V5.md:595`), but `GET /shortages/{id}` (`dashboard.py:97`) and `/allocation-methodology` (`planning.py:37`) exist. There is no audit-read route |
| §12.1 Readiness/capabilities | Missing | health is liveness only (`main.py:35`) |
| §12.3 Visitor reads | Partial | `PP_VISITOR_ORGANIZATION_ID` read-only Overview/catalog only (`presenter_access.py:168`) |
| §14.1 Overview | Implemented | `apps/web/src/app/overview/page.tsx`; root redirects there (`app/page.tsx`) |
| §14.1 Site detail | Implemented | `components/overview/site-inspector.tsx` |
| §14.1 Forecast explorer | Implemented | `app/data/pulse/page.tsx`, `components/data-explorer/forecast-chart.tsx` |
| §14.1 Method comparison | Implemented | `app/recommendations/page.tsx` |
| §14.1 Scenario simulator | Implemented | `app/scenarios/page.tsx`; `/optimization` redirects (`app/optimization/route.ts:7`) |
| §14.1 Methodology/audit | Partial | methodology page exists; no snapshot/event audit view |
| §14 Frontend unit tests (Vitest for dirty/stale state) | Missing | only `apps/web/tests/forecast-proxy.test.mjs` (node:test); no Vitest in `apps/web/package.json` |
| §11 Supplier replenishment | Missing (PAUSED) | see V5-A14 |
| §13.3 Probes/logs | Partial | see SPEC-13.5 |
| §15 Deployment (Fly/Vercel/tunnel) | Config only | `apps/api/fly.toml`, `Dockerfile.compute`; no deployment |

## 5. Open P0 items on BOARD.md

[BOARD.md](pantrypulse/BOARD.md) says its PP-01–PP-23 rows "retain their recorded historical status and do not override subsequent integrated evidence". All 23 are still marked **TODO**, though code now covers most of them. The table gives the real state of each row.

| Board row | Board status | Actual state in code |
|---|---|---|
| PP-01 Confirm repo/rules/deadline/P0 | TODO | Hackathon (Oct 23–25) is past; scope for "v1 runs locally" is the open vault action |
| PP-02 Contracts | TODO | Done: `packages/contracts`, `contracts:check` gate |
| PP-03 Schema/migration | TODO | Done: head `ppvp_0007` (`migrations/versions/ppvp_0007_plans.py:7-8`) |
| PP-04 Demo seed/**reset** | TODO | Seed done; **reset missing** |
| PP-05 Tokens/dashboard composition | TODO | Done in source; human direction sign-off not recorded |
| PP-06 CI and preview | TODO | CI done; connected preview not deployed |
| PP-07 – PP-14 | TODO | Done (see §2) |
| PP-15 – PP-18 UI screens | TODO | Done (see §4) |
| PP-19 Judge journey E2E | TODO | Done (CI connected step) |
| PP-20 Visual/a11y repair | TODO | Automated part done; **critic + human review open** |
| PP-21 Adversarial audit | TODO | **Not found** as a recorded audit for the current tree (PR-75/PR-77 reviews and `docs/optimization/FINALIZATION.md` cover earlier trees) |
| PP-22 Release/rollback + five rehearsals | TODO | **Open** |
| PP-23 Submission assets | TODO | **Open / possibly moot** (event passed) |
| PP-24 – PP-29 BE-01..06 | MERGED; independent review pending | **Independent verifier pass still not recorded** |
| PP-45 forecast API | live-worker smoke, review, OR convergence open | Converged on main (PR #78/#93); independent release review not recorded |
| VP inventory / PP-47 / PP-49 | UI binding, independent release review open | UI binding done (`app/data/inventory`, `data/operations`); **independent release review open** |

**Open P0 work in practice:**

1. Demo reset (PP-04/FR-14/OPEN-32).
2. Adversarial audit on the current tree (PP-21).
3. UX-critic and human visual sign-off (PP-20).
4. Release manifest, rollback and five rehearsals (PP-22).
5. Independent verifier pass for PP-24–29 and the VP API rows.
6. Fix the flaky `overview-layout.spec.ts:216`.

Supplier proposals are P0 scope in V5 §2.1 but are PAUSED.

## 6. Docs that contradict the code

Fix these before relying on them:

| Doc | Claim | Code |
|---|---|---|
| `CLAUDE.md:23` | "migration head ppor_0005"; "Chronos remains a standalone exercise" | Head is `ppvp_0007`; Chronos worker is in `workers/production.py:9` |
| `CURRENT-STATUS.md:3,8` | `feat/forecasting-next` / Chronos jobs are a "candidate" | Merged in PR #93 (`0ab8929`) |
| `SPEC-V5.md:595` | Shortages/methodology "Not implemented" | `dashboard.py:97`, `planning.py:37` |
| `SPEC-V5.md` §16.3 | full gate "references missing `test:unit`, `contracts:check`" | Both exist (`apps/web/package.json`); gate is green |
| `EXTERNAL-SERVICES.md:32` | "real Chronos is a separate offline model exercise" | Registered, flag-gated handler |
| `docs/setup/LOCAL-DEMO.md:18` | "Open `/optimization`" | Redirects to `/scenarios` |
| `INSTALLATION.md:156,166` | "tests cover the scaffold"; "no Alembic domain revisions yet" | 68 API test files; 11 revisions |
| `ACCEPTANCE-MATRIX.md:11` | three named sites | ≥6 beneficiaries + hub |

## 7. How to run the app today

There is **no single start command**. The working recipe is the CI connected job (`.github/workflows/pantrypulse-ci.yml:86-108`). On WSL, the vault note "PantryPulse Local WSL Test Runs Need Alternate Ports" applies.

The worker needs Linux, because the process driver uses Linux containment. On the original Windows host, OR-Tools is blocked natively, so run the API in Docker there.

```sh
# 0. Dependencies (once)
npm ci
uv sync --frozen --project apps/api
npx playwright install chromium          # only for E2E

# 1. PostgreSQL 16 (compose.yaml → 127.0.0.1:55432, user pantrypulse / local_dev_only)
docker compose up -d postgres

# 2. Seed a NEW isolated schema (refuses reuse; never resets)
export DATABASE_URL_UNPOOLED='postgresql+psycopg://pantrypulse:local_dev_only@127.0.0.1:55432/pantrypulse_dev'
uv run --frozen --directory apps/api python scripts/load_optimization_demo.py \
  --schema ppor_demo_local --output /tmp/demo.json

# 3. Presenter credentials: scripts/quality/demo-ci-env.py prints KEY=VALUE lines
#    (username, password, org id, scrypt hash, proxy token). Do NOT `eval` them:
#    the $ in the hash expands and every login returns 401. Write them to an env file
#    and load it literally.

# 4. API (needs DATABASE_URL, PP_DATABASE_SCHEMA, PP_ALLOWED_ORIGINS=http://127.0.0.1:3000,
#    PP_COOKIE_SECURE=false, PP_PRESENTER_*, PP_TRUSTED_PROXY_TOKEN)
(cd apps/api && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000)

# 5. Worker (Linux only)
(cd apps/api && .venv/bin/python -m app.workers.supervisor --registry production --schema ppor_demo_local)

# 6. Web: apps/web/.env.local with PANTRYPULSE_API_ORIGIN=http://127.0.0.1:8000 and the same PP_TRUSTED_PROXY_TOKEN
npm run dev:web     # http://127.0.0.1:3000 → /overview; log in as presenter
```

Gates: `node scripts/quality/run.cjs quick|full|e2e`. Set `PP_RUN_CONNECTED=1` for the connected browser journey, and `PP_TEST_DATABASE_URL` for the PostgreSQL integration tests.

Under WSL, ports 5432 and 8000 are held by Windows-side containers. Use 55433 for the test database and 8001 for the API, and set `PANTRYPULSE_API_ORIGIN` to match.

## 8. External dependencies

| Dependency | Required? | Where | Notes |
|---|---|---|---|
| Docker + PostgreSQL 16 | **Yes** | `compose.yaml` | Local, free |
| Linux (WSL ok) for the worker | **Yes** for compute | `workers/process_driver.py` | |
| Node 24.16 / npm 11.13 / uv 0.11.15 / Python 3.12.13 | **Yes** | SPEC-V5 §15.1 | |
| Playwright Chromium | E2E only | `apps/web` | `install-deps` needs sudo on WSL |
| **Neon** (hosted Postgres) | Optional | `compose.forecast.yaml`, `apps/api/demo.env.example:6` (`DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `sslmode=require`) | Previously used project `autumn-rain-99060639` (SPEC-V5 §4). Not needed for a local run |
| **Vercel** | Optional, historical | `docs/setup/VERCEL.md` | Only a static `/design-lab` preview from a branch; no connected deployment |
| Cloudflare tunnel | Optional | `docs/setup/CLOUDFLARE.md` | Remote API reachability only |
| Fly.io | Optional, not deployed | `apps/api/fly.toml`, `Dockerfile.compute` | Would be paid compute; needs authorization |
| Hugging Face (Chronos-2 weights) | Optional | `compose.compute.yaml:47` `HF_HOME`; `adapters/chronos2.py:77` | Public model download into a cache; no token in any example file; app runs cache-only and only with `PP_CHRONOS_ENABLED=1` |
| GitHub Actions | CI | `.github/workflows/pantrypulse-ci.yml` | |
| **Paid APIs / LLM keys** | **None** | grep for `api_key\|openai\|gemini\|anthropic` in `apps/` found nothing | The Gemini/Agent Framework idea is an unaccepted proposal (SPEC-V5 §2.2) |

**Secrets** (all private and ignored by Git): `PP_PRESENTER_PASSWORD_HASH`, `PP_TRUSTED_PROXY_TOKEN`, database URLs, and any Fly/Neon credentials. Examples are `apps/api/.env.example`, `compute.env.example`, `demo.env.example` and `apps/web/.env.example`.

## 9. Not checked

- No test, gate, build or app run was executed for this report.
- Per-row implementation claims are based on file and route presence plus test file names. Test bodies were not read, so the depth of coverage for each acceptance row is unverified.
- The Chronos and OR evidence numbers come from the spec and QUALIFICATION/FINALIZATION docs, not from a rerun.
