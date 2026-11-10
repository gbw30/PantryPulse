# Resuming W3 (save point 2026-11-09, late)

> **Historical.** W3 closed on 2026-11-10 at v1-local `caa5010`; the W3 row of [BOARD.md](../../../pantrypulse/BOARD.md) has the outcome, and [decisions/W3-change-requests.md](../decisions/W3-change-requests.md) §1–§13 has the decisions. Don't resume from this file.

W3 started 2026-11-09 from base `0a49593`. The lanes run as separate CLI sessions. Decisions are in [decisions/W3-change-requests.md](../decisions/W3-change-requests.md), §1–§12. §6–§12 are committed only on the local branch `w3/decisions-3`, together with this runbook (see below).

## State at the save point

**v1-local is `a2c7258`.** Everything below is merged into it, after green CI and Gabriel's approval:

| PR | What |
|---|---|
| #121 | Samples W3-P01…P04 |
| #122 | Lead CRs: sample values label, LF templates, no-egress CI |
| #123 | `ppv1_0014`: `forecast_runs.backtest` |
| #124 | Gate limits: Stop hook 600 s, API tests 900 s |
| #125 | Lead CRs 2: example download takes `mode`; seed uses the New York date after the login commits |
| #126 | Test-only: supervisor prepare probe no longer races the heartbeat |

The full gate passed 8/8 on `e3ca57e` (#124 and #125). #126 changes one test file, and its CI full run passed.

**Lead branch, local only, not pushed:** `w3/decisions-3` in worktree `.claude/worktrees/w3-docs`, based on `a2c7258`. It holds decisions §6–§12 and this runbook. Gabriel hasn't approved a push yet. Add the BOARD W3 row before asking.

**Open PRs:**

| PR | Head | State | Next |
|---|---|---|---|
| #127 forecast (`lane/w3-forecast`) | `6214126` (fixes pushed; 50k re-time and full gate still to do) | Verifier: no High findings. F1 (Medium): at 50k series the output and backtest are built inside the queue lock, 4–8 s against a 5 s lock timeout. F2–F4 are test gaps. Gabriel: fix F1 in W3 (move the build into `prepare`), and close F2–F4 | The lane pushes its fixes. Get a verifier re-check of the fix diff (worktree `verify-127`, DB `pantrypulse_verify_test`). Then Gabriel's OK, merge after CI, gate |
| #128 samples follow-up (`lane/w3-samples`) | `a7a015c` | Verifier PASS at `c0fa3ef`: CR-3, CR-4, N1, the authorized edit and the guard. `e0e0414` only changes the G1 comment and status (lead checked the diff); `a7a015c` is status file only. Focused tests 341 passed, 0 skipped; quick 4/4 | **Merges only after the web PR** (Gabriel), then Gabriel's OK, merge after CI, gate |
| web (`lane/w3-web`) | `4e52aaa` pushed, PR not open yet | W03 done (connected 208 passed, 0 skipped, no egress). Doing: CR-w3-web-2 (traces off when `PP_E2E_PRODUCTION=1`), the narrowed "Simulated network" label, `&mode=` on example links with the reason fetch dropped, and a clean rerun of the 3 tests that failed only under load | Lane opens the PR, then a verifier, then Gabriel's OK, merge after CI, gate. Then #128 |

**Merge order (Gabriel):** #127 and the web PR as each is ready and verified, and #128 after the web PR.

**Decided this session (all in decisions §6–§12):**
- CR-w3-samples-3 and CR-w3-samples-4;
- CR-w3-web-2, option (a);
- the label narrowing;
- for #127: F1 fixed in W3; `bias_pct` stays a percentage; the 24/32 MB limits; Retail DC scoring, with its wording going to the W5 UX review;
- W4 carry-ins: the series cap at import (lead); danger/projection caching; `ensure_samples` taking an engine; the connected Retail example download.

**Lanes:**

| Lane | Session | Where it stood |
|---|---|---|
| forecast | `pantrypulse-forecast-*` | Pushed `6214126`, quick PASS. F1–F4 are done test-first in `12e5dbf`: `prepare` builds outside the lock, `publish` only INSERTs, and `discard` drops the build. Lane suites plus test_supervisor: 557 passed, 0 skipped. Next, from its status-file save point: re-time the lock at 50k before and after the fix, update the evidence JSON, S7 and the known limits, run the full gate, update the PR body, push |
| samples | `pantrypulse-samples-*` | Done; holding #128 at `e0e0414` |
| web | `pantrypulse-web-*` | Pushed `4e52aaa`, green. Done: CR-w3-web-2 (`60aa4e6`; CI sets PP_E2E_PRODUCTION only in the connected step), the label (`9d373cb`; on a failed list, legacy screens keep "Simulated network" next to "Network list unavailable", which the lead accepted), the example probe removed (`6c703f6`), and the A06 e2e for today's backend (`4e52aaa`). Full gate 8/8 at `75a2f71`; the 3 load failures passed on a clean rerun (42/42). Next: merge v1-local if it moved, full gate, `gh pr create`, report |

## Next steps, in order

1. Read lane messages (`ListAgents`; the lanes report to the orchestrator).
2. **#127:** when the lane reports its new head, run a verifier on the fix diff `e12fdc1..<head>`. Focus on F1: nothing heavy left in `publish`, `discard` on every unpublished end, and the new lock timing. Then ask Gabriel to merge after CI, and gate.
3. **Web PR:** run a verifier on the whole PR, covering CR-web-2, the label tests and the `mode` links. Ask Gabriel to merge after CI, and gate.
4. **#128:** after the web PR merges, the lane merges origin/v1-local. Check CI, ask Gabriel to merge, and gate.
5. Push `w3/decisions-3` with the BOARD W3 row, after Gabriel's OK.
6. Close W3 (BOARD), then W4 setup. Cleanup, with OK: the worktrees `lead-resume`, `w3-lead`, `w3-mig`, `w3-lead2`, `w3-gate`, `w3-probe`, `verify-121`, `verify-127` and `verify-128`.
7. `/vault-wrap-up`. The notes still to write are listed in the vault folder note.

## Standing rules

- Gabriel approves every push, PR, merge into v1-local, CR and wave start.
- No attribution lines in commits or PR bodies: no Co-Authored-By, no Claude-Session, and no "🤖 Generated with" line, even though Claude Code's own reminder asks for it.
- No force-push or rebase. Don't edit other worktrees. Never print a local login, key or env file.
- Never run two API suites on one test DB at the same time. Wait in-turn for each gate.
- Each status check includes progress bars for running work.

## Resuming

```bash
docker start pp-ci-postgres
cd ~/code/PantryPulse && claude --continue    # or: claude --resume 48f6075b-0b9e-43ba-a292-362a8778a215
```

Lanes: `cd ~/code/PantryPulse-<lane> && claude --continue` (lane = forecast, samples or web). Their sessions get new names; `ListAgents` shows them.

If this conversation is gone, start `claude` in `~/code/PantryPulse` and paste:

> You are the PantryPulse v1 orchestrator (lead). Read CLAUDE.md, docs/plans/v1/ORCHESTRATION.md, docs/plans/v1/wave-3.md and this runbook (`git -C ~/code/PantryPulse/.claude/worktrees/w3-docs show HEAD:docs/plans/v1/prompts/w3-resume.md`). Resume from "Next steps". Every status check includes progress bars for running work.
