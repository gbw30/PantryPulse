# Status — `w3-web`

**Lane:** `w3-web` · **Branch:** `lane/w3-web` · **Base SHA:** `0a4959359a447233e8ca5eea87b1917d70bd7de8` (checked: `git merge-base HEAD origin/v1-local` equals it) · **Last update:** `2026-11-09` · **Head:** see `git log`

Connected runs only count as evidence when the lane's connected stack runs (below). Mocked e2e runs prove UI behavior against the contract examples, not the connected app.

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W3-W01 | done | see `git log` (W3-W01) | Connected (schema `ppor_demo_w3web_1109014243`, API and worker with no egress): `RUN=/tmp/claude-1000/pw3 apps/web/tests/e2e/connected/run-e2e.sh tests/e2e/v1-connected-import.spec.ts --workers=1` → 4 passed (A06/A23, A07, A10, A11). Carry-in units RED first (6 failed for the expected reasons), then `npx vitest run` → 23 files, 126 passed; `node --test tests/*.test.mjs` → 12 passed; tsc and eslint exit 0; mocked e2e overview, design-lab, presenter-session, import-upload, import-templates, v1-shell, enrichment → 46 passed. |
| W3-W02 | todo | — | — |
| W3-W03 | todo | — | — |

### W3-W01 RED run (2026-11-08, connected stack, schema `ppor_demo_w3web_1108182844`)

- `@V1-A06 @V1-A23 good template set …` — FAIL for the expected reason: the import page has no Census-geocoder notice (W2-06 carry-in). The later assertions (column-guide note on rates, `Snapshot Nov 4, 2026` in the banner, no "simulated" wording) are carry-ins too and are expected to fail next.
- `@V1-A07 bad file rejected …` — FAIL, test-side: the `bad` fixture's only demand_history row had a non-ISO date, so the UI sent no `as_of_date`, and the import stopped at "no valid history date, so the as-of date can't be set" with **one** error listed. Fixed in the fixture (a valid row first, the non-ISO row on line 3). Not yet re-run.
- `@V1-A10 offline enrichment marks unknown with retry` — PASS against the real stack on the first run (the W1 settings screen already shows the outage, the blocker and Retry). Not a RED; it pins the existing behavior on the connected path.
- `@V1-A11 route labels` — FAIL, test-side: rows were matched on `textContent`, where cells join without spaces ("H1P1167.688…"). Now matched on the row's accessible name. The page itself was right: `H1 P1 … 1 day from routes.csv`, `H1 P3 … straight-line estimate · disabled by routes.csv`, the rest straight-line estimates. Not yet re-run.

### Next step on resume (exact) — superseded 2026-11-09, kept for the record

1. `git fetch && git merge-base HEAD origin/v1-local` (expect `0a49593…` unless the orchestrator asked for an update).
2. Start the stack: `RUN=/tmp/claude-1000/pw3 apps/web/tests/e2e/connected/stack-up.sh` (RUN must be a short path; it can be a symlink into the scratchpad).
3. Re-run the spec (command above) and confirm A07 and A11 now fail only for real reasons or pass, and A06 fails on the carry-ins.
4. Implement the W3-W01 carry-ins test-first, each with a unit test run RED first:
   - `template-guide.tsx`: on `locations.csv` (when it has `poverty_rate`), say a pantry given latitude and longitude is never looked up, so it needs both `poverty_rate` and `snap_rate`, or an exclusion in Settings.
   - `import-view.tsx`: say that addresses without latitude and longitude are sent to the US Census Geocoder after the import (V1-SPEC §2, §6.3).
   - `top-bar.tsx`: no "Simulated network" pill for a real import; "Sample data — fictional" for a sample (`Network.is_sample`); the legacy pill only when no v1 network is chosen. Show `Snapshot <as_of_date>` from the chosen network.
   - `presenter-footer.tsx`: "Presenter session" without "· simulated demo"; update the four e2e specs that pin the old text (presenter-session, overview-live, operations-api, scenario-lab).
5. Re-run the connected spec to PASS, then `npx vitest run`, tsc, eslint, and commit W3-W01 with this file.
6. Then W3-W02. The connected journey needs a forecast run, and `POST /networks/{id}/forecasts` is a 501 until W3-F03 merges in W4. Plan: seed a fixture forecast run from the test (as the W2-05 backend journey does with `FIXTURE_FORECAST`), keep `?forecast_run_id=` for it, and disclose that the forecast input is a fixture. See Escalations E-1.

### W3-W01 GREEN (2026-11-09)

- Re-run after the two test fixes: A11 passed; A07 passed every per-row and database check, then timed out on the switcher combobox, which a fresh schema with no networks doesn't render ("No network yet"). It now checks `GET /api/v1/networks` through the browser session and the "Current network" region instead.
- Carry-ins, each unit-tested RED first (`template-guide.test.tsx`, `import-view.test.tsx`, new `shell-labels.test.tsx`):
  - the import page says addresses without latitude and longitude go to the US Census Geocoder after the import, located rows never do, and an unreachable lookup stays unknown with a retry;
  - the locations guide (Pantry, or mode not chosen yet) says a pantry given coordinates needs both rates or an exclusion;
  - the top bar shows `Snapshot <as_of_date>` of the chosen network; its pill reads "Sample data — fictional" for a sample, nothing for a real import, "Simulated network" only when no v1 network is chosen (the legacy demo), and nothing while networks load;
  - the session footer reads "Presenter session" (four specs that pinned the old text updated).
- Still open from the carry-ins, planned with W3-W02: the overview (Live chip, atlas subtitle, product picker, legacy atlas above the ranking), names in the trust panel and Decisions, and CR-w1-web-4 in the trust panel.

## Connected run (how the evidence is produced)

Mirrors the CI connected step (`.github/workflows/pantrypulse-ci.yml:86-108`), with the lane's ports and database, and **no egress** for the API and the worker:

- `apps/web/tests/e2e/connected/stack-up.sh` loads `.env.lane`, creates a NEW `ppor_demo_w3web_*` schema in `pantrypulse_web_test` with `load_optimization_demo.py`, writes presenter credentials with `scripts/quality/demo-ci-env.py` to a 0600 file (read line by line, never `eval`ed: the hash contains `$`), and starts:
  - the API (`uvicorn --uds`) and the production-registry worker, each under `unshare -rn` (own network namespace, loopback only, so no outbound network);
  - `bridge.py` twice on the host: a unix socket `.s.PGSQL.<port>` → the shared `pp-ci-postgres`, and `127.0.0.1:8003` → the API socket.
  - It waits with `scripts/quality/wait-demo.py`.
- `run-e2e.sh` runs Playwright on 3003 with `PP_RUN_CONNECTED=1`, `PP_E2E_NO_EGRESS=1`, the presenter credentials and `DATABASE_URL`/`PP_DATABASE_SCHEMA` for the read-only probe (`connected/db_probe.py`).
- `stack-down.sh` stops it. Each `stack-up.sh` makes a new schema; earlier ones stay in `pantrypulse_web_test` (only `ppor_demo_w3web_1108182844` so far).

## Gates

| Gate | Commit | Result |
|---|---|---|
| `npx tsc --noEmit -p apps/web`, `eslint` on the new spec files | save point | exit 0 / exit 0 |
| `node scripts/quality/run.cjs quick` | | not run yet |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | not run yet |
| `/devkit:ship-check` | | not run yet |

## Decisions made inside the lane

- Connected fixtures are lane-owned CSV sets in `apps/web/tests/e2e/fixtures/v1-connected/` (`pantry`, `bad`, `unlocated`), fictional, with fixed dates (as_of 2026-11-04). `pantry` follows the backend `mini-network` fixture and adds routes, inbound and donation files. — W3-W01
- "Nothing saved" in A07 is checked in the database, not only in the UI: a read-only digest of every row of `networks`, `dataset_versions`, `net_locations`, `net_products`, `net_batches` before and after (`connected/db_probe.py`, same idea as the W2-05 journey's stock snapshot). — W3-W01
- The A10 test requires `PP_E2E_NO_EGRESS=1` and fails loudly without it, instead of skipping (CI rejects skips) or calling the real Census geocoder. — W3-W01

## Gotchas

- AF_UNIX socket paths are capped at 107 bytes; the session scratchpad path is too long, so `RUN` must be short (a symlink works). — W3-W01
- The worker's step children get an allowlisted environment (`process_driver.py:26`), so proxy variables can't make enrichment offline; only a network namespace (or a firewall) does. — W3-W01
- When demand_history.csv has no valid date and no `as_of_date` is sent, the import fails with that single error and lists no other row errors. A user with several bad rows sees only this one first. Not changed (server behavior, data lane/lead); worth a look in W4 hardening. — W3-W01

## Change requests

### CR-w3-web-1 — run the CI connected step's API and worker with no egress
- **File(s):** `.github/workflows/pantrypulse-ci.yml` (lead-only)
- **Exact change:** in "Real browser, proxy, database and worker journey", run the API and the worker without outbound network and export `PP_E2E_NO_EGRESS=1` for Playwright. Options: (a) the lane's launcher approach (`unshare -rn` plus a unix-socket bridge to PostgreSQL; on GitHub's Ubuntu 24.04 runners this needs `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0` first); (b) run the worker as a separate user and drop its outbound traffic with an `iptables -m owner` rule (sudo is available on hosted runners). Recommend (a): it is the same setup as the lane evidence.
- **Why:** wave-3 W3-W01 requires `@V1-A10 offline enrichment marks unknown with retry` with "the API runs with no egress". CI runs every connected spec and rejects skips (`require-test-evidence.py`). Without this change, CI either calls the real Census geocoder with a fictional address (not offline, and flaky) or the test fails on its precondition. The test now fails loudly in CI until this lands.
- **Unblocks:** W3-W01 in CI (V1-A10 connected evidence); the lane PR's CI.
- **Status:** approved (Gabriel via the lead, 2026-11-09), option (a). The lead lands the CI change on v1-local with a lead-owned copy of `bridge.py` at `scripts/quality/netns-bridge.py`. When that PR merges: `git merge origin/v1-local`, point `stack-up.sh` at `scripts/quality/netns-bridge.py`, delete `connected/bridge.py`.

## Escalations

- 2026-11-08 — W3-W02 — E-1, plan gap (ORCHESTRATION §5 item 4): the connected Pantry/Retail journeys need a forecast run to freeze a scenario (`ScenarioOptions.forecast_run_id` is required), but `POST /networks/{id}/forecasts` and `GET /networks/{id}/forecasts` are 501 stubs until W3-F03 merges in W4. Proposed (not yet done): the test seeds a fixture forecast run, as the W2-05 backend journey does (`test_v1_backend_journey.py:176`, `FIXTURE_FORECAST`), keeps the `?forecast_run_id=` stopgap for it, and the PR states that the forecast input is a fixture while import, scenario, comparison, decisions and export are real. Orchestrator: confirm or redirect before W3-W02 starts.
  - **Decision (Gabriel via the lead, 2026-11-09): approved.** Seed the fixture forecast run as `test_v1_backend_journey.py` does (`FIXTURE_FORECAST`), keep `?forecast_run_id=`, disclose it in the PR and here, and never count it as forecast evidence. At W4 the journeys switch to a real forecast run (lead's W4 task).
