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

## 5. W4-02 ownership

The web lane builds W4-02: the new `apps/web/tests/e2e/v1-full-journey.spec.ts`, the E-1 switch to a real `forecast.v1` run and the connected Retail example download. This changes `wave-4.md`, which gave the spec to the orchestrator; the web lane already owns the connected harness and the E-1 journeys. The lead runs the whole set connected, does the #3 compose re-up check and sends failures to an integration-fixer. An independent verifier checks before the PR.

## 6. W5 UX review

- With a second plan's Decisions open in another tab, printing from the first tab shows the "No selected actions" alert. It fails openly and never prints wrong rows. Saving the selection only when the print link is used would avoid it.

## 7. Hardening batch outcomes (#137 enrichment, #138 solver, #139 imports; Gabriel, 2026-11-10)

- **#9 is per-row:** a malformed Census Match row is `Unreadable`. Its location stays unlocated and is listed for review. Every other row in the batch keeps its result. This replaces failing the whole batch.
- **Reverse geocoding** for locations given with coordinates moves to the W5 known-limits list. The column guide already asks for manual rates or an exclusion.
- **`IMPORT_ALREADY_FINISHED`, not `…_PUBLISHED`:** a run that is already `done` or `failed` is refused. Because a failed run is refused too, the code name says FINISHED.
- **Expired-on-arrival inbound stays frozen:** the solver keeps it, and the decision is to document it.
- **Known limits (H1, H3):**
  - The import sweep assumes one supervisor.
  - After a lost phase record, a re-upload that lands while the admitted job reads its files can import a mix of old and new files.
  - The receivers' selling order comes from the shared projection.
  - The F2 starvation screen covers donor protection only.
  - The verifier's receiving-capacity check uses the packed arrival date.

## 8. W4-02 and the web hardening (#140, #142)

- **Forecast UI:** the Overview has one "Run forecast" control, for the presenter only. A running job shows again after a reload, and there is no cancel. A replayed forecast says "already up to date" instead of "new run". The `?forecast_run_id=` stopgap is gone.
- **Web hardening:** enrichment that never started shows its reason with Retry. A commit that got no answer "may still be starting", and the page checks up to 30 times before it says "didn't start". "Check again" resumes that window, so it never offers a duplicate import.
- **Known limits:**
  - Two local workers seeding one fresh database can race; the race fails loudly. CI runs one worker.
  - The end-to-end time budget runs at 240–268 s of 300 s.

## 9. CI: docs-only PRs skip the full job (#141; Gabriel, 2026-11-11)

- **Docs-only** means every changed file is Markdown under `docs/` or at the root, except the root `README.md` and the three files a test reads (`TEST_READ`). A docs-only PR skips `full`.
- `git diff --no-renames` counts both sides of a rename. If the classifier fails, `full` runs. Pushes to main always run `full`.
- **Known limit:** the read guard sees only quoted literal `docs/…md` paths.

## 10. W4-03 review gates (Gabriel, 2026-11-11)

**Step 1, adversarial review of `d9b4a08`:** one High, reproduced by the lead.
- The High: a pantry or store with no available forecast was planned as if its demand were zero, so every method could ship its whole stock, and the verifier passed the plan.
- Fixed in #144: such a location sends none of that product, under every method, and the verifier rejects it on its own path (`UNKNOWN_DEMAND_SENDER`).
- Held, with evidence: blank-only history, inbound on the last horizon day, the re-seed on day 8, a stale version returning 409, retried import keys, tenant isolation, a danger tie, and Retail stock all expiring tomorrow.

**Overview CI flake:** root-caused and fixed in #143. A closed card's late focus return, and its outside-click handler, closed the next site's card. CI then ran with 0 flaky.

**Step 3, research-claims review:** no false research or impact claims. Label fixes landed in #145 and #146:
- #1: the Data screen label;
- #2: the ACS source;
- #4: the empty ranking says nothing could be ranked;
- #5: the Low band "under 20% (may be none)";
- #9: "this network's history";
- #3 stopgap: the import guide names where the sales label appears.

**Decisions:**
- **#6:** "Plans aim to help the most people" is kept as the V1-D03 wording.
- **#3, full fix (W5):** the danger ranking and projection rows carry the demand basis, so sales-based demand is labeled everywhere (V1-SPEC §6.1). This is a contract change.
- **#8 (W5):** the frozen scenario carries per-location donation forecasts (option A, a contract change), so each location's explanation shows "expected donations (forecast, not confirmed)". Option B, a lookup at explanation time, was rejected: it would loosen the rule that a plan's inputs are frozen.
- **Hubs and distribution centres (W5):** the import refuses (or clearly flags) demand history for hubs and distribution centres. Until then, a hub whose history is all blank is listed "no forecast" but can still send.

**Known limits and W5 candidates:**
- A comparison re-run on a scenario frozen before #144 returns its stored result (dev databases only).
- A backtest with an all-zero denominator reads "evaluated" with null scores and no reason.
- The Retail band meanings say "projected short" though a Retail score can come from expiry.
- The product picker (Radix Select) has a similar late focus return; it was not seen on CI.
- A repeated commit on a finished import can move its phase back. It was seen only through a test-harness shortcut.
- Local e2e runs need a free-port check and no server reuse, because Playwright reuses a leftover server outside CI.

**Step 2, ux-critic:** see §11.

## 11. W4-03 step 2: the ux-critic review (2026-11-11)

**Evidence:** the lead captured the connected app on v1-local `60ccf17` (real API and database, both samples) at 1440×900, 1280×720 and 390×844: import, the Overview atlas and ranking, the live site inspector, forecast trust, a Scenario Lab comparison, Decisions, a reduced-motion card, and a keyboard walkthrough with its Tab order. The critic reviewed the screenshots and the code; it ran nothing.

**Findings, ranked** (each is a W5 polish task, W5-UI02.1–.5):
1. **High — Data Explorer mixes networks.** With a v1 network selected, `/data` shows the legacy summary block (other sites, other units, another run) above that network's Forecast trust. A reader takes its fill rate and unmet totals as their own. The lead confirmed it in code: `data-explorer.tsx:201` renders the legacy `Screen` above `ForecastTrustSection`.
2. **High — Scenario Lab comparison is clipped.** Two method cards per row clip the quantity columns at 1440 and 1280, every card lists all its rows (even "No transfers"), and "Open suggested actions" sits below them.
3. **High — Decisions effects don't name their period.** The Overview shows 7-day unmet need; a 2-day plan says "Receiver unmet need: 7 cases lower" with no dates, so a reader can think the plan clears the week.
4. **High — Retail expiry reads as a shortage.** The DC ranks first at 100% ("first deficit"), and the legend explains every band as "projected short". A DC has no sales, so stock it doesn't send counts as expiring (W3 §10). This absorbs the Retail band wording from §10.
5. **Medium-High — the Overview's first view.** The ranking starts below the fold at 1440×900 and 1280×720. "Run forecast" reads as the ranking's main action. The inspector lists products alphabetically, so the driving product isn't first. A focused marker shows no site name. Escape doesn't close the live inspector: the lead confirmed this from the keyboard log and the code (`location-inspector.tsx` has no Escape handler, unlike `network-atlas.tsx:292-305`).

**The known items:**
- "Run forecast" placement: folded into finding 5.
- Two tabs and one print selection: not a blocker (it fails openly). The §6 fix stays: save the selection only when the print link is used (W5-UI05).
- 7-day unmet need next to a 1–3-day plan: finding 3.
- "Already up to date": clear as written; no change.
- A card stays open when focus moves to another marker (#143): correct; Escape is covered by finding 5.

**Notes** (W5-UI05):
- The sidebar network selector is wider than the sidebar and covers page titles at 1440 and 1280.
- Import step 1 opens all seven column guides, so the page runs about 5,800 px; collapse them by default. The routes and inbound hints read "Optional. Optional.".
- The unit plural writes "boxs".
- Retail "each" reads oddly ("17 each projected unmet").

**V1-A20:** not passable from this evidence. Focus is visible, a keyboard-opened card takes focus, and the reduced-motion card is complete and readable. Still needed in W5-UI03: axe at all three viewports on import, Decisions and the atlas ranking; keyboard walkthroughs of import and Decisions; reduced-motion runs at 1280 and 390; marker touch targets at 390×844.

**Refuted:** the critic said the Data Explorer footer links to a missing `/optimization` route. The route exists (`apps/web/src/app/optimization`).
