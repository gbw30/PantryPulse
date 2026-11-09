# Wave 4 — Integrate wave 3 (orchestrator)

**Base:** `v1-local` after W2. **Order:** `w3-forecast` → `w3-samples` → `w3-web`. **Mode:** orchestrator; `verifier`, `adversarial-reviewer`, `ux-critic` and `integration-fixer` run in-session (A). The merge mechanics are the same as W2-01…W2-04 ([wave-2.md](wave-2.md)).

### W4-01: Review and merge the three lane PRs · S each · depends on: each lane's PR · V1-A22

- [ ] **Step 1:** for each PR in order:
  1. The verifier gets requirements + diff + tests first, and uses the `verify-forecast` skill for `w3-forecast`.
  2. Run `/code-review`.
  3. CI is green with 0 skipped.
  4. The lane merges `origin/v1-local`.
  5. Gabriel approves, then `gh pr merge --merge`.
  6. Run `run.cjs full` on `v1-local`.

### W4-02: The whole v1 journey, connected · M · depends on: W4-01 · V1-A05, A06, A12, A13, A14, A15, A16, A23

**Files:** create `apps/web/tests/e2e/v1-full-journey.spec.ts`. In W4 the orchestrator owns it; `w5-polish` owns it in W5.

- [ ] **Step 1:** write the failing connected tests:
  - `@V1-A05 both samples present and labeled after first start`.
  - `@V1-A06 example downloads equal data/templates/examples`.
  - `@V1-A12 forecast with backtest or "accuracy not evaluated"`.
  - `@V1-A13 atlas ranking equals GET /danger and the table alternative`, and selecting a row opens the live site inspector (`GET /networks/{id}/projection`, W0-08 §6).
  - `@V1-A14 @V1-A15 @V1-A16 compare → decisions → export on both samples`.
  - `@V1-A23 donation forecast shown "not confirmed", danger unchanged with and without it`.
  - W3 carry-in (E-1, 2026-11-09): the web lane's connected Pantry and Retail journeys use a fixture forecast run through `?forecast_run_id=`. Switch them to a real `forecast.v1` run from W3-F03 and remove the stopgap ([decisions/W3-change-requests.md](decisions/W3-change-requests.md) §4).
- [ ] **Step 2:** run with `PP_RUN_CONNECTED=1 PP_E2E_PRODUCTION=1 node scripts/quality/run.cjs e2e`. Send each failure to an `integration-fixer` packet.
- [ ] **Step 3:** PASS, 0 skipped. Commit on `w4/integration`, open the PR, and merge with Gabriel's OK.

### W2-06 deferrals (schedule at W4-02/W4-03)

Hardening items decided at W2-06 ([decisions/W2-06-change-requests.md](decisions/W2-06-change-requests.md) §4). Each lands test-first through a small PR with Gabriel's OK:
- Solver S1: an independent FEFO check in the verifier.
- The F2 residual.
- One tenancy helper.
- Cancel and retry for v1 jobs.
- Enrichment says why it didn't start.
- Reverse geocoding when coordinates are given.

### W4-03: Review gates · M · depends on: W4-02 · V1-A20, V1-A13

- [ ] **Step 1:** `adversarial-reviewer` on the `v1-local` head. Seed cases:
  - a series with only blank days;
  - inbound on the last horizon day;
  - a sample re-seed on day 8;
  - a backtest with a zero denominator;
  - a danger tie;
  - a Retail store with all stock expiring tomorrow.
- [ ] **Step 2:** `ux-critic`. Give it screenshots at 1440×900, 1280×720 and 390×844 of the import, atlas ranking, forecast trust, comparison and decisions screens, plus a keyboard walkthrough and a reduced-motion capture, all taken by the orchestrator. Its findings (at most five) become W5 polish tasks.
- [ ] **Step 3:** run `research-claims-check` on all new UI copy and docs that mention the research, fairness, forecasts or impact. Fix through small PRs.

### W4-04: Re-plan and launch W5 · S · depends on: W4-03

- [ ] **Step 1:** decide the open CRs with Gabriel. Add the ux-critic findings to `wave-5.md` as W5-UI02 items, then update `prompts/w5-*.md`.
- [ ] **Step 2:** confirm that `/jmo-workflow:better-ui` and `/jmo-workflow:animate` load in a new session; `stack-web@devkit` was installed 2026-11-04. If they don't, tell Gabriel before W5 starts.
- [ ] **Step 3:** wave-end report, consolidate the lanes' "Gotchas", W5 worktrees, then the wave-start report. **Gabriel approves the wave 5 start.**
