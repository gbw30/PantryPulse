# Wave 2 — Integrate wave 1 (orchestrator)

**Base:** `v1-local` after W0. **Branch:** `w2/integration` for cross-lane journey tests. Lane PRs merge directly into `v1-local`. **Mode:** orchestrator; `verifier`, `adversarial-reviewer` and `integration-fixer` run in-session (A). **Order:** `w1-data` → `w1-solver` → `w1-web` ([ORCHESTRATION.md §6](ORCHESTRATION.md#6-merge-policy)).

### W2-01: Review each lane PR · S per lane · depends on: each lane's PR · V1-A22

- [ ] **Step 1:** for each PR, give the `verifier` the requirements (its wave-1 task list and acceptance IDs), the immutable diff and the tests, before any lane rationale. The verifier returns PASS/FAIL/UNVERIFIED per acceptance ID.
- [ ] **Step 2:** run `/code-review` on the PR. Send findings to the lane as a PR comment. The lane fixes them on its branch, or argues back with evidence.
- [ ] **Step 3:** CI on the PR is green, and the backend job reports 0 skipped (`require-test-evidence.py`).

### W2-02: Merge `w1-data` · S · depends on: W2-01 (data)

- [ ] **Step 1:** "PR ready" report to Gabriel. Wait for approval, then `gh pr merge <n> --merge`.
- [ ] **Step 2:** on `v1-local`, run `node scripts/quality/run.cjs full`. Expected: PASS, 0 skipped.

### W2-03: Merge `w1-solver` · S · depends on: W2-02

- [ ] **Step 1:** the lane (or the orchestrator, in the lane worktree) runs `git merge origin/v1-local`, re-runs `tests/optimization` and `run.cjs quick`, and pushes.
- [ ] **Step 2:** Gabriel approves, then merge. Run `run.cjs full` on `v1-local`.

### W2-04: Merge `w1-web` · S · depends on: W2-03

- [ ] **Step 1:** the lane merges `origin/v1-local`, re-runs `test:unit` and its e2e specs, and pushes.
- [ ] **Step 2:** Gabriel approves, then merge. Run `run.cjs full` and `run.cjs e2e`. The connected run uses `PP_RUN_CONNECTED=1`; in W2 the existing V5 journey must stay green (V1-A22).

### W2-05: Backend v1 journey test · M · depends on: W2-04 · V1-A07, A10, A14, A15, A16, A23 (backend)

**Files:** create `apps/api/tests/integration/test_v1_backend_journey.py` (orchestrator-owned).

- [ ] **Step 1:** write the failing test `test_import_to_export_pantry_and_retail`. It imports the W1-D09 mini network (Pantry), plus a 1 DC + 3 stores Retail twin, then:
  - inserts a fixture forecast run;
  - builds the scenario;
  - runs `or-comparison.v3` (Pantry: 5 methods × 2 transfer modes; Retail: 3 methods × units/USD);
  - checks that every published result is verified;
  - fetches the actions;
  - exports the CSV;
  - asserts the stock tables are unchanged.
- [ ] **Step 2:** run it. Each failure goes to an `integration-fixer` packet: the minimal failing case, the owning wave-1 paths, and the base SHA. Its fix lands through a small PR with Gabriel's OK.
- [ ] **Step 3:** PASS. Commit on `w2/integration`, open the PR, and merge with Gabriel's OK.

### W2-06: Adversarial pass and change-request decisions · S–M · depends on: W2-05

- [ ] **Step 1:** dispatch `adversarial-reviewer` on the `v1-local` head with the V1-SPEC §6 behaviors. Seed cases:
  - duplicate keys after trimming;
  - a BOM file;
  - an import during an import;
  - a Census outage;
  - a key in an error;
  - every product at zero stock;
  - every route disabled;
  - USD with one price missing.
  Each reproduced failure becomes a fix packet or a wave-3 task.
- [ ] **Step 2:** decide with Gabriel every open CR from the wave-1 status files. Land the approved ones (contract, schema) on `v1-local`, and regenerate the contract.
- [ ] **Step 3:** light re-plan. Update `wave-3.md` and `prompts/w3-*.md` with any interface change, then send the wave-end report, consolidate the lanes' "Gotchas", set up the W3 worktrees and send the wave-start report. **Gabriel approves the wave 3 start.**
