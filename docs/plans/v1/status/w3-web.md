# Status — `w3-web`

**Lane:** `w3-web` · **Branch:** `lane/w3-web` · **Base SHA:** `0a4959359a447233e8ca5eea87b1917d70bd7de8` (checked: `git merge-base HEAD origin/v1-local` equals it) · **Last update:** `2026-11-09` · **Head:** see `git log`

Connected runs only count as evidence when the lane's connected stack runs (below). Mocked e2e runs prove UI behavior against the contract examples, not the connected app.

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W3-W01 | done | see `git log` (W3-W01) | Connected (schema `ppor_demo_w3web_1109014243`, API and worker with no egress): `RUN=/tmp/claude-1000/pw3 apps/web/tests/e2e/connected/run-e2e.sh tests/e2e/v1-connected-import.spec.ts --workers=1` → 4 passed (A06/A23, A07, A10, A11). Carry-in units RED first (6 failed for the expected reasons), then `npx vitest run` → 23 files, 126 passed; `node --test tests/*.test.mjs` → 12 passed; tsc and eslint exit 0; mocked e2e overview, design-lab, presenter-session, import-upload, import-templates, v1-shell, enrichment → 46 passed. |
| W3-W02 | done | see `git log` (W3-W02); carry-in `55fbdc9` | Connected, whole suite as in CI's connected step (production build, API and worker with no egress, schema `ppor_demo_w3web_1109024125` already holding v1 networks): `PP_E2E_PRODUCTION=1 RUN=/tmp/claude-1000/pw4 apps/web/tests/e2e/connected/run-e2e.sh --workers=1` → 192 passed, 0 failed, 0 skipped, including A14, A15 and A16 (journey) and A06/A23, A07, A10, A11 (import). The forecast run in A14–A16 is a FIXTURE (E-1), not forecast evidence. Units RED first, then `npx vitest run` → 23 files, 134 passed; `node --test tests/*.test.mjs` → 12 passed; tsc and eslint exit 0; `node scripts/quality/run.cjs quick` → exit 0 (web typecheck, web lint, api lint, api tests PASS). |
| W3-W03 | done | see `git log` (W3-W03) | Connected, whole suite as in CI's connected step (production build, API and worker with no egress through `scripts/quality/netns-bridge.py`, schema `ppor_demo_w3web_1109170453`, which already held the first run's v1 networks): `PP_E2E_PRODUCTION=1 RUN=/tmp/claude-1000/pw5 apps/web/tests/e2e/connected/run-e2e.sh --workers=1` → 208 passed, 0 failed, 0 skipped, including the 13 `@V1-A20` tests in `v1-a11y.spec.ts` and the new `@V1-A10` sample-values test. `npx vitest run` → 24 files, 138 passed; `node scripts/quality/run.cjs quick` → exit 0 (web typecheck, web lint, api lint, api tests PASS). |

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
- Still open from the carry-ins, planned with W3-W02: the overview (Live chip, atlas subtitle, product picker, legacy atlas above the ranking), names in the trust panel and Decisions, and CR-w1-web-4 in the trust panel. Done in W3-W02 (below).

### W3-W02 (2026-11-09)

- **Fixture forecast (E-1):** `connected/seed_forecast.py` runs the W2-05 journey's `FIXTURE_FORECAST` job on its own queue lane (`e2e_fixture`, a `compute_control` row it adds), so the production worker keeps the `default` lane, and prints the `forecast_run_id`. The series come from each set's `forecast.json` (copied from the backend fixtures). The journeys pass it as `?forecast_run_id=`. It is never forecast evidence; import, scenario, comparison, decisions and export are real.
- **RED → GREEN, connected (`v1-connected-journey.spec.ts`):** A14 and A15 passed on the first run, since the W1/W2 wiring already held. A16 failed for a test-side reason: it expected the mocked decisions spec's illustrative CSV header, but the server writes the W1-S07 columns (`scenario_id,scenario_hash,method,network_mode,product,unit,quantity,from,to,ship_date,arrival_date,why,effect,note`). A16 now pins that header; the mocked spec's comment says its columns are illustrative.
- **Carry-ins, each RED first:**
  - overview: a chosen v1 network shows its own header and danger ranking. The legacy demo atlas (its fixture/live snapshot, "Live · simulated network" chip, "simulated network" subtitle and pickers) shows only when no v1 network is chosen. `ShellProviders` mounts the session/network providers once, so the overview can read the network above its `AppShell` (unit tests RED, then GREEN). The connected A06 test now checks `/overview` after a real import, and it fails on the previous atlas (`[data-overview-source]` count 1).
  - the product and day pickers no longer say "Loading…" after a failed snapshot or with no products ("No products (snapshot unavailable)", "No products"); same for the data explorer's product picker.
  - names: Decisions already names locations (the server writes names into the action and why texts, `apps/api/app/services/optimization/actions.py:155-185`); A14 now asserts every action names locations and the effects tables use names. The trust panel uses `LocationList` names.
  - CR-w1-web-4: the data page takes `?forecast_run_id=`. The trust section reads `GET /networks/{id}/forecasts/{run}` (new client method, and a proxy GET route with its node test) for each series' method, fallback, missing days, band and the donation forecast. It reads the backtest by the run's `job_id`, and shows one "Accuracy by location and unit" row per `BacktestResult.locations` entry, never pooled across units. Mocked from the contract examples until W4.
  - lead carry-in (CR-w3-samples-1): `sourceLine` shows "Source: sample values" for sample-valued manual rates (commit `55fbdc9`).
- **Legacy connected overview test:** `overview-live.spec.ts` "connected: a signed-in presenter sees live data" now expects the network's ranking when the presenter has v1 networks and the legacy live atlas only when there are none; its old expectation depended on spec order and fails once samples are seeded.
- **Layout test race (`overview-layout.spec.ts`, "drops are clamped"):** in the full connected run it failed once. Over repeats it failed on the third repeat each time (1 in 3, then 1 in 5). The old atlas passed 3 of 3 repeats. The snapshot showed Pine Ridge's card open instead of Willow Creek's. After Escape, Radix returns focus to the opening marker when the card unmounts (`onCloseAutoFocus`), which can land after the dialog role is gone, so the test's next `focus()` was taken back. A keyboard user can't act inside that window. The test now waits for focus to return to the marker that opened the card (the intended behavior) before moving on: 175 of 175 over 5 repeats. My change moved the legacy atlas's first mount after the network list loads (client-side), which shifted the timing.
- **Legacy connected specs with v1 networks present:** a second full connected run on the same schema (v1 networks left by the first) failed `operations-api` (line 78), `recommendations` (line 320) and `scenario-lab` (line 450): strict-mode violations on "Compare methods". With a v1 network chosen, `/scenarios` shows both the legacy "Scenario builder" and the v1 "Comparison setup", and each has that button. This was already on the base, and CI's fresh schema avoids it only because those specs run before the v1 imports; seeded samples would trigger it there too. The locators are now scoped to the legacy "Scenario builder" form, and the three tests pass with v1 networks present. **For the lead:** `/scenarios` showing two builders for a v1 network is the same pattern as the overview carry-in. Resolved by lead item 1 below.

## Connected run (how the evidence is produced)

Mirrors the CI connected step (`.github/workflows/pantrypulse-ci.yml:86-108`), with the lane's ports and database, and **no egress** for the API and the worker:

- `apps/web/tests/e2e/connected/stack-up.sh` loads `.env.lane`, creates a NEW `ppor_demo_w3web_*` schema in `pantrypulse_web_test` with `load_optimization_demo.py`, writes presenter credentials with `scripts/quality/demo-ci-env.py` to a 0600 file (read line by line, never `eval`ed: the hash contains `$`), and starts:
  - the API (`uvicorn --uds`) and the production-registry worker, each under `unshare -rn` (own network namespace, loopback only, so no outbound network);
  - `scripts/quality/netns-bridge.py` (the lead's copy of the former lane `bridge.py`, CR-w3-web-1) twice on the host: a unix socket `.s.PGSQL.<port>` → the shared `pp-ci-postgres`, and `127.0.0.1:8003` → the API socket.
  - It waits with `scripts/quality/wait-demo.py`.
- `run-e2e.sh` runs Playwright on 3003 with `PP_RUN_CONNECTED=1`, `PP_E2E_NO_EGRESS=1`, the presenter credentials and `DATABASE_URL`/`PP_DATABASE_SCHEMA` for the read-only probe (`connected/db_probe.py`).
- `stack-down.sh` stops it. Each `stack-up.sh` makes a new schema; earlier ones stay in `pantrypulse_web_test` (`ppor_demo_w3web_1108182844`, `…_1109014243`, `…_1109024125` so far). The W3-W02 stack was restarted on a new schema after a failure snapshot recorded that run's generated password (Gotchas).

## Gates

| Gate | Commit | Result |
|---|---|---|
| `npx tsc --noEmit -p apps/web`, `eslint` on the new spec files | save point | exit 0 / exit 0 |
| `node scripts/quality/run.cjs quick` | W3-W02 | exit 0: web typecheck, web lint, api lint, api tests PASS |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | not run yet |
| `/devkit:ship-check` | | not run yet |

### Lead items (approved 2026-11-09)

- **Item 1, `/scenarios` with a v1 network:** a chosen v1 network shows only its "Method comparison" (header, then the v1 section); the legacy "Scenario builder", its saved-work pickers and its planning-catalog load appear only when no v1 network is chosen, and "Loading networks…" shows meanwhile (same pattern as the overview). Unit tests RED first (`tests/unit/scenario-lab.test.tsx`: 3 failed, both builders rendered), then GREEN. The mocked `v1-comparison.spec.ts` (A14) asserts no "Scenario builder" form and no `planning-catalog` call; the connected journey asserts no "Scenario builder" form for a real imported network.
- **Legacy specs that drive the legacy builder:** the network provider picks the first v1 network whenever one exists (at W4 the seeded samples always do), so the legacy builder is reachable only with no v1 network. The three connected specs (`operations-api`, `recommendations`, `scenario-lab`) now start with `withoutV1Networks(page)` (`tests/e2e/v1-mocks.ts`): only `GET /api/v1/networks` is answered (`{networks: []}`), and every other request reaches the real API. Their "Compare methods" locators are back to the unscoped originals, so a second builder on that view fails strict mode. The mocked `forecasting-integration.spec.ts` returned the example network list for the shell and now returns none, for the same reason (6 RED after item 1, then 6 passed). Showing two builders for a chosen v1 network is caught by the unit test, the mocked A14 test and the connected journey.
- **Item 3, one sign-in helper:** `tests/e2e/sign-in.ts` `signInThroughForm(page)` is the only form sign-in in the connected specs (`data-explorer`, `operations-api`, `overview-live`, `recommendations`, `scenario-lab`, and `connected.ts`'s per-worker `signIn`). A rejected login fails in 30 s and empties the password field first, so no password reaches `error-context.md` or the uploaded `test-results/`. `presenter-session.spec.ts` keeps its own form steps: it is mocked and types the fixed strings "wrong" and "right" to test the form itself.
- **Evidence:** `npx vitest run` → 24 files, 137 passed; tsc and eslint exit 0. Mocked e2e: v1-comparison, scenario-lab, recommendations, operations-api, overview-live, data-explorer, forecasting-integration, presenter-session → 89 passed, 0 failed (connected-only tests skip in mocked mode); one presenter-session 390×844 failure in the first parallel run did not recur in 15 of 15 repeats (the "Open navigation" click can land before hydration; `/overview` is unchanged by these items). Connected (production build, no egress, schema `ppor_demo_w3web_1109024125` already holding v1 networks): `PP_E2E_PRODUCTION=1 RUN=/tmp/claude-1000/pw4 apps/web/tests/e2e/connected/run-e2e.sh` with the specs above plus v1-connected-import and v1-connected-journey, `--workers=1` → 99 passed, 0 failed, 0 skipped.

### Save point 2026-11-09 (superseded by W3-W03 below; kept for the record)

- **Head:** the commit that adds this section, on top of `85e1561` (pushed to `origin/lane/w3-web`, no PR yet). Merged `origin/v1-local` at `5c5fbe7` (lead PR #122) in `298b24a`, no rebase.
- **Done:** W3-W01 and W3-W02 (evidence in the table above). Lead items 1 and 3 (`0932747`, evidence under "Lead items" above; connected 99 passed on the pre-merge stack). CR-w3-web-1 follow-up (`694d2d2`): `stack-up.sh` runs `scripts/quality/netns-bridge.py` and waits for the PG bridge socket like CI. `connected/bridge.py` was deleted.
- **Written, never run (no RED or GREEN yet):**
  - `8897020`: a connected `@V1-A10` test in `v1-connected-import.spec.ts`. It checks that a sample network's pre-filled rates read "Source: sample values" and a normal import's read "Source: entered by you". The sample is seeded with `connected/seed_sample.py`, the importer run with the internal seed's `is_sample` flag, until the W4 samples exist.
  - `85e1561`: W3-W03 `v1-a11y.spec.ts` covers import, decisions and atlas ranking at 3 viewports. Each runs a keyboard-only path (no click, fill or `focus()`), axe with zero violations of any impact, and a recorder of every CSS animation, transition, `animate()` and inline transform change under reduced motion. The import mocks moved to `v1-import-mocks.ts` (`import-upload.spec.ts` imports them; tsc and eslint pass, the e2e is not re-run).
- **Known RED tests:** none. The two specs above have not run.
- **Expected findings when W3-W03 runs (unverified):** Radix select, dialog, popover and sheet keep their `zoom-in-95` and slide `animate-in` keyframes under reduced motion. `tw-animate-css` has no reduced-motion rule, and the one in `shadcn/tailwind.css` covers only `shimmer`; the fix belongs in `src/components/ui/*` (`motion-reduce:` classes), not `globals.css`. Focus may fall to `<body>` after "Check and import" or "Start a new import" replaces the focused button.
- **Stack:** `RUN=/tmp/claude-1000/pw4` was stopped (`stack-down.sh`; ports 8003 and 3003 free). Its schema `ppor_demo_w3web_1109024125` stays in `pantrypulse_web_test`.
- **Gates since the merge:** none re-run. The merge brought no web changes. Before the merge: vitest 24 files and 137 passed; tsc and eslint exit 0.
- **Exact next step:**
  1. Run `RUN=/tmp/claude-1000/pw5 apps/web/tests/e2e/connected/stack-up.sh`, then `npm run build` in `apps/web`, then `PP_E2E_PRODUCTION=1 RUN=/tmp/claude-1000/pw5 apps/web/tests/e2e/connected/run-e2e.sh --workers=1`. This is the whole suite on the new bridge, including the new A10 sample-values test. Load `.env.lane` in every shell.
  2. W3-W03: `npx playwright test tests/e2e/v1-a11y.spec.ts tests/e2e/import-upload.spec.ts --workers=1` (mocked) → RED → fix in `apps/web/src/**` → GREEN. Then update this file, commit, push.
  3. Finish: quick and full gates (`PP19_TEST_SCHEMA_ISOLATION=1`), `/devkit:ship-check` with the verifier, then the PR into `v1-local`.

### W3-W03 (2026-11-09)

- **Spec (`tests/e2e/v1-a11y.spec.ts`, `@V1-A20`):** the import, decisions and atlas ranking screens, plus the shell controls on them (the network switcher, and the navigation drawer on a phone), at 1440×900, 1280×720 and 390×844.
  - Each test drives its screen with the keyboard only, with no `click`, `fill`, `check` or `focus()`.
  - axe must report zero violations of any impact: the shared helper's serious/critical gate, and no `a11y-advisory` annotation for the label.
  - Motion: with `prefers-reduced-motion: reduce`, a recorder installed before the page's scripts sees no CSS animation, transition, `animate()` call or inline-transform sequence that moves, scales or resizes anything, and nothing infinite.
  - A live check proves the recorder works: with motion allowed, it records the switcher opening.
- **RED:** the first connected run had 194 passed and 8 failed. The import and decisions tests failed at every viewport. Probes showed the cause:
  - focus dropped to `<body>` when the focused "Check and import" or "Export CSV" button became `disabled` while busy;
  - focus also dropped when "Start a new import" removed itself.

  The shell test then failed in two ways. axe reported `aria-hidden-focus` (serious) with the switcher open: Radix Select hides the app with `aria-hidden` only, and axe excuses that only under a modal dialog (`focusable-modal-open`), not a listbox. The Radix enter/exit animations (`zoom-in-95`, slides) also ran under reduced motion: no rule in `tw-animate-css` or `globals.css` covers them.
- **Fixes:**
  - Busy buttons keep focus: they get `aria-disabled` and ignore activation. The unit test now checks that a second press creates no second import.
  - "Start a new import" moves focus to the "3. Upload your files" heading (`tabIndex={-1}`, the `location-inspector` convention).
  - `ui/select.tsx` `InertOutside` marks the elements Radix hid as `inert` while a list is open, and focus still returns to the trigger.
  - `motion-reduce:animate-none!` on dialog, popover, select, sheet and tooltip. It needs `!`, because the `data-[state=open]:animate-in` selector outranks it.
- **Connected-run failures fixed on the way, each RED first:**
  - **Sign-in dialog closed by itself.** This failed `data-explorer`'s connected sign-in, and caused the earlier "flaky" presenter-session 390×844 test. The W3-W02 overview returned a different shell for "loading networks", the v1 overview and the legacy atlas, so React remounted the whole shell when the network list settled. That closed an open sign-in dialog or phone drawer. Two fixes:
    - `NetworkProvider` derives "signed out" from the presenter session in the same render, and no longer requests the list for a visitor, who would only get a 401.
    - The overview renders every state through one shell: `LegacyAtlas` takes a `body`.
    - New mocked tests: the dialog and its typed username survive the list settling, and a presenter's phone drawer stays open. Both went RED, then GREEN; presenter-session is 50/50 over 10 repeats.
  - **`@V1-A10` offline enrichment stayed "running".** Settings followed a lookup job only after "Retry lookups". A status read during the import's own job, which ends about 1.5 s after the import, never refreshed; earlier runs passed only because the job usually ended first. Settings now follows any running job it reads, and a job is never followed twice. Unit test RED, then GREEN.
- **CR-w3-samples-1 end to end:** the `@V1-A10` sample-values test (`8897020`) passed in both connected runs. A seeded sample network's P1–P3 read "Source: sample values"; a normal import's read "Source: entered by you".
- **Quick gate during the first connected run:** the Stop hook's run failed `api tests` with 2 failures while the 14-minute connected e2e run shared the machine and `pantrypulse_web_test`. Run alone, the API suite gives 1955 passed, 77 skipped, exit 0, and the quick gate above is exit 0. Gates and the connected suite now run one at a time.
- One `overview-layout` "grip handles" failure appeared once in a 13-file parallel mocked run; it passed 5 of 5 alone and 27 of 27 over 3 parallel repeats.

## Decisions made inside the lane

- Connected fixtures are lane-owned CSV sets in `apps/web/tests/e2e/fixtures/v1-connected/` (`pantry`, `bad`, `unlocated`), fictional, with fixed dates (as_of 2026-11-04). `pantry` follows the backend `mini-network` fixture and adds routes, inbound and donation files. — W3-W01
- "Nothing saved" in A07 is checked in the database, not only in the UI: a read-only digest of every row of `networks`, `dataset_versions`, `net_locations`, `net_products`, `net_batches` before and after (`connected/db_probe.py`, same idea as the W2-05 journey's stock snapshot). — W3-W01
- The A10 test requires `PP_E2E_NO_EGRESS=1` and fails loudly without it, instead of skipping (CI rejects skips) or calling the real Census geocoder. — W3-W01

## Gotchas

- AF_UNIX socket paths are capped at 107 bytes; the session scratchpad path is too long, so `RUN` must be short (a symlink works). — W3-W01
- The worker's step children get an allowlisted environment (`process_driver.py:26`), so proxy variables can't make enrichment offline; only a network namespace (or a firewall) does. — W3-W01
- The API allows 5 presenter logins per minute per address (`apps/api/app/services/presenter_access.py:91-106`). A rejected login never reloads the page, so a helper waiting for "load" hangs until the test timeout (15 min here). The connected helper now signs in once per worker, reuses the cookies and fails in 30 s. CI's connected step runs every spec, so other specs' logins count toward the same limit. — W3-W02
- A failed sign-in's Playwright `error-context.md` records the password textbox value, and CI uploads `apps/web/test-results/` as an artifact. The credentials are generated per run, but every connected spec now signs in through `tests/e2e/sign-in.ts`, which clears the field on failure (lead item 3). — W3-W02
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
