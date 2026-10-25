# PR #75 — VP integration review

Candidate: VP `8a4d0696e6587ef3a4da0fd3a32aa5f54f72da0c` integrated with
main `829262ab7485a5461ac693ec07cb9370fb76798f` at local merge `2803e76`.
Review date: October 25, 2026. The final PR head includes the corrections below.
No production database or existing Neon schema was modified for this review.

## Findings corrected before integration

1. **P1 — valid proxy login rejected.** Next.js's `NextRequest` normalizes
   `127.0.0.1` to `localhost`; comparing browser Origin directly with its URL
   rejected normal loopback login with 403. A real production Next/FastAPI HTTP
   reproduction failed while direct backend login succeeded. The proxy now uses
   the request Host authority with the request protocol, ignores client
   `X-Forwarded-Host`, and still rejects different origins. A regression uses
   the installed NextRequest implementation, not only a generic Request mock.
   Deployment must preserve the external Host/protocol at the trusted ingress;
   backend origin allowlisting remains an additional check.
2. **P2 — error contract drift.** Backend/proxy errors nested request_id and omitted
   details, contrary to SPEC-V5 §12.2. Both now emit
   `{error:{code,message,details:{}},request_id}` with a matching X-Request-ID.
   OpenAPI and generated TypeScript were regenerated; 400 and 500 error responses
   are declared alongside the other statuses.
3. **P2 — malformed JSON status.** Malformed JSON returned 422. It now returns 400;
   valid JSON with invalid schema/business values retains 422. Real PostgreSQL/API
   and real proxy HTTP regressions verify the distinction and redacted envelope.

Review also covered tenant-scoped references, immutable history/results, receipt
correction versus physical stock, idempotency/version locking, FEFO and inclusive
expiry, daily lost sales, explicit scenario modes/fingerprints, history cutoffs and
missingness, provider/fallback provenance, atomic fenced publication, saved-result
reuse, presenter/CSRF boundaries and migration ancestry. No additional blocking
issue was identified within this implemented baseline scope.

## Executed evidence

Environment: Windows, Python 3.12, locked dependencies, Node 24.16, PostgreSQL 16.
PostgreSQL ran as a separate loopback cluster on port 15438, database
`pantrypulse_vp_review_test`; tests used disposable schemas.

| Command/check | Result and scope |
|---|---|
| `apps/api/.venv/Scripts/python.exe -m pytest tests -q --tb=short` from apps/api, with PP_TEST_DATABASE_URL and PP19_TEST_DATABASE_URL pointing only at the review DB and PP19_TEST_SCHEMA_ISOLATION=1 | **950 passed, 20 skipped**; 133 database integration tests passed, including migrations, integrity, concurrency, stock rollback, publication, dedup, retry/cancel and tenant isolation |
| `apps/api/.venv/Scripts/python.exe -m ruff check apps/api` | PASS |
| `node --test apps/web/tests/forecast-proxy.test.mjs` | **2 passed**, including NextRequest loopback normalization and forged forwarded-host rejection |
| `npm run typecheck`, `npm run lint`, `npm run build` | PASS; final clean production build includes proxy corrections |
| `npm run test:config` | **17 passed** with normal Git fixture permissions |
| `PLAYWRIGHT_PORT=18809 CI=1 npm run test:e2e` | **6 passed**; existing scaffold/design-lab behavior, not a completed product journey |
| `apps/api/.venv/Scripts/python.exe apps/api/scripts/export_openapi.py --check packages/contracts/openapi.json` | PASS, generated schema matches application |
| `node node_modules/openapi-typescript/bin/cli.js packages/contracts/openapi.json -o packages/contracts/src/schema.d.ts --check` | PASS |
| Real production Next proxy → FastAPI → PostgreSQL smoke | Login 200 with both cookies; catalog 200 with 7 sites/2 products; foreign origin 403; malformed JSON 400; worker-absent forecast submission 503 COMPUTE_UNAVAILABLE; logout 200; subsequent catalog 401 |

The review's ignored `artifacts/vp-review/` holds pytest output/JUnit and the
disposable HTTP smoke script/output. Sandbox-only Git fixture failures and a stale
Next build-cache/process failure were resolved by a normal-permission rerun and
a clean generated build directory, respectively; final results above passed.

## Explicit limits

- Twenty Linux process-control tests were skipped: 11 process-driver tests and
  9 worker-slice integration tests. Docker Desktop failed to initialize its local
  secrets-engine socket. The existing WSL Docker image lacks Python. No Linux
  production-supervisor run, process containment or measured deployed limits are
  claimed. Direct handler/database tests and a test admission heartbeat do not
  substitute for this evidence. Admission without a worker remains closed.
- Forecast checks establish shape (26 series / seven dates), missingness/cutoffs,
  labeled baseline fallback, null uncalibrated intervals and immutable publication;
  they do not establish predictive accuracy or real Chronos execution. Chronos,
  supplier planning and hosting remain paused.
- The repository's full product gate still references missing `test:unit`,
  `contracts:check` scripts and `tests/integration/test_migrations.py`. These are
  pre-existing gate gaps; the concrete proxy, contract and migration commands above
  were executed directly. A green full-product gate is not claimed.
- Pure scenario freeze/projection is not database scenario capture, allocation
  integration or a completed UI journey. Visitor access, imports, OR convergence
  (#67/#68), deployment and complete V5 release acceptance remain open.
- This is a code/integration review, not an independent mathematical/research
  certification or a production security audit.

SPEC-V5's current interface and acceptance rows now reflect this bounded
implementation. Historical records remain tied to their original environments.
