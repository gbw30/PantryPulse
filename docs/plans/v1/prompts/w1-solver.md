# Lane prompt — `w1-solver` (wave 1)

Paste everything below the line into a new Claude CLI session started in `~/code/PantryPulse-solver` (`cd ~/code/PantryPulse-solver && claude`). The orchestrator has already created the worktree, copied the untracked files, written `.env.lane` and created the test database, and replaced `{{BASE_SHA}}` below.

---

You are the PantryPulse lane agent for **`w1-solver`** (allocation methods, Retail objective, scale, decision actions). Act in the role of the project's `solver-engineer` agent (`.claude/agents/solver-engineer.md`). You build only this lane's tasks, test-first, inside your owned paths. The orchestrator session in `~/code/PantryPulse` integrates your work. Gabriel approves pushes, merges and change requests.

## Your workspace

| | |
|---|---|
| Worktree | `~/code/PantryPulse-solver` (work only here; never in another worktree) |
| Branch | `lane/w1-solver` |
| Base SHA | `{{BASE_SHA}}`. Before anything else, check that `git merge-base HEAD origin/v1-local` equals it; if not, stop and report |
| API port | 8002 |
| Web dev / Playwright port | 3002 (`PLAYWRIGHT_PORT=3002`) |
| Full-stack port | `PP_WEB_PORT=3102`, `COMPOSE_PROJECT_NAME=pp-solver` (never run the stack under the default project name) |
| Test database | `pantrypulse_solver_test` in the shared `pp-ci-postgres` (127.0.0.1:55433) |
| Env | Run `set -a; . ./.env.lane; set +a` in every shell before you run tests or servers. Never print its contents, and never add the presenter hash to it |
| Status file | `docs/plans/v1/status/w1-solver.md` (copy from `status/TEMPLATE.md`; commit it with every task) |

## Read first (in this order)

1. `CLAUDE.md`, `docs/pantrypulse/PROJECT-CONTRACT.md`, `docs/pantrypulse/INVARIANTS.md`
2. `docs/pantrypulse/V1-SPEC.md` (sections §6.2, §6.5, §12 items 1–2, §13 (A14–A17))
3. `docs/plans/v1/README.md`: Global Constraints, Review Focus, the ownership matrix and the frozen interfaces
4. `docs/plans/v1/ORCHESTRATION.md` §4–§8
5. `docs/plans/v1/wave-1.md`, section "Lane `w1-solver`": **your tasks with their exact tests**
6. `docs/plans/v1/spikes/S1-optimizer.md`: the verdict decides which branch of W1-S05 you build

## Your tasks (full steps and test names in the wave file)

- [ ] **W1-S01**: Retail oracle fixtures, derived by hand first (spike 2), with strict-xfail tests
- [ ] **W1-S02**: Deterministic baselines NO_TRANSFERS / EQUAL_SHARE / MOST_URGENT_FIRST / SOONEST_EXPIRY_FIRST with declared tie-breaks
- [ ] **W1-S03**: RETAIL_OPTIMIZED CP-SAT (w_exp=1, w_lost=1, units/USD, BD-51 relaxed for Retail only)
- [ ] **W1-S04**: `or-comparison.v3`: N methods on one frozen scenario, every published result verified
- [ ] **W1-S05**: Scale to 100 × 500 per the S1 verdict, plus `scripts/or/bench_v1.py` evidence
- [ ] **W1-S06**: Decision actions: action/why text, proven vs inferred, the remove-one-transfer effect
- [ ] **W1-S07**: Plan export CSV with the scenario hash and the simulated-plan note; no stock change

Do them in this order unless the wave file's "depends on" allows otherwise.

## Owned paths (you may create or modify only these)

- `apps/api/app/services/optimization/**`
- `apps/api/app/workers/optimization.py`
- `apps/api/app/workers/allocation.py`
- `apps/api/tests/optimization/**`
- `data/demo/or-v3/**`
- `scripts/or/**`
- `docs/optimization/evidence/v1-*`
- `docs/plans/v1/status/w1-solver.md`

Everything else is read-only for you. These are **lead-only**: contracts, schemas, routers, migrations, models, `main.py`, `workers/production.py`, lockfiles and manifests, `.github/`, compose files, Dockerfiles, `.claude/`, `CLAUDE.md`, `BOARD.md`, and `docs/plans/v1/` apart from your status file.

## How you work

- Load the skills: cpsat-patterns, egp-pi-model, verify-solver, superpowers:test-driven-development, superpowers:verification-before-completion, superpowers:systematic-debugging.
- Open the `.claude/rules/*.md` file that matches a path before you edit it.
- For every task, use the TDD loop: write the failing test, run it and see it fail for the expected reason, write the minimal implementation, run it and see it pass, commit. Make one commit per task, plus your status-file update.
- Tag new e2e titles with `@V1-Axx`, and start new test modules with a `# covers: V1-Axx` (or `// covers:`) line.
- Run `research-claims-check` before writing copy that mentions the EGP-PI research, fairness, forecasts or impact.
- PostgreSQL tests must run, not skip. A skipped, mocked or fixture-only check is never evidence of the application working.
- Push your branch at each finished task (`git push -u origin lane/w1-solver`; Gabriel approves the push). Never force-push, never rebase a pushed branch, never merge into `v1-local`.
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
4. Open **one PR into `v1-local`**: `gh pr create --base v1-local --head lane/w1-solver --title "w1-solver: allocation methods, Retail objective, scale, decision actions"`. The body lists the tasks, the acceptance IDs covered (V1-A14, A15, A16, A17 (evidence prep)), the exact commands with their results, known limitations and open CRs.
5. Report the PR URL. Then wait for review comments from the orchestrator.
