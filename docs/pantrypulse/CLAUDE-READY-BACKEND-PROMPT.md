# Claude Code prompt: implement the six READY backend components

Paste the prompt below into a Claude Code session started at the repository root. It uses the configured orchestration (CLAUDE.md, TASK-PROTOCOL.md): the main session is the lead, solver-engineer and forecast-engineer build in isolated worktrees, and verifier reviews each lane. Section 13 of BACKEND-SPEC.md stays the component contract.

```text
Act as the PantryPulse lead (main session) using the configured orchestration in CLAUDE.md and
docs/pantrypulse/TASK-PROTOCOL.md. Implement only the six READY backend components, gbw30/PantryPulse
issues #1–#6 (BE-01…BE-06). Do not continue into the rest of the backend.

Repository: C:\Users\gabri\.vscode\projects\Hackathons\GATORHACK26\PantryPulse

Authority, highest first: this prompt; CLAUDE.md, .claude/rules and TASK-PROTOCOL.md; the local
docs/pantrypulse/BACKEND-SPEC.md (section 0, sections 13.1–13.8, section 14 blockers); the six issue
bodies. If local section 13 and an issue materially disagree, report the exact conflict for that
component and continue with the others. Main's BD-30 is observability; the reconciled two-mode choice
is BD-41. Both transfer modes are required, with no default.

Specification versions (already established):
- The local, untracked BACKEND-SPEC.md is the actionable contract. It was built on origin/main
  a0ad11f, adds BD-41 and section 13, and must not be replaced by origin's shorter version.
- origin/main's BACKEND-DESIGN-CHECKPOINT.md (BD-01–40) is newer than the local copy (BD-01–29); the
  spec defers to main's decisions.
- This prompt document is also local and untracked.
- Builder worktrees only see committed files, so these docs must be committed on the integration
  branch before any builder starts (step 4).

Read first: CLAUDE.md; .claude/rules for touched paths; BACKEND-SPEC.md sections 0, 13 and 14;
TASK-PROTOCOL.md; the six issue bodies (`gh issue view N`); apps/api/pyproject.toml; existing
API/test conventions and apps/api/tests/test_health.py.

Component boundaries (the only implementation writes allowed):
- BE-01 #1: apps/api/app/schemas/planning_primitives.py, apps/api/tests/test_planning_primitives.py
- BE-02 #2: apps/api/app/services/transfer_modes.py, apps/api/tests/test_transfer_modes.py (needs BE-01)
- BE-03 #3: apps/api/app/services/demand_targets.py, apps/api/tests/test_demand_targets.py
- BE-04 #4: apps/api/app/services/fixed_point.py, apps/api/tests/test_fixed_point.py
- BE-05 #5: apps/api/app/services/solver_outcomes.py, apps/api/tests/test_solver_outcomes.py
- BE-06 #6: apps/api/app/services/forecasting/history.py, apps/api/tests/forecasting/test_history.py
- apps/api/tests/forecasting/__init__.py only if test collection needs it. Every other package
  __init__.py already exists.

Plan to present before any write (then wait for my approval):
1. Record git status, HEAD, worktree list and divergence from origin/main. Leave the existing
   C:\Users\gabri\.codex\worktrees\* worktrees alone.
2. Lanes:
   - Lead: BE-01, because it is in app/schemas (lead-owned) and is BE-02's only dependency. The lead
     builds it test-first in the integration worktree.
   - solver-engineer: BE-02, BE-04, BE-05.
   - forecast-engineer: BE-03, BE-06.
   - verifier: reviews each lane. At most these two builders; no nested workers.
3. Draft packets docs/pantrypulse/tasks/PP-01.md … PP-06.md, one per issue: BE ID, issue URL, base
   SHA (filled in at step 4), exact write boundary, dependencies, acceptance commands, reviewer, stop
   rule and evidence fields.

After approval:
4. Integration base, without touching the main checkout's files or my uncommitted work:
   - `git worktree add -b be/ready-1-6 C:\Users\gabri\.vscode\projects\Hackathons\GATORHACK26\PantryPulse-be-ready main`
     (a sibling folder, outside the repo).
   - In that worktree, merge origin/main (needs my OK per settings), copy in the local
     BACKEND-SPEC.md and this prompt document, write the six packets, and commit:
     "docs: adopt READY backend spec and task packets".
   - Implement BE-01 test-first, run its targeted pytest and Ruff, and commit. That commit is BASE_SHA.
5. Dispatch solver-engineer and forecast-engineer with `isolation: worktree` and their packets.
   - Each builder confirms HEAD == BASE_SHA before writing. A native isolated worktree may start
     from main instead; the builder then stops and reports, and the lead creates a non-forced task
     branch at BASE_SHA inside that clean worktree before resuming.
   - It writes a meaningful failing test first, then implements.
   - It runs only its components' pytest file(s) and Ruff from apps/api, natively. These are pure
     functions: no Docker, dependency, lock or model changes.
   - It commits only its allowed files on its own worktree branch and returns commit SHA, files,
     exact commands and results.
6. For each lane, give verifier the packet requirements, the diff (BASE_SHA..lane commit) and the
   tests before any builder rationale.
   - Verifier derives at least one independent counterexample per issue and returns
     PASS/FAIL/UNVERIFIED per issue.
   - On FAIL, send the builder the smallest failing case. After two materially different failed
     fixes, stop that issue and report a minimal failing example. The other issues continue.
7. Cherry-pick passing lane commits onto be/ready-1-6 (needs my OK per settings). Then run once,
   from apps/api in the integration worktree:
   uv run --frozen pytest -q tests/test_planning_primitives.py tests/test_transfer_modes.py tests/test_demand_targets.py tests/forecasting/test_history.py tests/test_fixed_point.py tests/test_solver_outcomes.py tests/test_health.py
   uv run --frozen ruff check app/schemas/planning_primitives.py app/services/transfer_modes.py app/services/demand_targets.py app/services/forecasting/history.py app/services/fixed_point.py app/services/solver_outcomes.py tests/test_planning_primitives.py tests/test_transfer_modes.py tests/test_demand_targets.py tests/forecasting/test_history.py tests/test_fixed_point.py tests/test_solver_outcomes.py
   Repeat testing only for a failure, a new edit or a concrete regression. If frozen uv would fetch
   packages, use its offline option and disclose the command. A failed environment check is not a pass.

Component rules (from section 13):
- Pure and deterministic: no database, network or filesystem side effects, and no model or solver
  imports.
- Use each issue's exact input types, return shapes, exceptions, rejection order and nonmutation
  rules. Validate all inputs before route rules.
- Keep strict no-default mode selection, separate from allocation method.
- MODE_ROUTE_ALLOWED is not full feasibility. The fixed-point helper is not an objective or a
  whole-solver overflow proof. Native status permission is not publication approval. History
  alignment is not imputation, proxy selection, CSV import or forecasting.
- Tests use independent expected values and adversarial cases from the issue, never copies of the
  implementation logic.
- Preserve the existing health response and expose no new domain routes.

Out of scope: dependencies or lockfiles; public routes or final TypeScript DTOs; ORM or migrations;
receipts or stock changes; scenario persistence, FEFO, shortages/surplus or transfer verification;
forecast providers, baseline/fallback or buffer policy; queues, workers or auth; supplier planning;
solver objectives or AP/RP work; containers, model downloads, benchmarks or hosting. Decide no OPEN
topic from section 14. A missing business decision, a materially ambiguous contract, or a write
outside a boundary is reported as a blocker for that component only.

Never: modify, stage or commit anything in the main checkout (including my uncommitted and untracked
work); push; open PRs; comment on or close issues; merge into main; deploy; delete or prune any
worktree; or claim the integrated backend or research engine is complete.

Finish with:
- a table of issue -> lane -> commit SHA -> files -> targeted pytest/Ruff result -> verifier verdict
  -> remaining limitations;
- the combined regression output;
- the integration branch and worktree paths;
- proof that the main checkout's status is unchanged.
The request is complete when all six components are implemented and verified, or each unresolved one
has a concrete blocker with the independent work preserved.
```
