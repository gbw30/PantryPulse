# W4 decisions: the v1 code review and its fixes

**Status:** decided by Gabriel, 2026-11-10. **Applies to:** W4 and W5.

**Base and order:** W4 started at v1-local `3e9abcc` with the order (1) confirmed code-review fixes, (2) the W3 §11 carry-ins, (3) W4-02, (4) the W2-06 hardening items, (5) W4-03/04. W4-01 (merging the three W3 lane PRs) counts as done in W3: each lane PR had an independent verifier, CI with 0 skipped, and a full gate 8/8 on `caa5010`. The code review below covers W4-01's `/code-review` step.

## 1. The review and how it was checked

Gabriel ran `/code-review` on all of v1 (`main...HEAD`, 473 files, production code). It returned 15 findings and ran nothing. Read-only verifiers checked every finding against `3e9abcc`, by a run where cheap and by an end-to-end code trace otherwise.

| # | Finding | Verdict | Decision |
|---|---|---|---|
| 1 | The import wizard polls forever when a commit gets a 5xx and the run stays `uploading` with no job | CONFIRMED (trace) | Fixed in #135 (§2) |
| 2 | A re-import commit and a comparison publish wait on each other across two connections (FK `FOR KEY SHARE` vs `FOR UPDATE`) | CONFIRMED (lock-level run) | Fixed in #134 (§3) |
| 3 | `_sweep` drops every staged table that isn't its own, and the sample seed calls it directly | PLAUSIBLE | Check a compose re-up in W4-02, then decide |
| 4 | An exception from a publisher's `validate` kills the worker process | CONFIRMED (run) | Fixed in #134 (§3) |
| 5 | `publish_staged` doesn't check the run's phase or job | REFUTED (queue fencing, one job per run, `UNIQUE(import_run_id)`) | Phase check goes to the hardening batch |
| 6 | The async upload handler does sync DB work on the event loop | PLAUSIBLE (body is streamed) | Hardening batch |
| 7 | Print breaks at about 650 selected actions (URL over 16 KB) and export at 2,621 (body over 64 KiB) | PLAUSIBLE (sizes measured) | Fixed in #133 and #135 (§2, §3) |
| 8 | Decisions and print show a generic error instead of the "no verified plan" reason | CONFIRMED (trace) | Fixed in #135 (§2) |
| 9 | A Census "Match" row without coordinates reads as success; a malformed one crashes the step | CONFIRMED (run) | Hardening batch |
| 10 | Two tabs can start two enrichment jobs (no dedupe on retry) | CONFIRMED (trace) | Hardening batch |
| 11 | A non-positive solver time limit reaches CP-SAT | REFUTED (caught before CP-SAT as `METHOD_TIME_LIMIT`) | None |
| 12 | One ACS rate is never filled when the CSV gives the other | REFUTED (CSV rates are manual overrides) | None |
| 13 | Staging's per-statement timeout has no total limit; a timeout reads as `PREPARE_FAILED` | CONFIRMED (trace) | Hardening batch |
| 14 | The ACS table loads inside the queue lock | CONFIRMED, informational (once per process, 0.07 s) | None |
| 15 | Dead `loc in sublots` guard in `product_model.py` | CONFIRMED, no effect today | Hardening batch (delete it) |

## 2. Web fixes (#135, web lane, `8fd6d22`)

- **#1:** if a commit fails with a 5xx or no answer and the run reads `uploading` with no job, polling stops and the page says the import didn't start, with Retry (commits the same run again) and "Start a new import".
- **#8:** the comparison loads first. An unverified method shows its "no verified plan" state with solver status and failure reason, including when the actions route answers 409. `METHOD_NOT_IN_COMPARISON` has its own message. The @V1-A16 e2e tests now mock the real 409.
- **#7, web half:** the print link carries no action ids. One selection is saved in localStorage with its network, comparison and method; print uses it only when all three match, and a failed save removes it. The proxy body cap is 1 MiB for the plan export path only (anchored match); every other path keeps its cap.
- **Verification:** two independent verifiers (PASS WITH NOTES on `555c188` and `8fd6d22`). CI green with 0 skipped.

## 3. Lead fixes (#133 `fa560d6`, #134 `e739f68`)

- **#7, API half (#133):** `ExportRequest.action_ids` is capped at `EXPORT_MAX_ACTIONS = 40_000`. 40,000 real ids are 1,000,016 bytes as the browser sends them, under the 1 MiB export cap.
- **#4 (#134):** any exception other than `PublicationRejected` from `validate` is logged as `PUBLICATION_VALIDATE_FAILED` with its type and fails that job as `OUTPUT_INVALID`.
- **#2 (#134):** `commit_import` locks the network row `FOR NO KEY UPDATE`. Commits for one network stay serialized; FK checks no longer wait on it.
- **W3 §11 lock-timeout carry-in (#134):** submit, retry and cancel wait up to 15 s for the queue lock (`admission_lock_timeout_ms`), and their statement timeout grows by the same amount. Every other queue transaction keeps 5 s.
- **Verification:** independent verifier PASS (#133) and PASS WITH NOTES (#134); reverting the three changed lines made all 5 new tests fail. CI green with 0 skipped.

## 4. Hardening batch (with the W2-06 items, after W4-02)

Each lands test-first through a small PR with Gabriel's OK:
- #5: `publish_staged` refuses a run already `done` or `failed` (`IMPORT_ALREADY_PUBLISHED`).
- #6: run `store_import_file`'s sync DB calls in the threadpool.
- #9: treat a malformed Census Match row as Census unavailable; catch `InvalidOperation` and `IndexError`.
- #10: pass `deduplicate=True` when retrying enrichment.
- #13: one staging deadline; each statement's timeout is the time left. A timeout reads as `TIMED_OUT`.
- #15: delete the dead guard (don't switch it to `.get`, which would diverge from the verifier).
- Import commit edges (web verifier): the queue admits a job in its own transaction before the run's phase is saved, so a failure in between leaves a queued job while the run reads "no job". Give the commit a stable idempotency key per run, and make `run_import` check which job owns the run. A commit still waiting when the proxy gives up at 20 s reads as "didn't start"; soften that wording after a proxy timeout.
- Notes from the #134 verifier: an import commit can outlast the proxy's 20 s; the statement budget on submit, retry and cancel is 25 s; a validate crash is stored with the same `OUTPUT_INVALID` reason as a real rejection (only the log line tells them apart).

## 5. W5 UX review

- With a second plan's Decisions open in another tab, printing from the first tab shows the "No selected actions" alert. It fails openly and never prints wrong rows. Saving the selection only when the print link is used would avoid it.
