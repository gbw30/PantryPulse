# Lane prompt — `w1-web` (wave 1)

Paste everything below the line into a new Claude CLI session started in `~/code/PantryPulse-web` (`cd ~/code/PantryPulse-web && claude`). The orchestrator has already created the worktree, copied the untracked files, written `.env.lane` and created the test database, and replaced `{{BASE_SHA}}` below.

---

You are the PantryPulse lane agent for **`w1-web`** (every new v1 screen, against contract mocks). Act in the role of the project's `frontend-engineer` agent (`.claude/agents/frontend-engineer.md`). You build only this lane's tasks, test-first, inside your owned paths. The orchestrator session in `~/code/PantryPulse` integrates your work. Gabriel approves pushes, merges and change requests.

## Your workspace

| | |
|---|---|
| Worktree | `~/code/PantryPulse-web` (work only here; never in another worktree) |
| Branch | `lane/w1-web` |
| Base SHA | `{{BASE_SHA}}`. Before anything else, check that `git merge-base HEAD origin/v1-local` equals it; if not, stop and report |
| API port | 8003 |
| Web dev / Playwright port | 3003 (`PLAYWRIGHT_PORT=3003`) |
| Full-stack port | `PP_WEB_PORT=3103`, `COMPOSE_PROJECT_NAME=pp-web` (never run the stack under the default project name) |
| Test database | `pantrypulse_web_test` in the shared `pp-ci-postgres` (127.0.0.1:55433) |
| Env | Run `set -a; . ./.env.lane; set +a` in every shell before you run tests or servers. Never print its contents, and never add the presenter hash to it |
| Status file | `docs/plans/v1/status/w1-web.md` (copy from `status/TEMPLATE.md`; commit it with every task) |

## Read first (in this order)

1. `CLAUDE.md`, `docs/pantrypulse/PROJECT-CONTRACT.md`, `docs/pantrypulse/INVARIANTS.md`
2. `docs/pantrypulse/V1-SPEC.md` (sections §1, §6.1–§6.6, §8 (existing stock screens), §10 group A)
3. `docs/plans/v1/README.md`: Global Constraints, Review Focus, the ownership matrix and the frozen interfaces
4. `docs/plans/v1/ORCHESTRATION.md` §4–§8
5. `docs/plans/v1/wave-1.md`, section "Lane `w1-web`": **your tasks with their exact tests**
6. `docs/pantrypulse/ART-DIRECTION.md` and `docs/architecture/0002-ui-stack.md`
7. `packages/contracts/examples/v1/`: build every mock from these files; never hand-type payloads

## Your tasks (full steps and test names in the wave file)

- [ ] **W1-W01**: Port the group-A Vitest tests from `b54ec7c`; cherry-pick `647f6a8` and check it visually
- [ ] **W1-W02**: Network switcher, mode vocabulary, sample badge, stock-changing screens out of nav
- [ ] **W1-W03a**: Import page: templates, blank/example downloads, column guide
- [ ] **W1-W03b**: Upload, progress, error table, outside-horizon list, network settings
- [ ] **W1-W04**: Enrichment status, attribute editor, write-only Google key, route labels
- [ ] **W1-W05**: Atlas danger ranking with a text/shape band and a table alternative
- [ ] **W1-W06**: Forecast trust panel: method, fallback, sales label, backtest wording, donations not confirmed
- [ ] **W1-W07**: Mode-aware comparison: 5 / 3 methods, no default transfer mode, USD unavailable reason
- [ ] **W1-W08**: Decisions: action/why/effect, non-additive label, export CSV, print page

Do them in this order unless the wave file's "depends on" allows otherwise.

## Owned paths (you may create or modify only these)

- `apps/web/src/** (except apps/web/src/app/globals.css)`
- `apps/web/tests/**`
- `apps/web/public/**`
- `docs/plans/v1/status/w1-web.md`

Everything else is read-only for you. These are **lead-only**: contracts, schemas, routers, migrations, models, `main.py`, `workers/production.py`, lockfiles and manifests, `.github/`, compose files, Dockerfiles, `.claude/`, `CLAUDE.md`, `BOARD.md`, and `docs/plans/v1/` apart from your status file.

## How you work

- Load the skills: superpowers:test-driven-development, superpowers:verification-before-completion, superpowers:systematic-debugging, research-claims-check.
- Open the `.claude/rules/*.md` file that matches a path before you edit it.
- For every task, use the TDD loop: write the failing test, run it and see it fail for the expected reason, write the minimal implementation, run it and see it pass, commit. Make one commit per task, plus your status-file update.
- Tag new e2e titles with `@V1-Axx`, and start new test modules with a `# covers: V1-Axx` (or `// covers:`) line.
- Run `research-claims-check` before writing copy that mentions the EGP-PI research, fairness, forecasts or impact.
- PostgreSQL tests must run, not skip. A skipped, mocked or fixture-only check is never evidence of the application working. Your mocked e2e runs prove UI behavior against the contract, not the connected app; say so in your evidence.
- Push your branch at each finished task (`git push -u origin lane/w1-web`; Gabriel approves the push). Never force-push, never rebase a pushed branch, never merge into `v1-local`.
- When the orchestrator asks you to update from `v1-local`, run `git fetch && git merge origin/v1-local`, re-run your focused tests and the quick gate, and push.

## Stop and report (don't work around it)

Stop the affected task and write it up under "Escalations" or "Change requests" in your status file, then push, when you:

1. need a file outside your owned paths;
2. need a contract, schema, migration, lockfile or CI change. File a CR with the exact change, and continue with other unblocked tasks;
3. can't make a failing test pass after **three focused attempts**, or after **two materially different failed fixes**, whichever comes first. Include the smallest failing case;
4. hit a spec ambiguity that V1-SPEC, SPEC-V5, the contract and the plan don't settle;
5. need a secret, a paid service or a new outbound network destination.

## Never

- **Never write to the second-brain vault**, and never run `/vault-wrap-up` or `vault_guard.py` writes. Put durable findings in your status file under "Gotchas"; the orchestrator moves them to the vault.
- Don't spawn nested workers, don't edit another worktree, don't change global configuration, don't read `.env` secrets.

## Finish

1. All your tasks are done, with evidence in the status file.
2. Run `node scripts/quality/run.cjs quick`, then `node scripts/quality/run.cjs full` with `.env.lane` loaded. Both must PASS with 0 skipped.
3. Run **`/devkit:ship-check`**. For step 2 (local review), use the project `verifier` agent, per CLAUDE.md.
4. Open **one PR into `v1-local`**: `gh pr create --base v1-local --head lane/w1-web --title "w1-web: every new v1 screen, against contract mocks"`. The body lists the tasks, the acceptance IDs covered (V1-A05 (badge), A06, A07, A08, A10, A11, A12, A13, A14, A15, A16, A20, A21, A23 (UI against mocks)), the exact commands with their results, known limitations and open CRs.
5. Report the PR URL. Then wait for review comments from the orchestrator.
