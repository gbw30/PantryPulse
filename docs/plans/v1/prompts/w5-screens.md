# Lane prompt — `w5-screens` (wave 5)

Paste everything below the line into a new Claude CLI session started in `~/code/PantryPulse-screens` (`cd ~/code/PantryPulse-screens && claude`). The orchestrator has already created the worktree, copied the untracked files, written `.env.lane` and created the test database, and replaced `{{BASE_SHA}}` below.

---

You are the PantryPulse lane agent for **`w5-screens`**: the ux-critic fixes on the Data Explorer, the Scenario Lab comparison and Decisions. Act in the role of the project's `frontend-engineer` agent (`.claude/agents/frontend-engineer.md`). You build only this lane's tasks, test-first, inside your owned paths. A second web lane, `w5-polish`, works on the Overview, the shell and the design tokens at the same time; stay out of its paths. The orchestrator session in `~/code/PantryPulse` integrates your work. Gabriel approves pushes, merges and change requests.

## Your workspace

| | |
|---|---|
| Worktree | `~/code/PantryPulse-screens` (work only here; never in another worktree) |
| Branch | `lane/w5-screens` |
| Base SHA | `{{BASE_SHA}}`. Before anything else, check that `git merge-base HEAD origin/v1-local` equals it; if not, stop and report |
| API port | 8005 |
| Web dev / Playwright port | 3005 (`PLAYWRIGHT_PORT=3005`) |
| Full-stack port | `PP_WEB_PORT=3105`, `COMPOSE_PROJECT_NAME=pp-screens` (never run the stack under the default project name) |
| Test database | `pantrypulse_screens_test` in the shared `pp-ci-postgres` (127.0.0.1:55433) |
| Env | Run `set -a; . ./.env.lane; set +a` in every shell before you run tests or servers. Never print its contents, and never add the presenter hash to it |
| Status file | `docs/plans/v1/status/w5-screens.md` (copy from `status/TEMPLATE.md`; commit it with every task) |

## Read first (in this order)

1. `CLAUDE.md`, `docs/pantrypulse/PROJECT-CONTRACT.md`, `docs/pantrypulse/INVARIANTS.md`
2. `docs/pantrypulse/V1-SPEC.md` §4 (provenance), §6 (the screens and their wording), §13 (A12, A14–A16, A20)
3. `docs/plans/v1/decisions/W4-change-requests.md` §6 and §11: why each task exists
4. `docs/plans/v1/README.md`: Global Constraints, the ownership matrix and the frozen interfaces
5. `docs/plans/v1/ORCHESTRATION.md` §4–§8
6. `docs/plans/v1/wave-5.md`, section "Lane `w5-screens`": **your tasks with their exact tests**
7. `docs/pantrypulse/ART-DIRECTION.md` and `docs/architecture/0002-ui-stack.md` (these decide the direction; the jmo skills are method only)

## Your tasks (full text and tests in the wave file)

- [ ] **W5-UI02.1**: the Data Explorer shows only the selected network (no legacy summary block above Forecast trust)
- [ ] **W5-UI02.2**: the Scenario Lab comparison fits: one card per row, nothing clipped, the action link near the top, rows behind a disclosure
- [ ] **W5-UI02.3**: Decisions names the period each effect covers, and says the plan doesn't cover the days after its window
- [ ] **W5-SC01**: follow-ups: the 700-action unit-test timeout, the unit plural ("boxes"), the print selection saved only when the print link is used
- [ ] **W5-SC02**: screenshots of your three screens at three viewports, then finish (below)

## Owned paths (you may create or modify only these)

- `apps/web/src/components/data-explorer/**`
- `apps/web/src/components/scenario-lab/**`
- `apps/web/src/components/decisions/**`
- `apps/web/src/app/data/page.tsx`, `apps/web/src/app/scenarios/**`, `apps/web/src/app/decisions/**`
- `apps/web/tests/unit/decisions-view.test.tsx`, `apps/web/tests/unit/scenario-lab.test.tsx`
- `apps/web/tests/e2e/data-explorer.spec.ts`, `scenario-lab.spec.ts`, `decisions.spec.ts`, `v1-comparison.spec.ts`, and new `apps/web/tests/e2e/v1-screens-*.spec.ts`
- `docs/pantrypulse/visual-evidence/w5-screens/**`
- `docs/plans/v1/status/w5-screens.md`

Everything else is read-only for you. `w5-polish` owns the rest of `apps/web/**`: `globals.css` and its tokens, `components/ui/**`, `components/shell/**`, `components/overview/**`, the e2e helpers and `playwright.config.ts`. If you need a change there, file it as a CR in your status file and tell the orchestrator. These are **lead-only**: contracts, schemas, routers, migrations, models, `main.py`, `workers/production.py`, lockfiles and manifests, `.github/`, compose files, Dockerfiles, `.claude/`, `CLAUDE.md`, `BOARD.md`, and `docs/plans/v1/` apart from your status file.

## How you work

- Load the skills: /jmo-workflow:better-ui, visual-review, superpowers:test-driven-development, superpowers:verification-before-completion, superpowers:systematic-debugging, research-claims-check.
- Open the `.claude/rules/*.md` file that matches a path before you edit it.
- For every task, use the TDD loop: write the failing test, run it and see it fail for the expected reason, write the minimal implementation, run it and see it pass, commit. Make one commit per task, plus your status-file update.
- Tag new e2e titles with `@V1-Axx`, and start new test modules with a `// covers: V1-Axx` line.
- Forecasts are projections; unmet need, dates and windows must be stated, never implied. Run `research-claims-check` before writing copy that mentions forecasts, fairness or impact.
- PostgreSQL tests must run, not skip. A skipped, mocked or fixture-only check is never evidence of the application working.
- Before any Playwright or connected run, check that your port is free (`ss -ltnp | grep :3005`). Playwright reuses a leftover server outside CI.
- Push your branch at each finished task (`git push -u origin lane/w5-screens`; Gabriel approves the push). Never force-push, never rebase a pushed branch, never merge into `v1-local`.
- When the orchestrator asks you to update from `v1-local`, run `git fetch && git merge origin/v1-local`, re-run your focused tests and the quick gate, and push.

## Stop and report (don't work around it)

Stop the affected task and write it up under "Escalations" or "Change requests" in your status file, then push, when you:

1. need a file outside your owned paths;
2. need a contract, schema, migration, lockfile or CI change. File a CR with the exact change, and continue with other unblocked tasks;
3. can't make a failing test pass after **three focused attempts**, or after **two materially different failed fixes**, whichever comes first. Include the smallest failing case;
4. hit a spec ambiguity that V1-SPEC, SPEC-V5, the contract and the plan don't settle;
5. need a secret, a paid service or a new outbound network destination.

## Never

- Put durable findings (gotchas, decisions and why) in your status file under "Gotchas"; the orchestrator consolidates them at wave end.
- Don't spawn nested workers, don't edit another worktree, don't change global configuration, don't read `.env` secrets.

## Finish

1. All your tasks are done, with evidence in the status file.
2. Run `node scripts/quality/run.cjs quick`, then `node scripts/quality/run.cjs full` with `.env.lane` loaded. Both must PASS with 0 skipped.
3. Run **`/devkit:ship-check`**. For step 2 (local review), use the project `verifier` agent, per CLAUDE.md.
4. Open **one PR into `v1-local`**: `gh pr create --base v1-local --head lane/w5-screens --title "w5-screens: Data Explorer, Scenario Lab and Decisions fixes from the W4 UX review"`. The body lists the tasks, the acceptance IDs covered (V1-A12, A14, A15, A16, A20), the exact commands with their results, known limitations and open CRs.
5. Report the PR URL. This lane merges mid-wave, so tell the orchestrator as soon as the PR is open.
