# Resuming W3 (save point 2026-11-09, evening)

W3 started 2026-11-09 from base `0a49593`. The lanes run as separate CLI sessions. Decisions: [decisions/W3-change-requests.md](../decisions/W3-change-requests.md), which lands with PR #122.

## State at the save point

**v1-local:** `0a49593` (unchanged since the W3 start).

**Lead PRs and branches:**

| Item | Head | State | Gabriel's approval |
|---|---|---|---|
| PR #122 `w3/lead-crs` (worktree `.claude/worktrees/w3-lead`) | `5cb3c761f40bf4e990aa1ee95088eafe0603d59f` | CI `verify` passed; `full` was running. Verifier: code PASS (full API suite 2032 passed, 0 skipped); follow-ups fixed in `5cb3c76` | Push + merge after CI |
| `w3/ppv1-0014-backtest` (worktree `.claude/worktrees/w3-mig`), local only | `a3c3b59` + this runbook | `ppv1_0014`: `forecast_runs.backtest` JSONB, NULL or an object. The tests failed first. Full API suite: 2038 passed, 0 skipped. Not yet independently verified | Option B approved; **push and PR not yet approved** |

PR #122 holds:
- CR-w3-samples-1: sample rates read "sample values";
- CR-w3-samples-2: template CSVs keep LF;
- CR-w3-web-1: the CI connected step runs the backend with no egress, using `scripts/quality/netns-bridge.py`;
- the W3 decisions file, the BOARD W2/W3 rows, and the W4-02 E-1 carry-in.

**Lane PRs:**
- PR #121, `lane/w3-samples` at `51b65aa`: W3-P01…P04 done. CI `verify` passed; `full` was running. The independent verifier (W4-01 Step 1) was mid-review. The lane holds the head and pushes only review fixes.

**Lanes:**

| Lane | Session | Where it stood |
|---|---|---|
| forecast | `pantrypulse-forecast-*` | F01, F02 done; F05 green locally. F03's `get_backtest` waits for `ppv1_0014`; then F04/F06 |
| samples | `pantrypulse-samples-*` | 4/4 tasks done, PR #121 in review. Waits for #122 to merge, then `git merge origin/v1-local` |
| web | `pantrypulse-web-*` | W01, W02 done, pushed `ee2ae4c`: connected e2e 192 passed, 0 skipped, no egress, fixture forecast run per E-1. Doing the approved follow-ups (hide the legacy Scenario builder when a v1 network is chosen; a shared sign-in helper that clears the password on failure), then W03 |

**Open for Gabriel:**
- **CR-w3-samples-3:** Retail examples need a mode on the example route.
- **CR-w3-samples-4:** the seed uses the UTC `date.today()`, so from 20:00 to 24:00 New York time it dates samples a day ahead. Lead file `scripts/local_bootstrap.py`. Part (b): run the seed outside the login transaction.
- **Merge order:** W4 says forecast → samples → web, but samples is ready first. Ask whether #121 may merge before forecast.

## Next steps, in order

1. **PR #122:** `gh pr checks 122`. If green, run `gh pr merge 122 --merge --match-head-commit 5cb3c761f40bf4e990aa1ee95088eafe0603d59f`. Then run the full gate on the merged v1-local (main tree, detached at `origin/v1-local`):
   `U=postgresql+psycopg://pantrypulse:isolated_test_only@127.0.0.1:55433/pantrypulse_test; PP_TEST_DATABASE_URL=$U PP19_TEST_DATABASE_URL=$U PP19_TEST_SCHEMA_ISOLATION=1 node scripts/quality/run.cjs full`.
   If the connected step failed in CI, read `artifacts/bridge-*.log`, `api.log` and `worker.log` in the run's evidence upload. The `sysctl` on ubuntu-24.04 was the unverified part.
   After the merge, tell samples to merge `origin/v1-local`, and tell web to merge and point `stack-up.sh` at `scripts/quality/netns-bridge.py`.
2. **PR #121:** get the verifier's report. If the session that ran it is gone, dispatch a new `verifier` with the same packet: head `51b65aa`, base `0a49593`, worktree `.claude/worktrees/verify-121`, DB `pantrypulse_verify_test`, V1-A02/A05/A06 and W3-P01…P04. Send findings to the lane. Merge only with Gabriel's OK and after CI, then run the full gate.
3. **`ppv1_0014`:** first, in `w3-mig`, run `git merge origin/v1-local` (after #122) and set decisions §5 to "approved B, landed in #N". Then dispatch a verifier, ask Gabriel for push + PR, merge after CI, run the gate, and tell forecast to merge `origin/v1-local`.
4. Decide CR-w3-samples-3, CR-w3-samples-4 and the merge order with Gabriel.
5. Cleanup, with OK: worktrees `lead-resume` (merged), and `w3-lead` and `w3-mig` after merge; `verify-121` after review.
6. `/vault-wrap-up`. The notes still to write are listed in the vault folder note.

## Standing rules

- Gabriel approves every push, PR, merge into v1-local, CR and wave start.
- No Claude attribution lines in commits or PRs.
- No force-push or rebase.
- Don't edit other worktrees.
- Never print a local login, key or env file.
- Each status check includes progress bars for running work.

## Resuming

```bash
docker start pp-ci-postgres
cd ~/code/PantryPulse && claude --continue    # or claude --resume and pick this orchestrator session
```

Lanes: `cd ~/code/PantryPulse-<lane> && claude --continue`. Their sessions get new names; `ListAgents` shows them.

If this conversation is gone, start `claude` in `~/code/PantryPulse` and paste:

> You are the PantryPulse v1 orchestrator (lead). Read CLAUDE.md, docs/plans/v1/ORCHESTRATION.md, docs/plans/v1/wave-3.md and this runbook (`git -C ~/code/PantryPulse/.claude/worktrees/w3-mig show HEAD:docs/plans/v1/prompts/w3-resume.md`). Resume from "Next steps". Every status check includes progress bars for running work.
