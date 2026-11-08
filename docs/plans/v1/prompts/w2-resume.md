# Resuming W2-06 after the 2026-11-08 save point

W2 is lead-only (no lanes run). At the save point, W2-05 is done and W2-06 is partly landed. Decisions: [decisions/W2-06-change-requests.md](../decisions/W2-06-change-requests.md).

## Progress since the save point (2026-11-09)

- Steps 1–3 are done. v1-local is now `74efe6e`, which includes:
  - #116, the NUL fix (`fdb3a5e`);
  - #117, the partition plus the ATTACH foreign-key test (`5ff9add`; verifier R1–R6 PASS).

  The full gate passed 8/8 on `fdb3a5e` and again on `74efe6e`.
- The `CLAUDE.md` migration head is now `ppv1_0013`, on this branch (`da0f4a1`); it lands with the next docs PR.
- Step 4 is done:
  - #118 (A6/A7) merged as `46a1e4a`;
  - #119 (A2/A5) merged as `e7daa17`.

  The full gate passed 8/8 on each merge. The decisions file records how each fix landed.
- Step 5 is in progress. `wave-2.md` and the `BOARD.md` W2 row now record the W2-06 outcome, and `wave-3.md` gives the samples lane its `is_sample` interface. Still to do: the wave-end report, the W3 worktrees, the wave-start report, and Gabriel's approval of the W3 start.
- The lead's partition worktree `.claude/worktrees/lead-partition` (branch `w2/partition-integration`) is merged, so it can be removed with Gabriel's OK.

## State at the save point

**v1-local is `d07c94c`** (PR #115 merged). It holds:
- Lead CRs A1 (`forecast.v1` job status), A3 (the CR-w1-web-4 contract) and A4 (solver provenance), each independently verified over three review rounds.
- The W2-05/W2-06 plan docs and the decisions file.

PR #115's CI passed (`full` 11m12s, `verify`). On merged `d07c94c`, the local full gate passed 8/8 and e2e (judge journey) passed. Step 1 is done for `d07c94c`.

**Unpushed branches**, each in its own worktree:

| Branch | Head | Worktree | State |
|---|---|---|---|
| `w2/fix-nul-header` | `b0ec518` | `.claude/worktrees/agent-a5cd0b33c60f80115` | NUL-header fix plus supervisor resilience. Full API suite 1981 passed, 0 skipped. The first review (at `55033e4`) passed N2–N5; its findings were fixed in `b0ec518`. **Re-check of `b0ec518`: F1 and F2 RESOLVED, mutants M4–M8 caught, 1981 passed and 0 skipped, focused set clean 3×.** Ready for a PR with Gabriel's OK. |
| `w2/net-batches-partition` | `8258401` | `.claude/worktrees/agent-ade1db6e1f551b1fc` | `ppv1_0013`. Verified twice, with P1–P6 PASS and both findings RESOLVED; full suite 1960 passed, 0 skipped. Docker Desktop bench (6 CPU / 8 GiB): publish 1.49 s and 1.51 s, against 6.25 s and 4.91 s before. |
| `w2/w2-05-docs` | `4f41b7a` | main tree | Superseded: its commit is in #115. Delete it once Gabriel says so. |
| `w2/w2-06-resume` | (this file) | `.claude/worktrees/lead-resume` | This runbook. Push it with the next docs PR. |

**What each fix does:**
- **NUL fix (`b0ec518`):**
  - A NUL in any header cell is one MALFORMED row error with a "save as CSV UTF-8" fix.
  - With no `as_of_date`, every unreadable file is named. The "no valid history date" error appears only when the history file can be read.
  - An unexpected exception in `Supervisor._publish` ends the attempt FAILED with `PUBLICATION_STORAGE_FAILED`, discards it, and the supervisor keeps serving. `OwnershipLost` still re-raises. The log has the exception type, never its message.
  - Any exception from the commit call in `jobs.py` is `CommitUncertain` (reconciled, never discarded).
- **Partition (`8258401`):**
  - `net_batches` is LIST-partitioned by `dataset_version_id`. Publish ATTACHes a partition built in prepare.
  - No FK is pre-added to any staged partition (batches or history); ATTACH clones the parent's four FKs. A pre-added FK makes ATTACH drop the duplicate RI triggers, which takes AccessExclusive on the referenced table, so readers would block publish.
  - The builder added a `ppv1_immutable` trigger on `net_batches`. The lead keeps it: no path updates or deletes batches.
  - **Known limits:** an idle *writer* on `net_locations` (enrichment) still delays publish, as before. The organizations FK check now runs under the lock (about +0.4 s).

**Test databases** on `pp-ci-postgres` (127.0.0.1:55433). Never share one between concurrent runs.
- `pantrypulse_test`: lead gates.
- `pantrypulse_verify_test`: NUL fixer and its verifier.
- `pantrypulse_verify2_test`: partition builder and its verifier.
- `pantrypulse_solver_test`: the lead-CR verifier.

## Next steps, in order

1. **Gates on v1-local.** From the main tree on `origin/v1-local`, with `U=postgresql+psycopg://pantrypulse:isolated_test_only@127.0.0.1:55433/pantrypulse_test`, run:
   - `PP_TEST_DATABASE_URL=$U PP19_TEST_DATABASE_URL=$U PP19_TEST_SCHEMA_ISOLATION=1 node scripts/quality/run.cjs full`
   - then the same with `PLAYWRIGHT_PORT=3017` and `e2e`.

   Don't edit that tree while a gate runs: it fails with "source changed during checks".
2. **NUL fix.**
   - The verifier re-check of `b0ec518` (diff `55033e4..b0ec518`) is done, and every item is RESOLVED or PASS:
     - F1: UTF-16 with no BOM and no as-of date names every file.
     - F2: every commit-call exception reconciles. An exception before COMMIT ends FAILED with `PUBLICATION_COMMIT_LOST` and discards once.
     - The M4–M8 mutants are caught.
     - Suite: 1981 passed, 0 skipped.
     - The focused set ran clean three times; the `run_until` flake wasn't reproduced.
   - Known behaviour, not a defect: if `demand_history` has no dates and `donation_history` can't be read, only the donation error shows until the next upload.
   - Next: ask Gabriel to push and open a PR into v1-local, wait for CI, merge with `gh pr merge N --merge --match-head-commit <full sha>`, and run the full gate.
3. **Partition, after the NUL fix merges.**
   - In its worktree, run `git merge origin/v1-local` (no rebase).
   - Add a test: corrupt one staged row before ATTACH (a batch's location, product or organization; a demand row's product). ATTACH must raise ForeignKeyViolation, and the attempt must end FAILED with `PUBLICATION_STORAGE_FAILED`. Expect: staged tables discarded, nothing attached, the import phase `failed`, and the supervisor serving the next job. Before the NUL fix, that error escaped `Supervisor.tick()` and stopped the worker.
   - Run the full suite (0 skipped), get a verifier re-check, then ask for Gabriel's OK. Mention the trigger and the known limits.
   - Merge, run the gate, then set the migration head in `CLAUDE.md` to `ppv1_0013` (lead).
4. **Data fixes A2, A5, A6 and A7**, after steps 2 and 3. Dispatch one `integration-fixer` packet with the exact base SHA. Each change is test-first, then verified, then a PR with Gabriel's OK:
   - **A2:** the importer sets `networks.is_sample`. HTTP can't set it; the seed path does. Record the interface in the decisions file §2.
   - **A5:** a fractional `handling_units_per_unit` is a row error at import.
   - **A6:** the freeze drops lots already expired at `as_of_date` and lists an assumption.
   - **A7:** the source of a `Non_Exact` Census match says "unconfirmed address match".
5. **W2-06 Step 3:**
   - Write the W2-06 outcome in `wave-2.md` and the W2 row of `BOARD.md`.
   - Consolidate the gotchas.
   - Send the wave-end report.
   - Create the W3 worktrees at the base SHA.
   - Send the wave-start report. **Gabriel approves the W3 start.**
6. **Cleanup, each with Gabriel's OK:**
   - `docker compose -p pp-smoke down -v` (the smoke stack and only its data);
   - drop `pantrypulse_bench_test` on the `pantrypulse-postgres-1` stack;
   - `docker image rm` the `pantrypulse-api:bench-*` images;
   - remove the finished agents' worktrees after their branches merge.
7. **`/vault-wrap-up`.** Notes still to write:
   - the NUL-in-header worker crash;
   - that a quality gate invalidates itself when the source changes;
   - that the publication check must derive provenance, not trust it;
   - smoke-stack isolation (its own compose project and login folder).

## Standing rules

- Gabriel approves every push, PR, merge into v1-local, CR and wave start; approval for one doesn't cover the next.
- No Claude attribution lines in commits or PRs.
- No force-push or rebase.
- Don't edit other worktrees.
- Never print a local login or a key.

## Resuming the orchestrator

```bash
docker start pp-ci-postgres
cd ~/code/PantryPulse && claude --continue    # or claude --resume and pick the W2 orchestrator session
```

If that conversation is gone, start `claude` in `~/code/PantryPulse` and paste:

> You are the PantryPulse v1 orchestrator (lead). Read CLAUDE.md, docs/plans/v1/ORCHESTRATION.md, docs/plans/v1/wave-2.md, docs/plans/v1/decisions/W2-06-change-requests.md and this runbook (`git show w2/w2-06-resume:docs/plans/v1/prompts/w2-resume.md` until it is merged). Resume W2-06 from "Next steps" step 2: the gates on v1-local `d07c94c` passed. Start by bringing me the `w2/fix-nul-header` `b0ec518` PR for approval (it is verified). Bring me each PR for approval.
