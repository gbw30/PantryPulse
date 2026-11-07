# Resuming Wave 1 after the 2026-11-07 pause

Wave 1 paused on 2026-11-07. Lane heads at the pause: data `7a723f0`, solver `9014366`, web `ce7d7df`, all pushed and clean. Every lane's work was committed and pushed with a clean worktree, and each lane wrote a "Pause point" section in its status file (`docs/plans/v1/status/w1-<lane>.md` on its branch). The lead CRs are in PR #103 (`w1/cr-scenario-window-policy`), which is **not merged** yet. See the W1 row in `docs/pantrypulse/BOARD.md`.

## 0. Before opening any session (one WSL terminal)

```bash
docker start pp-ci-postgres          # shared test Postgres on 127.0.0.1:55433; no-op if already up
docker ps --filter name=pp-ci-postgres --format '{{.Names}} {{.Status}}'   # expect "Up … (healthy)"
cd ~/code/PantryPulse && git fetch origin
for l in data solver web; do git -C ~/code/PantryPulse-$l status --short; done   # expect no output
```

## 1. Orchestrator first (terminal 1)

```bash
cd ~/code/PantryPulse && claude --continue    # or: claude --resume, then pick the orchestrator session
```

If the old conversation is gone, start `claude` there and paste:

> You are the PantryPulse v1 orchestrator (lead). Read CLAUDE.md, docs/plans/v1/ORCHESTRATION.md, the W1 row of docs/pantrypulse/BOARD.md and docs/plans/v1/prompts/w1-resume.md. Resume Wave 1 from the pause point:
> 1. Rerun `node scripts/quality/run.cjs full` on PR #103's head, with the test DB env set and no other test runs in parallel.
> 2. Have the `verifier` re-check the fixes in `4366141`. Gabriel approved merging #103 once CI and the verifier are clean.
> 3. Merge with `gh pr merge 103 --merge`.
> 4. Tell each lane to merge origin/v1-local (no rebase).
> 5. Bring me the data lane's gate-timeout question.
> 6. Bring me the solver's Retail bench finding: 123 of the 209 at-risk products (150 in USD) get a capacity share too small to move one unit under the advance split. Ask whether to raise a localized-weight option. Also review its EGP rule that skips, with a label, any product with fewer than two pantries that have demand.

Wait until the orchestrator reports PR #103 merged before you resume the data and solver lanes; the web lane can start right away.

## 2. Lanes (one terminal each)

The preferred way keeps each lane's full context:

```bash
cd ~/code/PantryPulse-data   && claude --continue
cd ~/code/PantryPulse-solver && claude --continue
cd ~/code/PantryPulse-web    && claude --continue
```

Then paste the lane's prompt below. If its old conversation is gone, start plain `claude` in that worktree, paste the lane's original prompt from `docs/plans/v1/prompts/w1-<lane>.md` first, then the resume prompt. **The original prompt's base-SHA check is replaced by the resume prompt**, because the lane branches have already merged v1-local or will.

**w1-data** (after #103 is merged):

> Resume lane w1-data from your status file's "Pause point".
> 1. Run `git fetch origin && git merge origin/v1-local` (no rebase). Run `set -a; . ./.env.lane; set +a`.
> 2. Then build, test-first:
>    - the import.v1 prepare/discard/publish path (staged tables keyed by attempt_id);
>    - the routes-google.v1 job with `child_secrets=("google_maps_api_key",)`;
>    - W1-D05 and W1-D09.
> 3. Before your PR: run the quick and full gates and report exact counts. Name any PP19 skips; don't count them as validated. Open the PR only with Gabriel's approval.

**w1-solver** (after #103 is merged):

> Resume lane w1-solver from your status file's "Pause point".
> 1. Run `git fetch origin && git merge origin/v1-local` (no rebase). Run `set -a; . ./.env.lane; set +a`.
> 2. Finish the `wip` commit `3b60263` first: rename `tests/optimization/pending_cr1_pantry_methods.py` back to a collected `test_*.py` name and run it against the real CR-1 schema. It has only run against a local stand-in so far.
>    Then run the Pantry bench and build the Pantry halves of S02/S04/S05/S07:
>    - use planning_days and the policy from or-input-v3;
>    - comparison_id = job_id;
>    - pre-publication reads return 404 COMPARISON_NOT_FOUND.
> 3. Before your PR: run the quick and full gates and report exact counts.

**w1-web** (can start right away):

> Resume lane w1-web from your status file's "Pause point".
> 1. Rerun the verifier on your head, then fix its should-fix findings test-first, including the RangeError on an impossible demand_history date and the path-traversal residual.
> 2. Rerun the gates. Open the PR into v1-local only with Gabriel's approval.
> 3. After the orchestrator says #103 merged, run `git merge origin/v1-local` (no rebase). Then:
>    - wire LocationList and add the GET to the proxy allowlist;
>    - build the inspector against LocationProjection on mocks;
>    - add the Pantry window picker and policy to scenario creation.

Rules for every lane: no Claude-Session or Co-Authored-By lines; never force-push or rebase pushed branches; Gabriel approves each push to the PR, each merge and each change request.
