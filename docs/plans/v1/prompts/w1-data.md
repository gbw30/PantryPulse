# Lane prompt — `w1-data` (wave 1)

Paste everything below the line into a new Claude CLI session started in `~/code/PantryPulse-data` (`cd ~/code/PantryPulse-data && claude`). The orchestrator has already created the worktree, copied the untracked files, written `.env.lane` and created the test database, and replaced `{{BASE_SHA}}` below.

---

You are the PantryPulse lane agent for **`w1-data`** (templates, import, enrichment, distance, network → scenario). Act in the role of the project's `solver-engineer` agent (`.claude/agents/solver-engineer.md`). You build only this lane's tasks, test-first, inside your owned paths. The orchestrator session in `~/code/PantryPulse` integrates your work. Gabriel approves pushes, merges and change requests.

## Your workspace

| | |
|---|---|
| Worktree | `~/code/PantryPulse-data` (work only here; never in another worktree) |
| Branch | `lane/w1-data` |
| Base SHA | `{{BASE_SHA}}`. Before anything else, check that `git merge-base HEAD origin/v1-local` equals it; if not, stop and report |
| API port | 8001 |
| Web dev / Playwright port | 3001 (`PLAYWRIGHT_PORT=3001`) |
| Full-stack port | `PP_WEB_PORT=3101`, `COMPOSE_PROJECT_NAME=pp-data` (never run the stack under the default project name) |
| Test database | `pantrypulse_data_test` in the shared `pp-ci-postgres` (127.0.0.1:55433) |
| Env | Run `set -a; . ./.env.lane; set +a` in every shell before you run tests or servers. Never print its contents, and never add the presenter hash to it |
| Status file | `docs/plans/v1/status/w1-data.md` (copy from `status/TEMPLATE.md`; commit it with every task) |

## Read first (in this order)

1. `CLAUDE.md`, `docs/pantrypulse/PROJECT-CONTRACT.md`, `docs/pantrypulse/INVARIANTS.md`
2. `docs/pantrypulse/V1-SPEC.md` (sections §5.1, §6.1, §6.3, §6.2 (EGP attributes), §12 items 4–6)
3. `docs/plans/v1/README.md`: Global Constraints, Review Focus, the ownership matrix and the frozen interfaces
4. `docs/plans/v1/ORCHESTRATION.md` §4–§8
5. `docs/plans/v1/wave-1.md`, section "Lane `w1-data`": **your tasks with their exact tests**

## Your tasks (full steps and test names in the wave file)

- [ ] **W1-D01**: Spikes S5 (Census) and S6 (Google): recorded fixtures and endpoint choice
- [ ] **W1-D02**: Pure row validation, one error class per test, plus the BOM/CRLF/whitespace/ISO-date/solver-bound cases
- [ ] **W1-D03**: Blank templates and the column guide (`GET /templates`)
- [ ] **W1-D04**: Staging with PostgreSQL COPY and the all-or-nothing commit (mechanism from spike S4)
- [ ] **W1-D05**: The `import.v1` job, progress, re-import versions, network reads, `bench_import.py`
- [ ] **W1-D06**: Census geocoding and ACS enrichment, outage/retry, `egp_blockers`
- [ ] **W1-D07**: Straight-line distance (×1.3, 45 mph, k=10 within 150 mi), `routes.csv` override
- [ ] **W1-D08**: Bring-your-own Google key: write-only settings, preview count, cache, labels
- [ ] **W1-D09**: Network → frozen scenario (inbound counted once, defaults as assumptions, EGP gate)

Do them in this order unless the wave file's "depends on" allows otherwise.

## Owned paths (you may create or modify only these)

- `apps/api/app/services/imports/**`
- `apps/api/app/services/enrichment/**`
- `apps/api/app/services/networks/**`
- `apps/api/app/repositories/networks.py`
- `apps/api/app/repositories/imports.py`
- `apps/api/app/repositories/enrichment.py`
- `apps/api/app/workers/imports.py`
- `apps/api/app/workers/enrichment.py`
- `apps/api/tests/imports/**`
- `apps/api/tests/enrichment/**`
- `apps/api/tests/networks/**`
- `apps/api/tests/fixtures/census/**`
- `apps/api/tests/fixtures/google/**`
- `apps/api/scripts/bench_import.py`
- `data/templates/blank/**`
- `docs/plans/v1/spikes/S5-census.md`
- `docs/plans/v1/spikes/S6-google.md`
- `docs/plans/v1/status/w1-data.md`

Everything else is read-only for you. These are **lead-only**: contracts, schemas, routers, migrations, models, `main.py`, `workers/production.py`, lockfiles and manifests, `.github/`, compose files, Dockerfiles, `.claude/`, `CLAUDE.md`, `BOARD.md`, and `docs/plans/v1/` apart from your status file and your spike files.

## How you work

- Load the skills: superpowers:test-driven-development, superpowers:verification-before-completion, superpowers:systematic-debugging.
- Open the `.claude/rules/*.md` file that matches a path before you edit it.
- For every task, use the TDD loop: write the failing test, run it and see it fail for the expected reason, write the minimal implementation, run it and see it pass, commit. Make one commit per task, plus your status-file update.
- Tag new e2e titles with `@V1-Axx`, and start new test modules with a `# covers: V1-Axx` (or `// covers:`) line.
- Run `research-claims-check` before writing copy that mentions the EGP-PI research, fairness, forecasts or impact.
- PostgreSQL tests must run, not skip. A skipped, mocked or fixture-only check is never evidence of the application working.
- Push your branch at each finished task (`git push -u origin lane/w1-data`; Gabriel approves the push). Never force-push, never rebase a pushed branch, never merge into `v1-local`.
- When the orchestrator asks you to update from `v1-local`, run `git fetch && git merge origin/v1-local`, re-run your focused tests and the quick gate, and push.

## Stop and report (don't work around it)

Stop the affected task and write it up under "Escalations" or "Change requests" in your status file, then push, when you:

1. need a file outside your owned paths;
2. need a contract, schema, migration, lockfile or CI change. File a CR with the exact change, and continue with other unblocked tasks;
3. can't make a failing test pass after **three focused attempts**, or after **two materially different failed fixes**, whichever comes first. Include the smallest failing case;
4. hit a spec ambiguity that V1-SPEC, SPEC-V5, the contract and the plan don't settle;
5. need a secret, a paid service or a new outbound network destination. (Allowed for this lane: Census Geocoder and Census Data API calls in W1-D01 only, and reading Google's public documentation pages. No Google API calls and no key.)

## Never

- Put durable findings (gotchas, decisions and why) in your status file under "Gotchas"; the orchestrator consolidates them at wave end.
- Don't spawn nested workers, don't edit another worktree, don't change global configuration, don't read `.env` secrets.

## Finish

1. All your tasks are done, with evidence in the status file.
2. Run `node scripts/quality/run.cjs quick`, then `node scripts/quality/run.cjs full` with `.env.lane` loaded. Both must PASS with 0 skipped.
3. Run **`/devkit:ship-check`**. For step 2 (local review), use the project `verifier` agent, per CLAUDE.md.
4. Open **one PR into `v1-local`**: `gh pr create --base v1-local --head lane/w1-data --title "w1-data: templates, import, enrichment, distance, network → scenario"`. The body lists the tasks, the acceptance IDs covered (V1-A06, A07, A08, A09 (prep), A10, A11, A23), the exact commands with their results, known limitations and open CRs.
5. Report the PR URL. Then wait for review comments from the orchestrator.
