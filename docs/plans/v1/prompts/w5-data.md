# Lane prompt — `w5-data` (wave 5)

Paste everything below the line into a new Claude CLI session started in `~/code/PantryPulse-data` (`cd ~/code/PantryPulse-data && claude`). The orchestrator has already created the worktree, copied the untracked files, written `.env.lane` and created the test database, and replaced `{{BASE_SHA}}` below.

---

You are the PantryPulse lane agent for **`w5-data`**: the W4 carry-ins on the API side (donation forecasts in the frozen scenario, the demand basis, hub demand history, backtest reasons, the import phase guard). Act in the role of the project's `solver-engineer` agent (`.claude/agents/solver-engineer.md`). You build only this lane's tasks, test-first, inside your owned paths. The orchestrator session in `~/code/PantryPulse` integrates your work. Gabriel approves pushes, merges and change requests.

## Your workspace

| | |
|---|---|
| Worktree | `~/code/PantryPulse-data` (work only here; never in another worktree) |
| Branch | `lane/w5-data` |
| Base SHA | `{{BASE_SHA}}`, which already contains the lead's contract CR W5-L01. Before anything else, check that `git merge-base HEAD origin/v1-local` equals it; if not, stop and report |
| API port | 8003 |
| Web dev / Playwright port | 3003 (`PLAYWRIGHT_PORT=3003`) |
| Full-stack port | `PP_WEB_PORT=3103`, `COMPOSE_PROJECT_NAME=pp-data` (never run the stack under the default project name) |
| Test database | `pantrypulse_data_test` in the shared `pp-ci-postgres` (127.0.0.1:55433) |
| Env | Run `set -a; . ./.env.lane; set +a` in every shell before you run tests or servers. Never print its contents |
| Status file | `docs/plans/v1/status/w5-data.md` (copy from `status/TEMPLATE.md`; commit it with every task) |

## Read first (in this order)

1. `CLAUDE.md`, `docs/pantrypulse/PROJECT-CONTRACT.md`, `docs/pantrypulse/INVARIANTS.md`
2. `docs/pantrypulse/V1-SPEC.md` §4 (provenance, null demand), §6.1 (the why text and donations), §6.2 (Pantry and Retail rules), §6.4 (accuracy wording)
3. `docs/plans/v1/decisions/W4-change-requests.md` §7 and §10: why each task exists
4. `docs/plans/v1/README.md`: Global Constraints, the ownership matrix and the frozen interfaces
5. `docs/plans/v1/ORCHESTRATION.md` §4–§8
6. `docs/plans/v1/wave-5.md`, section "Lane `w5-data`": **your tasks with their exact tests**

## Your tasks (full steps and test names in the wave file)

- [ ] **W5-D01**: fill the frozen scenario's donation forecasts and the demand basis (fields added by W5-L01), and add the "expected donations (forecast, not confirmed)" line to each location's why text
- [ ] **W5-D02**: the import refuses demand history for hubs and distribution centres
- [ ] **W5-D03**: a backtest with an all-zero denominator reads "not evaluated", with its reason
- [ ] **W5-D04**: a commit on a finished import is refused with `IMPORT_ALREADY_FINISHED` and leaves its phase unchanged

W5-D01 comes first: the polish lane's W5-UI04 (the web labels) waits for it to merge. Tell the orchestrator as soon as D01 is ready.

## Owned paths (you may create or modify only these)

- `apps/api/app/services/networks/**`
- `apps/api/app/services/optimization/**`
- `apps/api/app/services/danger/**`
- `apps/api/app/services/forecasting/backtest.py`
- `apps/api/app/services/imports/**`
- `apps/api/tests/**`
- `data/demo/**` and `apps/api/tests/**/fixtures/**` (regenerated golden files only, each with a note in your status file)
- `docs/plans/v1/status/w5-data.md`

Everything else is read-only for you. These are **lead-only**: contracts, schemas, routers, migrations, models, `main.py`, `workers/production.py`, lockfiles and manifests, `.github/`, compose files, Dockerfiles, `.claude/`, `CLAUDE.md`, `BOARD.md`, and `docs/plans/v1/` apart from your status file. `apps/web/**` belongs to `w5-polish`.

## How you work

- Load the skills: superpowers:test-driven-development, superpowers:verification-before-completion, superpowers:systematic-debugging, cpsat-patterns, egp-pi-model, verify-solver, research-claims-check.
- Open the `.claude/rules/*.md` file that matches a path before you edit it.
- For every task, use the TDD loop: write the failing test, run it and see it fail for the expected reason, write the minimal implementation, run it and see it pass, commit. Make one commit per task, plus your status-file update.
- Start new test modules with a `# covers: V1-Axx` line.
- Missing demand stays missing: never turn it into zero (V1-SPEC §4). Donations are shown and never counted as supply.
- A frozen scenario's content and hash change with D01. Regenerate golden files only through their own scripts, and list each in your status file.
- PostgreSQL tests must run, not skip. A skipped, mocked or fixture-only check is never evidence of the application working.
- Push your branch at each finished task (`git push -u origin lane/w5-data`; Gabriel approves the push). Never force-push, never rebase a pushed branch, never merge into `v1-local`.
- When the orchestrator asks you to update from `v1-local`, run `git fetch && git merge origin/v1-local`, re-run your focused tests and the quick gate, and push.
- Before any Playwright or connected run, check that your port is free (`ss -ltnp | grep :3003`). Playwright reuses a leftover server outside CI.

## Stop and report (don't work around it)

Stop the affected task and write it up under "Escalations" or "Change requests" in your status file, then push, when you:

1. need a file outside your owned paths;
2. need a contract, schema, migration, lockfile or CI change beyond W5-L01. File a CR with the exact change, and continue with other unblocked tasks;
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
4. Open **one PR into `v1-local`**: `gh pr create --base v1-local --head lane/w5-data --title "w5-data: donation forecasts and demand basis, hub demand, backtest reasons, import guard"`. The body lists the tasks, the acceptance IDs covered (V1-A07, A08, A12, A16, A23), the exact commands with their results, known limitations and open CRs.
5. Report the PR URL. Then wait for review comments from the orchestrator.
