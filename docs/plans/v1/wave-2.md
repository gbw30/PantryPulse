# Wave 2 — Integrate wave 1 (orchestrator)

**Base:** `v1-local` after W0. **Branch:** `w2/integration` for cross-lane journey tests. Lane PRs merge directly into `v1-local`. **Mode:** orchestrator; `verifier`, `adversarial-reviewer` and `integration-fixer` run in-session (A). **Order:** `w1-data` → `w1-solver` → `w1-web` ([ORCHESTRATION.md §6](ORCHESTRATION.md#6-merge-policy)).

### W2-01: Review each lane PR · S per lane · depends on: each lane's PR · V1-A22

- [ ] **Step 1:** for each PR, give the `verifier` the requirements (its wave-1 task list and acceptance IDs), the immutable diff and the tests, before any lane rationale. The verifier returns PASS/FAIL/UNVERIFIED per acceptance ID.
- [ ] **Step 2:** run `/code-review` on the PR. Send findings to the lane as a PR comment. The lane fixes them on its branch, or argues back with evidence.
- [ ] **Step 3:** CI on the PR is green, and the backend job reports 0 skipped (`require-test-evidence.py`).

### W2-02: Merge `w1-data` · S · depends on: W2-01 (data)

- [ ] **Step 1:** "PR ready" report to Gabriel. Wait for approval, then `gh pr merge <n> --merge --match-head-commit <reviewed sha>`.
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
  W1 carry-in (2026-11-07):
  - **The Retail twin doesn't exist yet**, so build it as a fixture next to `tests/networks/fixtures/mini-network`.
  - Insert the forecast run the way `tests/networks/test_build_scenario.py` does. `POST /networks/{id}/forecasts` is 501 until W3.
  - Every committed import queues `enrichment.v1` (follow-up hook) and `max_queued` is 2, so drain those jobs before submitting comparisons.
  - Every mini-network location has coordinates, so A10 needs one extra location without coordinates plus a recorded geocoder response.
- [ ] **Step 2:** run it. Each failure goes to an `integration-fixer` packet: the minimal failing case, the owning wave-1 paths, and the base SHA. Its fix lands through a small PR with Gabriel's OK.
- [ ] **Step 3:** PASS. Commit on `w2/integration`, open the PR, and merge with Gabriel's OK.
- [ ] **Step 4: live smoke of the W1 screens** (moved here from W1 by Gabriel, 2026-11-07).
  - Run the merged stack with a worker (commit answers 503 without one), with the web on a free `PLAYWRIGHT_PORT`/port.
  - Import the mini network through the UI. Every location has coordinates, so there is no outbound call.
  - Use a fixture forecast run through `?forecast_run_id=`.
  - Walk through the comparison (both modes), Decisions, export and print.
  - Danger, projection and forecasts are 501 until W3; check that they render as honest errors.
  - Signing in uses the generated local login, which needs Gabriel's OK. Never print it.

**W2-05 outcome (2026-11-08, done):**
- **Journey test:** `test_v1_backend_journey.py` runs as two tests, Pantry and Retail, rather than the single test named above. Merged as #113 (`a00c4d4`).
  - The Pantry A10 case uses three pantries without coordinates, answered by the recorded geocoder: one exact match (stored as known), one `Non_Exact` match (stored, listed for review), and one `No_Match`. The `No_Match` blocks the freeze until the user excludes it.
  - The verifier's mutation probes all failed the test. Three mutants survived the first version: inbound counted twice in the projection, a blank export effect, and an import horizon one day longer. The hardened test kills all three.
  - The full gate passed 8/8 on `a00c4d4`.
- **Live smoke:** run on a separate compose project at `5204265`, web on port 3018, signed in with that project's own generated login.
  - Passed: the UI import, the comparison in both transfer modes with all 5 methods verified, Decisions, the CSV export with hash and note, and print.
  - Danger's 501 shows "unavailable (not implemented)".
  - The comparison, Decisions and print screens raised no API or console errors.
  - New items for W2-06:
    - the header shows "Inventory · <today>" instead of the snapshot date;
    - the product picker stays on "Loading products…";
    - "simulated network" wording appears beyond the pill: the Live chip, the Atlas subtitle and the session footer.
- **Benchmark (W1 carry-in):** Docker Desktop, worker limits 6 CPU / 8 GiB, at `5204265`.
  - Publish held the lock for 6.25 s and 4.91 s, above 3.5 s. Gabriel approved the `net_batches` partition for W2-06.
  - The script's documented Docker command crashed with `IndexError`. Fixed in #114 (`9f8c7a3`); the full gate passed 8/8 there.

### W2-06: Adversarial pass and change-request decisions · S–M · depends on: W2-05

- [x] **Step 1:** dispatch `adversarial-reviewer` on the `v1-local` head with the V1-SPEC §6 behaviors. Seed cases:
  - duplicate keys after trimming;
  - a BOM file;
  - an import during an import;
  - a Census outage;
  - a key in an error;
  - every product at zero stock;
  - every route disabled;
  - USD with one price missing.
  Each reproduced failure becomes a fix packet or a wave-3 task.
- [x] **Step 2:** decide with Gabriel every open CR from the wave-1 status files. Land the approved ones (contract, schema) on `v1-local`, and regenerate the contract.
  - Also open from W1 (BOARD W2 row; lane status files; the W2 prep review):
    - **Must land before W3:** `forecast.v1` in `V1_NETWORK_JOBS` (lead CR); the importer sets `networks.is_sample` (data CR).
    - **Contracts:**
      - an external batch id field for hashed frozen batch ids;
      - cancel and retry for v1 jobs;
      - an abort route plus cleanup of abandoned import runs and files (W0-08 §2, §4).
    - **Enrichment:**
      - say why it didn't start;
      - given coordinates get no tract or ACS rates (reverse-geocode, or keep it and say so in the column guide);
      - should the automatic Census lookup after an import be labeled explicitly (V1-SPEC §4 "explicit, labeled")?
      - enrichment updates the published version (by design; record it).
    - **Data:**
      - a fractional `handling_units_per_unit` is accepted at import but blocks the freeze (reject it at import?);
      - batches already expired at `as_of_date` are frozen unfiltered (solver S3);
      - the staging sweep with more than one worker;
      - progress has no live row count (V1-A09).
    - **Solver:** an independent FEFO check (S1), record seed, worker count and OR-Tools version (S2), the F2 residual, publish retry backoff, and one tenancy helper.
    - **Web and UX:**
      - the legacy fixture atlas shown above an imported network's ranking (UX critic);
      - names not yet wired in trust and decisions;
      - the "Simulated network" pill;
      - sample rates read as "manual" while V1-SPEC §8 wants a "sample values" label.
    - **Projection:** should W3-F04/F05 reuse `project_v3`?
  - Carried from W1 (decisions §7 of `decisions/W0-08-scenario-and-import.md`):
    - define CR-w1-web-4 (forecast series read and per-location accuracy) with the D09 forecast-run interface;
    - run `bench_import.py` on Gabriel's Windows Docker stack. If the publish lock exceeds 3.5 s, land the `net_batches` version partition.
- **Outcome of Steps 1–2 (2026-11-08 to 11-09).** Decisions are in [decisions/W2-06-change-requests.md](decisions/W2-06-change-requests.md). Each PR below was independently verified, merged with `--match-head-commit` after CI, and followed by a full gate run on the merged v1-local.
  - **Adversarial pass:** all 8 seed behaviours held. The reviewer also found that a NUL byte in a CSV header crashed the worker. Fixed in **#116** (`fdb3a5e`):
    - the NUL is now a row error;
    - an unexpected error at publish fails only that attempt, with `PUBLICATION_STORAGE_FAILED`;
    - any error from the COMMIT itself is reconciled, never discarded.
  - **Lead CRs, #115** (`d07c94c`):
    - A1: `forecast.v1` job status;
    - A3: the CR-w1-web-4 contract (`NetworkForecastRun`, `BacktestResult.locations`, one entry per location and unit);
    - A4: solver provenance, derived again at publication.
  - **`net_batches` partition, #117** (`74efe6e`, `ppv1_0013`):
    - Publish on Docker Desktop dropped from 6.25 s to 1.49 s.
    - No foreign key is added to a staged partition before it is attached, so readers of the referenced tables no longer block ATTACH.
    - A refused row at ATTACH fails the import and the worker keeps running.
  - **Data fixes:**
    - **#118** (`46a1e4a`), A6 and A7: lots with expiry ≤ as-of are left out of the freeze and listed per product (Gabriel, 2026-11-09). A Census `Non_Exact` match is labelled "unconfirmed address match".
    - **#119** (`e7daa17`), A2 and A5: only an internal import can create a sample network. A handling-units value the freeze would refuse (a fraction, or over 1000) is a row error.
  - **Deferred** (decisions §3–§5): the B items go to the W3 lanes as carry-ins; the C items to W4, now including the Non_Exact review-list retry gap; the D items to W5 known limits.
- [ ] **Step 3:** light re-plan. Update `wave-3.md` and `prompts/w3-*.md` with any interface change, then send the wave-end report, consolidate the lanes' "Gotchas", set up the W3 worktrees and send the wave-start report. **Gabriel approves the wave 3 start.**
