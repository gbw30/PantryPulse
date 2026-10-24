# Scaffold verification — 2026-10-23

> **Current authority:** [Project specification V5](SPEC-V5.md). Historical evidence for its recorded date/tree only. V5 records current bounded test counts and capabilities; stale running-service, hook and uncommitted-file statements below are not current state.

## Finalized UI dependency stack

Installed and locked motion 14.6.0, tw-animate-css 1.4.0 and the local shadcn CLI 4.22.1 in apps/web/package.json and root package-lock.json. Recharts 3.10.1, Lucide, Tailwind and existing Radix/helper dependencies remain. Configured Watermelon and Kokonut namespaces; their individual source components are added on demand, and none were copied in this task. Added ui:add/ui:info npm commands, animation stylesheet imports and semantic theme tokens. Documented the final stack in INSTALLATION.md and ADR 0002; removed Motion/shadcn from the guide's uninstalled-optional list.

Validation: npm run ui:info recognized Next.js 16.4.3, RSC, TypeScript, Tailwind v4, Radix base and both registry URLs. npm ls reports all expected installed packages. npm run typecheck, npm run lint and npm run build passed; build resolves both new stylesheet imports. A metadata check confirmed the web manifest dependency sections match the root lockfile, and git diff --check passed. Product UI components, Motion provider, animations and backend/chart wiring remain future implementation work. No Three.js, React Spring or Bklit dependency was added.

## Developer onboarding follow-up

Re-read the live V4 tab on October 23, 2026; its revision and content match the saved snapshot. Added root INSTALLATION.md with manual Git/Node/npm/uv/Docker/WSL prerequisites, frozen setup, configuration, checks and optional dependency decisions. Installed/locked Recharts 3.10.1 and openapi-typescript 7.13.0. Added npm setup/doctor/config-test/browser-install entry points, Linux-engine preflight, exact Python version validation and container API/runtime diagnostics.

Executed scripts/setup-windows.ps1 -WithContainerApi -WithBrowser successfully: npm ci installed 427 packages, uv checked the 46 core packages, Chromium was available, API/PostgreSQL were healthy, and CP-SAT/SQLAlchemy runtime checks passed. scripts/doctor-windows.ps1 -RequireContainerApi also passed. Re-ran npm run check (lint/types and 2 API tests), npm run build, and npm run test:config (17 passing tests). PowerShell syntax checks and git diff --check passed. UI source did not change; the earlier Playwright smoke result below was not reclassified as a fresh test run.

Metadata checks confirmed the forecast ML extra is locked but absent from the native environment; Motion/MapLibre/React Flow/Vitest/Testing Library/shadcn CLI are absent from the canonical npm dependency tree. MAPIE, scikit-learn and google-genai are also absent from the native Python environment. No optional ML install or model download was performed. The default Docker image continues to exclude the forecast extra. Staged ENVIRONMENT.md changes remain untouched.

Scope: foundation only. No allocation engine, forecast adapter, domain schema, migration, generated domain contract, seed/reset endpoint or complete judge workflow exists yet.

## Executed checks

| Command / evidence | Result |
|---|---|
| scripts/setup-windows.ps1 | PASS: root npm ci, uv sync --frozen, Python 3.12.13 |
| scripts/doctor-windows.ps1 -RequireDatabase | PASS: pinned Node/npm/uv/Python, development readiness, pantrypulse_test query |
| npm run check | PASS: TypeScript, ESLint, Ruff, 2 pytest API scaffold tests |
| npm run build | PASS: Next 16.4.3 production build, static / and /_not-found |
| npm exec --workspace @pantrypulse/web -- playwright install chromium | PASS: Chromium installed |
| npm run test:e2e | PASS: 1 Chromium scaffold test, 16.6s; no solver journey claimed |
| node --test scripts/quality/tests/*.test.cjs | PASS: 17 existing hook/config tests under normal Git permissions |
| PowerShell parser: setup/doctor scripts | PASS; final setup switch addition also parsed |
| docker compose config --quiet | PASS before API addition; API profile subsequently built and started successfully |
| docker compose --profile api up -d --build --wait api | PASS: Python 3.12.13 and uv 0.11.15 image, frozen Linux dependencies |
| npm run check:runtime:docker | PASS: OR-Tools 9.15.6755 trivial CP-SAT OPTIMAL, SQLAlchemy 2.1.6/Alembic 1.20.1/psycopg 3.3.6 imports, actual pantrypulse_dev connection |
| npm run test:api:docker | PASS: 2 tests on Python 3.12.13/Linux |
| HTTP GET http://127.0.0.1:8000/api/v1/health | 200, {"status":"ok","scope":"process"} |
| docker compose --profile api ps | API and postgres healthy, loopback ports 8000 and 55432 |
| git diff --check | PASS, with ordinary LF/CRLF normalization notices |

The static web page has no client/API data path yet. API health is process liveness, not domain readiness. Database connection is separately verified by the runtime smoke. React review: static server components, no effects/client hydration logic or async waterfalls; semantic heading/link and visible keyboard focus.

## Native Windows limitation

Direct OR-Tools import failed because Windows Application Control blocked pandas._libs.groupby. Native health tests do not import it and therefore cannot establish solver readiness. No policy was disabled or bypassed. Use the tested Docker API profile for backend work on this host. Native health development remains possible.

Initial sandbox attempts also failed on uv cache permissions, temporary Git fixtures and local sockets. Authorized normal-environment reruns passed the relevant checks; these restrictions are separate from the native Application Control finding.

Resolved development dependencies emit two nonblocking deprecation notices: ESLint 9 is outside its current support window; Starlette TestClient recommends httpx2 instead of httpx. Current checks pass. Review compatibility at the next intentional dependency update; do not suppress warnings or alter locks silently.

## Research and repository status

V4 was read in full using the native Google Docs tab-aware connector. SPEC-V4.snapshot.txt records revision/tab identity. Publication date and DOI were checked against publisher search evidence and the author's university record. Full paper web retrieval timed out; equation-level review of sections 2.1.3/3 and Appendices A/C is still a prerequisite to solver implementation. The ADR's small oracle is hand arithmetic, not measured solver output.

Preserved staged ENVIRONMENT.md edits, existing nested PantryPulse/ folder, historical fixtures and database volume. No commits, pushes, hosted deployments, external orders or dispatches were performed. Docker Desktop, API and PostgreSQL remain running; the temporary Playwright web server was managed by its runner.

Existing full product gates remain unfulfilled: migration tests, contract drift and domain/judge tests are absent. Hook enforcement remains disabled. Chronos optional dependencies resolve in uv.lock but were not installed or used. No research fidelity, forecasting accuracy or product outcome claim follows from scaffold checks.
