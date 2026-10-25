# PantryPulse

Current authority (2026-10-25): Start with [CURRENT-STATUS.md](docs/pantrypulse/CURRENT-STATUS.md) and [SPEC-V5.md](docs/pantrypulse/SPEC-V5.md). Main includes the baseline API/presenter flow, connected OR comparisons and Linux/browser CI; PR #77 supplies bounded compute/Fly configuration and standalone Chronos evidence. Preserve six beneficiaries plus hub(s), hard FEFO, both explicit transfer modes with no default, frozen scenarios, durable jobs, the Next.js proxy and the research gate. Local backend/model preparation is resumed; supplier planning and public/paid deployment remain separate. Historical notes below do not undo newer accepted decisions.

Build the Gator Hack V MVP: at least six fictional beneficiaries plus hub(s), two products, seven-day forecasts and a 1–3-day simulated allocation window. Preserve the current repository, user changes and running tasks.

## Read first
- docs/pantrypulse/SPEC-V5.md: current project source of truth, code/branch status, accepted decisions, unresolved contracts and acceptance.
- docs/pantrypulse/PROJECT-CONTRACT.md: scope, units, forecast and solver contracts.
- docs/pantrypulse/INVARIANTS.md: quantitative truth conditions.
- docs/pantrypulse/ART-DIRECTION.md: approved visual direction.
- docs/pantrypulse/TASK-PROTOCOL.md: ownership, review and integration.
- docs/pantrypulse/DEMO.md: reset and judge journey.
- docs/pantrypulse/BOARD.md: current integration summary followed by historical delivery rows. Existing task packets are in docs/pantrypulse/tasks/; lead records bounded ownership before delegation.
- docs/pantrypulse/IMPLEMENTATION-PLAN.md and docs/architecture/ (ADR 0001 research gate, ADR 0002 UI stack): current V4 plan and decisions.
- docs/pantrypulse/ACCEPTANCE-MATRIX.md: required evidence per requirement. docs/pantrypulse/BACKEND-DATA-FLOW.md: how data moves through the API.
- INSTALLATION.md and docs/pantrypulse/WINDOWS-DEVELOPMENT.md: setup. SCAFFOLD-VERIFICATION.md: what has actually been run and what has not.
- Reference only, don't preload: docs/pantrypulse/SOURCE-SPEC.md (original PRD), docs/pantrypulse/HANDBOOK.md (orchestration rationale), docs/pantrypulse/templates/ (scaffold fragments for the lead), docs/pantrypulse/ENVIRONMENT.md (toolchain and config verification status).

## Repository map
The repository root is this folder and the only Git repo. Do not create or run from nested copies; the history of a former nested copy is the `legacy/main` ref.
- apps/web: Next.js 16 app (src/app, src/lib, tests/e2e, Playwright). It is the only npm workspace; the root package-lock.json owns the lock.
- apps/api: FastAPI presenter, forecast and planning routers; ORM/repositories; migration head ppor_0005; production forecast.v1/or-comparison.v2 workers; bounded allocation core and independent verifier. Chronos remains a standalone exercise. uv.lock owns Python dependencies.
- packages/contracts: generated OpenAPI and TypeScript output, plus regeneration instructions.
- docs/pantrypulse: product contract, protocol, plans. docs/architecture: ADRs.
- scripts/quality: gate runner and hook tests. scripts/*-windows.ps1: setup and doctor. data/demo: golden fixtures. .claude: agents, hooks, rules, skills and quality-gate.json.

## Navigating and evidence
- Find owners by path: each agent file lists its owned paths and .claude/rules/*.md scope by path glob. Open the matching rule before editing under that path.
- Docs describe the intended contract; code and command output describe current state. Many documented routes, tables and solvers do not exist yet, so grep the code before claiming something is implemented.
- Cite file:line for every claim, separate code from documentation, and write "not found" or "unverified" instead of guessing. Do not report a file you did not open as read.

## Delivery
- Lead owns contracts, migrations, lockfiles, shared configuration, integration, deployment and scope.
- Forecast/projection, solver/data, and frontend work in separate contexts and isolated worktrees. Delegate only bounded work with an explicit base SHA and write boundary. Do not spawn nested workers by default.
- Read-only verifier and UX critic are milestone gates. They report evidence; only the lead integrates. A reviewer does not approve its own changes.
- Never count a skipped, missing, disabled, timed-out, or fixture-only check as application validation.
- Run focused tests before handoff; run full gates on the merged candidate. Report exact commit, commands, results and unresolved limitations.

## Superpowers methods
Superpowers (`superpowers@claude-plugins-official`, reviewed at v7.0.1) supplies engineering methods. The PantryPulse lead stays the orchestrator, and the project agents keep their roles. Precedence, highest first:
1. The consolidated project specification docs/pantrypulse/SPEC-V5.md and later explicit user decisions. SOURCE-SPEC.md and PROJECT-CONTRACT.md retain historical material where compatible.
2. Contracts, invariants and deterministic fixtures.
3. This file, the rules, the agent definitions and the task packet.
4. Superpowers skills.

When a skill conflicts with a project constraint, keep the project rule and use the compatible form below. Never weaken verification or approved product behavior. Full rationale: HANDBOOK.md, Amendment A1.
- **Every lane:** `verification-before-completion` (mandatory: run the commands and read their output before any pass/fixed/deployed claim), `systematic-debugging` (mandatory: root cause before fixing; the two-failed-fix limit below still applies), `test-driven-development` (failing test first for inventory, forecasting, optimization, simulation and API logic; delete only code you wrote in this task) and `receiving-code-review`.
- **Lead only:**
  - `writing-plans`: run once, from the approved PRD. Save the plan to docs/pantrypulse/IMPLEMENTATION-PLAN.md, track tasks on BOARD.md, and turn each task into a PP-NN packet.
  - `brainstorming`: only for decisions that are genuinely open. Don't redo settled requirements.
  - `subagent-driven-development`: selective, for complex independent tasks only. Dispatch the project builder agent for that domain with a packet, never `general-purpose`. At most three builders, no nested workers, and no per-task review cycle for trivial UI changes.
- **`using-git-worktrees`:** the lead creates worktrees at the packet's exact base SHA. Builders started with `isolation: worktree` are already isolated: they check their base and never create a nested worktree.
- **`requesting-code-review`:** the reviewer is the project `verifier` agent (or `ux-critic`/`adversarial-reviewer`), given the requirements, diff and tests before any builder rationale. Review depth scales with risk.
- **`finishing-a-development-branch`:** builders use it only to check readiness, then hand back their commit and evidence. Builders never merge, push, open PRs or discard. The lead integrates; shared-branch merges, discarding work and cleanup of a dirty worktree need the user's approval.
- **Other skills:** use them when directly relevant. Run `diagnosing-superpowers` only on request, and never file issues without the user's approval.

## Other plugins and domain skills
- `context7`: look up docs for the versions pinned in package-lock.json and apps/api/uv.lock (Next 16, React 19, Tailwind 4, shadcn 4, OR-Tools 9.15, Chronos 2.3, SQLAlchemy 2). Retrieved docs don't override the repo's locked versions, contracts or tests. Queries go to Upstash, so never include secrets or data.
- `pyright-lsp`, `typescript-lsp`: diagnostics and navigation. They add to the quick gate; they don't replace it.
- `frontend-design`: method only. ART-DIRECTION.md and ADR 0002 decide the visual direction and component stack.
- Project skills: `egp-pi-model` and `cpsat-patterns` for any solver work, `research-claims-check` before any text about the research, and `verify-solver`/`verify-forecast` at gates.

## Product truth
- Forecasts are projections. Label simulated/proxy data and actual model/fallback provenance.
- Preserve null/missing demand; never silently turn it into zero. No future leakage.
- Raw quantiles are not calibrated intervals or stockout probabilities.
- Preserve inventory, units, reserves, capacities and solver status. Do not sum different category quantities into an unlabeled inventory KPI.
- Keep forecasts immutable; save scenario and planning inputs. Stale inventory versions return 409.
- P0 review is a simulation with no reservation or dispatch. Real approval/completion is P1 and requires atomic reservations and idempotency.
- An LLM never directly approves or changes inventory.

## Commands after scaffold
- Quick: node scripts/quality/run.cjs quick
- Full: node scripts/quality/run.cjs full
- E2E: node scripts/quality/run.cjs e2e
- Config tests: node --test scripts/quality/tests/*.test.cjs
- App checks: npm run check (types, lint, ruff, API tests), npm run build, npm run test:e2e.
- Backend runs in Docker on this Windows host because Application Control blocks OR-Tools natively: npm run dev:api:docker, npm run test:api:docker, npm run check:runtime:docker.
- The Stop gate is enabled and runs the quick gate; it does not run full or e2e.
Gate commands are declared in .claude/quality-gate.json. Active .github/workflows/pantrypulse-ci.yml verifies Linux/PostgreSQL and connected browser behavior and rejects skipped evidence. Do not install historical templates over executable manifests. Solver ceilings are now 300s search / 330s method / 690s comparison, queue expiry 1800s; local stop grace is 725s. Forecast 270/300s and worker 6-CPU/8-GiB ceilings remain.

## Operating limits
- Two materially different failed fixes: return a minimal failing case to the lead.
- A council is one proposal, one critique, one domain check and one lead decision, capped at 10 minutes.
- Feature freeze at hour 41; only demonstrated P0 blockers afterward.
- Keep secrets out of prompts, logs, fixtures and client bundles. Use only dedicated demo/test databases.
- Do not bypass permission controls. Writes outside the named repository, destructive operations, new paid services, production changes and submission need the user's corresponding authorization.
- Do not edit another worktree, force-push, reset away work, or remove a dirty worktree.
