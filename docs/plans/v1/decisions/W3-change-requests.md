# W3 decisions: change requests and escalations from the wave-3 lanes

**Status:** decided by Gabriel, 2026-11-09. **Applies to:** the W3 lanes, W4 and W5. The lane status files (`docs/plans/v1/status/w3-*.md` on each `lane/w3-*` branch) hold each request in full.

## 1. CR-w3-samples-1: sample rates read "sample values" (approved, lead)

- **Change:** V1-SPEC §8 labels a sample network's pre-filled poverty and SNAP rates "sample values". `location_attributes` (`apps/api/app/services/enrichment/service.py`) now reports source "sample values" instead of "manual" when no rate comes from a lookup (each rate is manual or missing) and the location's network has `is_sample`. The state stays `manual`. The scenario freeze copies the source, so a frozen sample scenario carries the same label.
- **Test:** `test_sample_network_template_rates_labeled_sample_values`. A sample import reads "sample values"; the same files imported as a normal network read "manual".
- **Known limit:** no column tells a template rate apart from a user's own edit (`PUT .../attributes` writes the same `manual_*` columns). A user's edit on a sample location therefore also reads "sample values". Sample rates come pre-filled, so EGP never asks for one. If sample editing matters later, add a column that records who entered the rates.
- **Screen (web lane):** `attribute-editor.tsx` `sourceLine` shows "Source: entered by you" for every `manual` state and never reads `source`, so the label doesn't reach the screen yet. The web lane shows "Source: sample values" when `source` says so (verifier, 2026-11-09).

## 2. CR-w3-samples-2: template CSVs keep LF on Windows (approved, lead)

`.gitattributes` adds `data/templates/**/*.csv text eol=lf`. With `core.autocrlf=true`, a Windows checkout turned the templates into CRLF, so the byte-equality drift tests failed there. The importer already accepts CRLF.

## 3. CR-w3-web-1: the CI connected step runs the backend with no egress (approved, option (a), lead)

- **Why:** V1-A10 (enrichment offline → unknown, with retry) must be shown with an API that can't reach the internet. CI rejects skips, so the web lane's test fails unless `PP_E2E_NO_EGRESS=1` is set.
- **Change** (`.github/workflows/pantrypulse-ci.yml`):
  1. `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`. GitHub's Ubuntu 24.04 image restricts unprivileged user namespaces.
  2. The API and the worker each run under `unshare -rn`. They reach PostgreSQL through a unix socket, and the API serves on one. `scripts/quality/netns-bridge.py` forwards both to TCP on the host.
  3. The step sets `PP_E2E_NO_EGRESS=1` and first checks that a connection from the namespace fails with `ENETUNREACH`.
- **Bridge:** `netns-bridge.py` is the web lane's `apps/web/tests/e2e/connected/bridge.py`, now lead-owned. After this merges, the web lane points `stack-up.sh` at it and deletes its own copy.
- **Rejected:** option (b), a separate worker user with an `iptables` owner rule. It needs more runner plumbing, and the lane hadn't tested it.

## 4. E-1: fixture forecast run in the web lane's connected journeys (approved)

The connected Pantry and Retail journeys need a forecast run to freeze a scenario. The network forecast routes stay 501 until W3-F03 merges. The web lane therefore seeds a fixture forecast run, the way `tests/integration/test_v1_backend_journey.py` does, and keeps the `?forecast_run_id=` stopgap. Import, scenario, comparison, decisions and export stay real. The PR discloses the fixture, and it never counts as forecast evidence. **W4-02** switches these journeys to a real `forecast.v1` run.

## 5. CR-w3-forecast-1: where backtest results are stored (approved, option B, lead)

Filed at `lane/w3-forecast` `448f8e3`. `backtest_scores` (`ppv1_0008`) has no `origins_evaluated`, no pooled sums and no run key, so `get_backtest(job_id)` can't serve the CR-w1-web-4 contract.

| Option | Change |
|---|---|
| A | Widen `backtest_scores` with a run FK, `origins_evaluated`, the pooled sums and wider `wape`/`bias`. Reads aggregate up to 50k rows per request. |
| B (lane recommends) | A nullable `forecast_runs.backtest` JSONB column holding the `BacktestResult` body, written in the run's existing INSERT and read as one row. |

**Decision (Gabriel, 2026-11-09): option B.** Migration `ppv1_0014` adds `forecast_runs.backtest` JSONB, NULL or a JSON object (`ck_forecast_runs_backtest`), and the `ForecastRun.backtest` model column. Only the `forecast.v1` network publisher writes it, in the run's INSERT, so it stays immutable with the run. `get_backtest` reads that one row and returns 404 for a run without one. Older runs and v2 site runs keep NULL. Downgrade refuses while a backtest is stored. `backtest_scores` stays unused in v1.

## 6. CR-w3-samples-3: Retail examples need a mode on the example download (approved, lead, then samples)

- **Lead (#125):** `GET /v1/templates/{name}.csv?kind=example&mode=PANTRY|RETAIL`.
  - With no mode, the route serves PANTRY. Any other mode returns 422. A blank download ignores the mode.
  - The Next.js proxy allows `kind` and `mode` on the template route.
  - RETAIL returned 404 `TEMPLATE_EXAMPLE_UNAVAILABLE` until the samples lane added Retail examples.
- **Samples (#128):**
  - `template_csv(name, "example", "RETAIL")` serves the Retail sample on `EXAMPLE_AS_OF`, byte for byte equal to `data/templates/examples/retail/*.csv`. The drift check covers both modes.
  - The RETAIL catalog offers examples. The catalog with no mode offers none.
  - The Retail sample gains `routes.csv`; the other six Retail files are unchanged.
  - The lead authorized one edit in `tests/imports/test_templates.py`: the RETAIL assertion now expects 200.
- **Merge order (Gabriel):** #128 merges only after the web PR that adds `mode` to example links. Otherwise a Retail import would download the Pantry files. The connected check that a Retail import downloads the Retail file is a W4 carry-in.

## 7. CR-w3-samples-4: seed date and transaction (approved (a) and (b), lead, then samples)

- **(a) Date (#125):** the bootstrap seeds with today's date in New York, the samples' timezone (`local_bootstrap.seed_today`). The UTC date was a day ahead from 20:00 to 24:00 New York time.
- **(b) Transaction (#125):** the login and the organization commit in their own transaction before `ensure_samples`. An open organizations write blocked the import's partition ATTACH.
- **Follow-up (#128):**
  - `ensure_samples` no longer commits the caller's transaction.
  - It refuses a session with pending ORM changes or an assigned xid.
  - The test helper commits the organization first.
  - Known limit (verifier G1): the guard misses a no-op write that holds a lock without an xid, for example `INSERT … ON CONFLICT DO NOTHING`. No caller does this. W4 passes an engine instead of a session, which removes the case.

## 8. CR-w3-web-2: presenter password in Playwright traces (approved, option (a), web lane)

- **Problem:** `trace: "retain-on-failure"` records the password, and CI uploads `apps/web/test-results/`. The password appears in the `fill` argument, in DOM snapshots of the input and in the login request body. No change to the sign-in helper can prevent this.
- **Decision:** `trace` is `"off"` when `PP_E2E_PRODUCTION=1`, the connected suite with a real password. Mocked runs keep `"retain-on-failure"`.
- **Ownership:** the web lane may make this bounded edit to the lead file `apps/web/playwright.config.ts`, with a test.
- **Rejected:** (b), excluding `trace.zip` from the CI upload. Local connected runs would still write the password to disk.

## 9. "Simulated network" label narrowed (approved, W3, web lane)

The top bar showed "Simulated network" whenever no v1 network was chosen. That included /import and /settings for a new user, and a failed network list.
- It is hidden on /import and /settings.
- A failed network list shows "Network list unavailable".
- It stays on every page that shows the legacy fixture data. A test lists those pages.

## 10. Forecast PR #127 review (Gabriel, 2026-11-09)

- **F1, fix in W3:** at 50k series, `publish` built the 106 MB output and the backtest inside the global queue lock: 4.2 s quiet, 7.3–7.9 s under load, against a 5 s lock timeout. The build moves to the publisher's `prepare` hook, and `publish` keeps only the INSERT.
- **`bias_pct`, accepted:** 100 × Σ(prediction − actual) / Σactual, a percentage, null when Σactual is 0. This overrides V5 §7's bias in units for v1. Units differ per product, so a bias in units can't be compared across series.
- **Limits, accepted:** `forecast.v1` `max_input_bytes` 24 MB and `max_output_bytes` 32 MB. The measured worst cases are 20.6 MB and 14.5 MB, pinned by a test.
- **Retail DC scoring, accepted:** a DC has no demand, so its dated stock is scored by expiry share. That share is 1.0 when nothing moves (V1-SPEC §6.6). The W5 UX review checks how the atlas explains it.
- **Test gaps F2–F4:** the lane closes them in W3. They cover an absent day staying null, donation history ending after demand, and the inbound term in the expiry share.

## 11. W4 carry-ins from W3

- **Series cap at import (lead):** V1-SPEC §5.1. An import within the envelope can still yield more than 50,000 demand + donation series. Today that is refused only at forecast submit (422 `FORECAST_SERIES_OVER_ENVELOPE`).
- **Danger and projection reads:** `GET /networks/{id}/danger` and `/projection` recompute on every request, about 4–6.7 s at 50k series, with no cache.
- **Samples:** `ensure_samples` and `seed_local.seed` take an engine, not a session (§7).
- **Web:** the connected Retail example download (§6), and W4-02's real `forecast.v1` run (§4).
- **Queue lock timeout (lead, Gabriel 2026-11-10):** after F1, a 50k-series forecast still holds the global queue lock for about 3.9–4.8 s, to INSERT its run row: the 106 MB output, the frozen input and the 9.4 MB backtest. The lock timeout is 5 s. Gabriel chose to raise the lock timeout for submit, retry and cancel (for example to 15 s) rather than stage the row outside the lock.
- **Prepare retries (lead, verifier N3 on #127):** a passing database error in a publisher's `prepare` now fails the attempt (`PREPARE_FAILED`). Before F1, the same read was retried as `QueueStorageUnavailable`. The supervisor should retry it.
- **Test gaps:** no test covers the network-switcher half of `235e30e` alone, the part where a visitor makes no `/networks` request. The API fixtures `apps/api/tests/networks/fixtures/{mini-network,retail-twin}/forecast.json` still say "fixture stand-ins".
- **W5 UX review:** /data shows "Simulated network" above a real network's "Forecast trust" section, so the page mixes simulated and real data. Also check how the atlas explains a Retail DC's expiry share (§10).

## 12. Gate and test fixes (lead, merged)

- **#124:** the Stop hook waits `stopHookTimeoutSeconds` (600 s) and reports a timeout as a timeout. The API-test step gets 900 s; the budgets are quick 960 s and full 1500 s. Under lane load, passing runs had been killed at 165 s and 480 s.
- **#126:** the supervisor test's prepare probe used `FOR UPDATE NOWAIT`, which failed whenever it landed inside the heartbeat's brief row lock (once in 2032 tests). It now waits up to 500 ms.

## 13. Later W3 decisions (Gabriel, 2026-11-10)

- **Forecast #127 review round 2:** N4 is fixed: a publish retried after a failed INSERT reuses the prepared run. N1 is fixed: the bench counts the lock acquire, and the 50k figures were about 5% low. N2 adds a shortcut comment: `prepare` ignores `remaining_s`. Gabriel approved the merge after the lead checked the diff and CI passed.
- **Web #129, H1 (High):** a rejected sign-in left the typed password in the form, and Playwright's aria snapshot wrote it to `error-context.md`, which CI uploads. Gabriel chose both fixes:
  - the sign-in form empties the password after any failed sign-in;
  - the test helper waits less than the test's time and clears the field in `finally`;
  - a canary spec checks that no output file contains the password.
- **Web #129, N1:** a login that never answered could still leak the password. Gabriel chose to fix it before the merge. Sign-in now aborts after 10 s with "Sign-in timed out. Try again." and empties the field. The helper extends the test's timeout to cover its own wait.
- **Web #129, M1:** traces are off when `PP_RUN_CONNECTED=1` or `PP_E2E_PRODUCTION=1`, so local connected runs are covered too (§8).
- **Attribution:** no attribution line in commits or PR bodies: no Co-Authored-By, no Claude-Session, no "🤖 Generated with". Claude Code's own reminder adds the PR line, so lanes remove it.
- **Merge order:** #127, then #129, then #128. #128 waited for #129 so that Retail example links carry `mode` before the catalog offers them.
