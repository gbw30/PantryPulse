# Resuming W3 (save point 2026-11-09, evening)

W3 started 2026-11-09 from base `0a49593`. The lanes run as separate CLI sessions. Decisions: [decisions/W3-change-requests.md](../decisions/W3-change-requests.md), which lands with PR #122.

## State at the save point

**v1-local:** `5c5fbe7`. PR #122 merged after green CI (`verify` and `full`; the no-egress connected step passed on GitHub's runner). **The full gate hasn't run on `5c5fbe7` yet.**

**Lead PRs and branches:**

| Item | Head | State | Gabriel's approval |
|---|---|---|---|
| PR #122 `w3/lead-crs` (worktree `.claude/worktrees/w3-lead`) | `5cb3c76` | **Merged** as `5c5fbe7`, CI green. The samples and web lanes were told to merge `origin/v1-local` | Done |
| `w3/ppv1-0014-backtest` (worktree `.claude/worktrees/w3-mig`), local only | `a3c3b59` + this runbook | `ppv1_0014`: `forecast_runs.backtest` JSONB, NULL or an object. The tests failed first. Full API suite: 2038 passed, 0 skipped. Not yet independently verified | Option B approved; **push and PR not yet approved** |

PR #122 holds:
- CR-w3-samples-1: sample rates read "sample values";
- CR-w3-samples-2: template CSVs keep LF;
- CR-w3-web-1: the CI connected step runs the backend with no egress, using `scripts/quality/netns-bridge.py`;
- the W3 decisions file, the BOARD W2/W3 rows, and the W4-02 E-1 carry-in.

**Lane PRs:**
- PR #121, `lane/w3-samples` at `51b65aa`: W3-P01…P04 done. CI `verify` passed; `full` was running.
  - The verifier (W4-01 Step 1) found no High or Medium issues. P01–P03 PASS; P04 PASS with 3 Low findings.
  - Full API suite 2054 passed, 0 skipped. V1-A02 and V1-A06 are UNVERIFIED at service level; they need compose and e2e.
  - The 3 Low findings went to the lane, which fixes them test-first and pushes a new head:
    - concurrent stale seeds add a duplicate version (needs a lock);
    - the egress test misses a call swallowed by `except Exception`;
    - two mutants survived (`is_sample` dropped from the lookup; ASC tie-break).

**Lanes:**

| Lane | Session | Where it stood |
|---|---|---|
| forecast | `pantrypulse-forecast-*` | Pushed `2339048`. F01, F02, F04, F05 and F06 done. F05: danger and projection on `project_v3`, tests/danger 10 passed, 0 skipped, 7/7 mutants killed. F06: 50k series in 12.5 s of 300 s, 1.1 GB peak. Only F03's `get_backtest` is left; it waits for `ppv1_0014`. **Check at review:** `forecast.v1` `max_input_bytes` raised from 16 MB to 24 MB (worst case 20.6 MB); at 50k series the output is built in the queue lock (4.2 s plus the INSERT); `get_danger` recomputes about 4 s per request |
| samples | `pantrypulse-samples-*` | 4/4 tasks done, PR #121 in review. Waits for #122 to merge, then `git merge origin/v1-local` |
| web | `pantrypulse-web-*` | W01, W02 done, pushed `ee2ae4c`: connected e2e 192 passed, 0 skipped, no egress, fixture forecast run per E-1. Doing the approved follow-ups (hide the legacy Scenario builder when a v1 network is chosen; a shared sign-in helper that clears the password on failure), then W03 |

**Open for Gabriel:**
- **CR-w3-samples-3:** Retail examples need a mode on the example route.
- **CR-w3-samples-4:** the seed uses the UTC `date.today()`, so from 20:00 to 24:00 New York time it dates samples a day ahead. Lead file `scripts/local_bootstrap.py`. Part (b): run the seed outside the login transaction.
- **Merge order:** W4 says forecast → samples → web, but samples is ready first. Ask whether #121 may merge before forecast.

## Next steps, in order

1. **Full gate on v1-local `5c5fbe7`.** Use the main tree, detached at `origin/v1-local`:
   `U=postgresql+psycopg://pantrypulse:isolated_test_only@127.0.0.1:55433/pantrypulse_test; PP_TEST_DATABASE_URL=$U PP19_TEST_DATABASE_URL=$U PP19_TEST_SCHEMA_ISOLATION=1 node scripts/quality/run.cjs full`.
   Then check that the web lane switched `stack-up.sh` to `scripts/quality/netns-bridge.py`.
2. **PR #121:** when the lane pushes its fixes, get a verifier re-check of the fix diff `51b65aa..<new head>`, using worktree `verify-121` and DB `pantrypulse_verify_test`. Then ask Gabriel for the merge, after CI, and run the full gate.
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
