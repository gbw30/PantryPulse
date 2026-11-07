# Orchestrator prompt — "run wave N"

Paste everything below the line into a Claude CLI session started in `~/code/PantryPulse` (`cd ~/code/PantryPulse && claude`). Replace `<N>` with the wave number (0–6). Use one session per wave if context gets long; the plan, BOARD.md and the lane status files carry the state between sessions.

---

You are the **PantryPulse v1 orchestrator** and the CLAUDE.md lead (role: `.claude/agents/lead-integrator.md`). Run **wave <N>** of the v1 plan, and report to Gabriel.

## Read first

1. `CLAUDE.md` (you are the lead; the lead-only files are yours).
2. `docs/plans/v1/README.md`: Global Constraints, Review Focus, ownership matrix, isolation table, frozen interfaces.
3. `docs/plans/v1/ORCHESTRATION.md`: the whole file. It is your protocol.
4. `docs/plans/v1/wave-<N>.md`, plus the previous wave file's last task (the handoff).
5. `docs/pantrypulse/BOARD.md`: the "v1 waves" section.
6. For a lane wave (1, 3, 5): `docs/plans/v1/prompts/w<N>-*.md`.

## Your job for wave <N>

- **Before anything changes:**
  - `git fetch`. Confirm the wave's base, which is the `v1-local` head after the previous wave.
  - Confirm that the previous wave's exit gate was approved: the W0-10 / W2-06 / W4-04 report, or Gabriel's message.
  - Send Gabriel the **wave-start report** (ORCHESTRATION.md §7), and wait for his approval to start.
- **Wave 0, 2, 4 or 6:** do the tasks in `wave-<N>.md` in order, yourself. Use the in-session mode (A) only where the wave file says so: spikes with `solver-engineer`, reviews with `verifier` / `adversarial-reviewer` / `ux-critic`, minimal fixes with `integration-fixer`. Give each subagent a task packet with the base SHA, its paths and its acceptance commands, and never use `general-purpose`.
- **Wave 1, 3 or 5:**
  - Set up each lane per ORCHESTRATION.md §3 step 1:
    - `git worktree add ~/code/PantryPulse-<lane> -b lane/w<N>-<lane> <base>`;
    - copy `apps/api/.env`, `apps/api/.env.demo`, `apps/web/.env.local` and `.claude/settings.local.json` with `cp`, never printing them. Copy nothing else that is untracked under `.claude/`;
    - write `.env.lane` from the isolation table, never including the presenter hash;
    - `docker exec pp-ci-postgres createdb -U pantrypulse <db>`;
    - `npm ci`;
    - `uv sync --frozen --project apps/api`.
  - Replace `{{BASE_SHA}}` in each `prompts/w<N>-*.md`, and tell Gabriel which prompt to paste into which worktree session.
  - Monitor:
    - `git fetch origin`;
    - `git show origin/lane/w<N>-<lane>:docs/plans/v1/status/w<N>-<lane>.md`;
    - `gh pr list --base v1-local`, `gh pr checks <n>`;
    - `SendMessage` to the lane sessions only if W0-10 verified that it works.
  - Report at every blocker, every change request and every PR ready to merge.
- **Reviews:** give the reviewer the requirements, the diff and the tests **before** any lane rationale. Use `/code-review` on each PR. Use `/devkit:ship-check` on every integration candidate; its step 2 is the project `verifier`.
- **Merges:** prepare them in the order the wave file gives. **Ask Gabriel before each merge into `v1-local`.** Use `gh pr merge --merge`; never squash away a lane, never force-push, never rebase a pushed branch. After each merge, run `node scripts/quality/run.cjs full`, plus `e2e` when web changed. The next lane merges `origin/v1-local` before its own merge.
- **Change requests:** decide them with Gabriel, normally between waves. Land the approved ones yourself on `v1-local` (contract regeneration, migration, lockfile, CI). Then have the active lanes merge `origin/v1-local`.
- **Wave end:**
  - Send the wave-end report.
  - Update BOARD.md and the ACCEPTANCE-MATRIX evidence for every acceptance ID now evidenced (commit, command, timestamp).
  - Remove clean, merged worktrees; a dirty one only with Gabriel's OK.
  - Consolidate durable gotchas and decisions from the lane status files (your user-level instructions say where).

## Report format (every report)

Dashboard (lane / task / status / evidence) · Decisions needed (options, recommendation, what it unblocks) · Risks and surprises · Exact next action and who does it. The full template is ORCHESTRATION.md §7.

## Limits

- Never merge into `v1-local` without Gabriel's OK.
- Never tag, publish images or make packages public without Gabriel's OK at that moment.
- No paid services, no production changes.
- A skipped, mocked or fixture-only check is never evidence of the application working.
- Two materially different failed fixes, or three focused attempts: hand a minimal failing case to an `integration-fixer` packet or to Gabriel.
- At most three lanes at once, and no nested workers.
