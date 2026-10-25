# PP-30: PR #49/#50 review fixes

Owner: lead integration session. User requested fixes and one pull request.
Review workspace base: local main 04df41ced650896bd4f4a4cd10de1354b406d216. Published change targets remote main ca5909b1277c86d9f8569886e2ee4fa7589a0f84; the unrelated local worker-spec commit is excluded.
Worktree: C:/Users/gabri/.codex/worktrees/pr49-pr50-fixes/PantryPulse.
Inputs: PR #49 bed08544e3dc9b00499224806d92dd8f437f0644; PR #50 2a8898d3d3983ca6744b33356e33dab5b7c4e862; V5 and F-07/F-11/F-12/F-15, BD-17/41, V5 section 14.

Scope: integrate the two bounded experiments in a review branch; fix numerical mean/ceiling, held-out basis handling, obsolete topology guidance, viewport fitting, mobile provenance and proposal labels. Resolve documentation conflicts without dropping main helpers. Allowed paths: original PR files, corresponding tests, Playwright configuration, this packet, V5 and architecture/forecast guidance. No domain API, DB, worker, model download, production dashboard or deployment.

User decision, October 24, 2026: retain Three.js only in /design-lab with an explicit prototype exception. Production stack remains governed by ADR 0002.

Verification: first demonstrate failing numerical/evaluation regressions; run API suite and Ruff, web types/lint/build, browser regression tests at 1440x900/1280x720/390x844, selection/reduced motion and persistent simulation disclosure. Independent reviewer sign-off remains pending. Full product gates retain documented missing integration checks.

Evidence on October 24, 2026, in the isolated Windows worktree (Python 3.12.13, dependencies installed with `uv sync --frozen` and `npm ci`):

- Numerical/basis regression tests demonstrated 7 failures before fixes; all 18 focused tests pass after fixes.
- Full API suite: 488 passed; one Starlette/httpx deprecation warning.
- Quick quality gate: web typecheck, web ESLint, API Ruff and API tests passed.
- Next.js production build passed, including the static `/design-lab` route.
- Chromium Playwright suite: 6 passed, including the existing scaffold smoke test and five design-lab cases. Viewports: 1440x900, 1280x720, 390x844; fit/reset/resize, mobile disclosure, location selection, reduced motion without hydration errors, optional 3D return and forced WebGL failure fallback. Used isolated port 3011.
- Configuration tests: 17 passed.
- Synthetic evaluation: 26 required series and 182 points; input hash `cc815438cc6e432f61bb46e8a777de40437d151f2a1a779653c1c0df9cb1f854`. This is offline simulated evidence only.
- Inspected mobile screenshot and final source diff; no conflict markers or whitespace errors.

The existing `evaluation.synthetic-v1.json` remains historical evidence for the original PR #49 source snapshot; its source hash and metrics are not certification of this revised source. Reproduce current metrics with `uv run --frozen --directory apps/api python -m scripts.evaluate_forecasting`.

Design tradeoffs: exact decimal-representation arithmetic avoids inventing ceiling units without an epsilon that could erase genuine fractional demand; its small rational-arithmetic overhead is bounded by the sparse window. Held-out truth can contain multiple actual bases so mismatches are counted, while training retains the original mixed-basis rejection and proxy authorization. Responsive map fitting keeps the full overview visible, with a readable location selector for small screens. ADR 0004 records the user's accepted dependency/GPU maintenance tradeoff for optional 3D.

No full product acceptance, live database/API jobs, actual Chronos inference, solver qualification or deployment was performed. Independent reviewer sign-off remains pending. Do not infer release readiness.
