# v1 orchestration protocol

This protocol governs the v1 waves in [README.md](README.md). Precedence follows CLAUDE.md: V1-SPEC and Gabriel's explicit decisions come first, then contracts and invariants, then CLAUDE.md, the rules, the agents and this plan, then Superpowers skills. Where this protocol amends a CLAUDE.md delivery rule, the amendment is Gabriel's 2026-11-04 decision and is marked **(amends CLAUDE.md)**.

## 1. Roles

| Role | Who | Does | Never does |
|---|---|---|---|
| **Gabriel** | the user | Approves each wave start, every contract/schema change request, every merge into `v1-local`, scope changes, and outward-facing release actions (tag, image publish, public packages). Opens the lane sessions in multi-session mode. Runs the Windows 11 checks | — |
| **Orchestrator** | one Claude session in `~/code/PantryPulse`, acting as the CLAUDE.md lead (`lead-integrator` role) | Sets up worktrees, `.env.lane` and test databases. Launches or briefs lanes. Monitors progress through git/gh. Reviews each lane PR with the `verifier` agent and `/code-review`. Runs `/devkit:ship-check` and the full gate on each integration candidate. Prepares merges, decides change requests with Gabriel, keeps `BOARD.md` current and reports to Gabriel. Consolidates the lanes' "Gotchas" at the end of every wave | Merge into `v1-local` without Gabriel's OK. Let a lane edit a lead-only file |
| **Lane agent** | one Claude session (multi-session) or one subagent (in-session) per lane | Builds only its own tasks, test-first, inside its owned paths. Keeps its status file current. Finishes with `/devkit:ship-check` and a PR into `v1-local` | Edit outside its paths. Change the contract or schema. Merge. Force-push. Start nested workers |
| **Reviewers** | project agents `verifier`, `adversarial-reviewer`, `ux-critic` | Read-only milestone gates. They receive the requirements, the diff and the tests before any builder rationale | Edit application sources. Review their own changes |

**(amends CLAUDE.md "Builders never … push, open PRs")** In multi-session mode, a lane agent may push its own `lane/*` branch and open **one PR into `v1-local`**, after `/devkit:ship-check` and with Gabriel's per-push approval. `git push` is in the `ask` list in `.claude/settings.json`. Lanes still never merge. In-session subagents never push. The orchestrator pushes and opens their PRs.

## 2. Execution modes

Checked against this setup on 2026-11-04 (Claude Code 2.1.318):

- The Agent tool supports `isolation: "worktree"` and background runs. Every project builder agent (`forecast-engineer`, `solver-engineer`, `frontend-engineer`, `integration-fixer`) declares `isolation: worktree` and `maxTurns: 35` (25 for `integration-fixer`). Harness worktrees live under `.claude/worktrees/` (gitignored), not under `~/code/PantryPulse-<lane>`.
- The Workflow tool exists, but needs Gabriel's explicit opt-in ("use a workflow"), so this plan does not depend on it.
- `ListAgents` lists peer Claude sessions on this machine, and `SendMessage` can address them. Whether a freshly opened lane session shows up there is **unverified**. Check it at W0-10. Either way, git/gh is the record.
- CI (`.github/workflows/pantrypulse-ci.yml`) runs on every `pull_request` whatever the base, so PRs into `v1-local` get the Linux gates.

**A. In-session.** The orchestrator dispatches a project builder agent (never `general-purpose`, per CLAUDE.md) with a task packet, in a harness worktree, in the background. Use it for bounded work that fits in 35 turns: spikes, one-task fixes, read-only reviews. The orchestrator records the harness worktree path in BOARD.md, then pushes and opens the PR itself.

**B. Multi-session.** Gabriel opens one Claude CLI session per worktree (`cd ~/code/PantryPulse-<lane> && claude`) and pastes the generated lane prompt from [prompts/](prompts/). Use it for lanes longer than about 35 turns. Those lanes need the Stop gate, interactive permission prompts and Gabriel's eye. The orchestrator monitors through `git fetch`, `gh pr view` and `gh pr checks`, and through `SendMessage` if W0-10 shows that it works.

| Wave | Mode | Why |
|---|---|---|
| W0 | Orchestrator works directly; spikes S1 and S4 use **A** (`solver-engineer`, which owns solver/data per CLAUDE.md) | Spikes are throwaway and bounded; the contract freeze must be done by the lead |
| W1 | **B** for all three lanes | Each lane is 7–9 tasks (several lane-days), well past the 35-turn cap |
| W2 | Orchestrator; `verifier`, `adversarial-reviewer` and `integration-fixer` use **A** | Integration is lead work; reviews and minimal fixes are short |
| W3 | **B** for all three lanes | Same reason as W1 |
| W4 | Orchestrator; reviewers, `ux-critic` and `integration-fixer` use **A** | Same reason as W2 |
| W5 | **B** for both lanes | Polish needs interactive visual iteration; packaging needs Docker and long runs |
| W6 | Orchestrator plus Gabriel; `verifier` uses **A** | Release actions need Gabriel's go-ahead one by one |

## 3. Wave lifecycle

1. **Prepare (orchestrator):**
   - `git fetch`; record the wave's base SHA, which is the `v1-local` head after the previous integration.
   - Create each worktree with `git worktree add ~/code/PantryPulse-<lane> -b lane/<wave>-<lane> <base SHA>`.
   - Copy the untracked files ([README isolation table](README.md#isolation-table)) and write `.env.lane`.
   - Create the lane's test database: `docker exec pp-ci-postgres createdb -U pantrypulse <db>`.
   - Run `npm ci` and `uv sync --frozen --project apps/api`.
   - Replace `{{BASE_SHA}}` in each lane prompt with the base SHA.
2. **Wave-start report** to Gabriel (§7). Gabriel approves the start.
3. **Launch:** mode A dispatch, or Gabriel pastes the prompts (mode B).
4. **Run:** lanes work their tasks and push their branches at task boundaries. The orchestrator checks each lane at least at every pushed task, and reads the status files and PR checks.
5. **Lane done:** the lane runs `/devkit:ship-check` and opens its PR. The orchestrator runs the `verifier` on it (requirements + diff + tests first), then `/code-review`. Findings go back to the lane through a PR comment and its status file.
6. **Integrate:** the next wave file (W2/W4/W6) lists the merge order. Gabriel approves each merge.
7. **Wave-end report** (§7), then consolidate the lanes' "Gotchas". Remove worktrees that are clean and merged. A dirty worktree is removed only with Gabriel's approval (CLAUDE.md).

## 4. Communication without shared-file conflicts

- **Status file.** Each lane owns exactly one: `docs/plans/v1/status/<lane>.md` (`<lane>` is the wave-prefixed ID, e.g. `w1-data`). It lives only on that lane's branch. It uses [status/TEMPLATE.md](status/TEMPLATE.md): tasks done / in progress / blocked, test evidence (command, commit, result), decisions, gotchas and change requests. The lane commits it with each task.
- **PR description.** It carries the final summary: tasks, acceptance IDs covered, the exact commands and their output, known limitations and open change requests.
- **The orchestrator reads, it never writes, lane branches:**
  - `git fetch origin && git show origin/lane/<wave>-<lane>:docs/plans/v1/status/<lane>.md`
  - `gh pr view <n> --json title,body,commits,statusCheckRollup`
  - `gh pr checks <n>`
- **Orchestrator to lane:** a PR comment (`gh pr comment`), or a message through `SendMessage` if W0-10 verified it. No lane reads another lane's branch.
- **Change requests (CR).**
  - The lane adds a `CR-<lane>-<n>` entry under "Change requests" in its status file, with the file, the exact change, the reason, and which task it unblocks. It pushes, then stops that task.
  - The orchestrator decides with Gabriel. Normally that happens between waves. A CR that blocks a whole lane may land mid-wave: the orchestrator commits it on `v1-local` with Gabriel's OK, and every active lane merges `origin/v1-local`.

## 5. Escalation: stop and report

A lane **stops the affected task and reports** in its status file, and to the orchestrator if messaging works. It does not work around the problem when it:

1. needs to create or change a file outside its owned paths;
2. needs a change to the contract, a schema, a migration, a lockfile or CI;
3. can't make a failing test pass after **three focused attempts**, or after **two materially different failed fixes**, whichever comes first. The two-fix limit comes from CLAUDE.md and the agent files; the three-attempt limit is Gabriel's 2026-11-04 rule. The report includes the smallest failing case;
4. hits an ambiguity that V1-SPEC, SPEC-V5, the contract and this plan don't settle;
5. needs a secret, a paid service, a new outbound network destination, or any action CLAUDE.md reserves for the user.

The lane may continue with other unblocked tasks in its list.

## 6. Merge policy

- The orchestrator prepares each merge: the lane PR is green in CI, the verifier and `/code-review` findings are fixed or accepted, the lane branch contains the current `origin/v1-local`, and the full gate passes on the merge candidate.
- It **asks Gabriel before merging into `v1-local`**, one PR at a time, in the order the wave file gives.
- `gh pr merge <n> --merge`. Never squash a lane PR away, never force-push, never rebase a pushed branch.
- After each merge: `node scripts/quality/run.cjs full` on `v1-local`, plus the e2e gate when web changed. The next lane merges `origin/v1-local` before its own merge.
- `v1-local` → `main` is out of scope for this plan and needs a separate decision.

## 7. Reporting to Gabriel

The orchestrator sends a short report at: **wave start**, **any blocker or change request**, **each PR ready to merge**, and **wave end**. Format:

```markdown
## <Wave N> — <wave start | blocker | PR ready | wave end> — <date>

### Dashboard
| Lane | Task | Status | Evidence |
|---|---|---|---|
| w1-data | W1-D02 | done | `uv run --frozen pytest -q tests/imports` 24 passed, 0 skipped @ abc1234 |
| w1-data | W1-D04 | in progress | — |
| w1-solver | W1-S03 | blocked (CR-w1-solver-1) | failing: tests/optimization/test_retail_oracle.py::test_usd_flip |

### Decisions needed
1. <question> — options: A … / B … — **recommend A** because … — unblocks <task IDs>

### Risks and surprises
- <one line each>

### Next action
<exact action> — <who: Gabriel | orchestrator | lane w1-data>
```

Evidence follows CLAUDE.md: exact commit, command and result. Skipped, mocked or fixture-only checks never count as application validation.

## 8. Rules every lane inherits

- Read CLAUDE.md, `docs/pantrypulse/PROJECT-CONTRACT.md`, `docs/pantrypulse/INVARIANTS.md`, V1-SPEC, [README.md](README.md), your wave file and this protocol before your first task.
- Open the `.claude/rules/*.md` file that matches each path before you edit it.
- W0-08 already created every service function, worker handler and router your task fills, as a stub raising `NotImplementedV1("<task id>")` (a 501). "Create `<file>`" for a stub path means replace the stub body and keep the frozen signature. When your route stops answering 501, delete its row from `STUBS` (or from `test_network_scoped_job_routes_return_501`) in `apps/api/tests/test_v1_contract.py`. That is the only edit a lane may make to that lead-owned file.
- Use the TDD loop for every task: write the failing test, run it and see it fail for the expected reason, write the minimal implementation, run it and see it pass, commit. Use `superpowers:verification-before-completion` before any "done" claim.
- Tag every new e2e title with `@V1-Axx` (the story-coverage convention adopted in W0-09). Put `# covers: V1-Axx` on the first line of new Python test modules.
- Run `research-claims-check` before writing any UI copy or doc that mentions the EGP-PI research, fairness, forecasts or impact.
- Gates before the PR: your task's focused tests, `node scripts/quality/run.cjs quick`, then `node scripts/quality/run.cjs full` with `.env.lane` loaded. Zero skips.
- Put durable findings in your status file under "Gotchas". The orchestrator consolidates them at wave end.
