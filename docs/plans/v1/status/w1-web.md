# Status — `w1-web`

**Lane:** `w1-web` · **Branch:** `lane/w1-web` · **Base SHA:** `39090104222e6a67b60f8d9fa0c9e798c68a38d7` · **Last update:** `2026-11-07` · **Head:** see `git log`

Mocked e2e runs prove UI behavior against the contract examples in `packages/contracts/examples/v1/`, not the connected app.

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W1-W01 | done | `a79162b` (cherry-pick 647f6a8) + test port commit | `npm run test:unit --workspace @pantrypulse/web` → Vitest 6 files / 47 passed; node --test 11 passed, 0 skipped (includes `forecast-proxy.test.mjs`). Screenshots `artifacts/w1-web/647f6a8-1440x900.png`, `647f6a8-390x844.png` (artifacts/ is gitignored). |
| W1-W02 | done | see `git log` (W1-W02) | `npx vitest run tests/unit/mode-vocabulary.test.ts` → 2 passed; `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/v1-shell.spec.ts` → 3 passed (mocked, `NetworkList` example). Full mocked suite → 151 passed, 6 skipped (pre-existing `PP_RUN_CONNECTED` connected tests, not evidence). `tsc --noEmit` and `eslint` clean. |
| W1-W03a | done | see `git log` (W1-W03a) | `npx vitest run tests/unit/template-guide.test.tsx` → 3 passed; `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/import-templates.spec.ts` → 1 passed (mocked `TemplateCatalog`; example download mocked as the 501 `NOT_IMPLEMENTED` W3-P03 envelope). |
| W1-W03b | done | see `git log` (W1-W03b) | `npx vitest run tests/unit/import-errors.test.tsx` → 8 passed; `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/import-upload.spec.ts` → 5 passed (@V1-A07, @V1-A23, @V1-A20 keyboard + axe at 1440×900, 1280×720, 390×844; mocked import flow from the Import* contract examples). Screenshots `artifacts/w1-web/import-*.png`. |
| W1-W04 | done | see `git log` (W1-W04) | `npx vitest run tests/unit/google-key-form.test.tsx` → 4 passed; `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/enrichment.spec.ts` → 3 passed (mocked EnrichmentStatus, LocationAttributes, RouteList, LocalSettings, GoogleLookupPreview, ForecastAccepted). |
| W1-W05 | done on mocks (map placement and inspector added after #103) | see `git log` (W1-W05; step 3 of the resume) | `npx vitest run tests/unit/danger-ranking.test.tsx` → 5 passed. After #103: `npx vitest run tests/unit/location-map.test.ts tests/unit/location-inspector.test.tsx` → 4 passed (RED first: the modules did not exist); `node --test tests/forecast-proxy.test.mjs` → 12 passed (RED first: `locations` was 404); `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/atlas-ranking.spec.ts` → 6 passed (@V1-A13 table alternative, @V1-A13 selecting a row opens the site inspector, @V1-A13 placement by coordinates, @V1-A20 axe on list, inspector and table at 1440×900, 1280×720 and 390×844; mocked `DangerRanking`, `LocationList`, `LocationProjection`). The projection route is a 501 stub until W3-F05, so the inspector is proven on mocks only. |
| W1-W06 | done, except method/fallback/donations from a live run (CR-w1-web-4) | see `git log` (W1-W06) | `npx vitest run tests/unit/trust-panel.test.tsx` → 6 passed; `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/forecast-trust.spec.ts` → 1 passed (mocked `BacktestResult`). RED was not run before implementing; instead a mutation check (bias sign flipped, quantile check removed) failed 2 of 6 unit tests, and they passed again after restoring. |
| W1-W07 | done (window picker and policy added after #103) | see `git log` (W1-W07) | RED run first: unit 6 failed, e2e 2 failed. After: `npx vitest run tests/unit/method-comparison.test.tsx` → 6 passed; `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/v1-comparison.spec.ts` → 2 passed (A14 both transfer modes + axe, A15 units and USD); `npx vitest run` → 81 passed; `scenario-lab.spec.ts` + `recommendations*.spec.ts` → 33 passed, 2 skipped (both connected-only, `PP_RUN_CONNECTED`). research-claims-check on the new EGP copy (`results.tsx` method card): PASS — "inspired", DOI, no reproduction or outcome claim.  After #103: `npx vitest run tests/unit/method-comparison.test.tsx tests/unit/v1-comparison.test.tsx` → 7 RED first (no window radio, no `DEFAULT_PANTRY_POLICY`), then 12 passed; `v1-comparison.spec.ts` → 2 passed (Pantry posts `planning_days: 3` and the contract policy; Retail posts neither). |
| W1-W08 | done (effect lines in the product's unit since #105, CR-w1-web-5) | see `git log` (W1-W08) | RED run first: unit import failed, e2e 5 failed. After: `npx vitest run tests/unit/action-card.test.tsx` → 5 passed; `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/decisions.spec.ts tests/e2e/v1-comparison.spec.ts` → 7 passed (A16 CSV download + print rows, A20 keyboard/axe/reduced motion at 1440, 1280 and 390); `npx vitest run` → 86 passed; eslint and `tsc --noEmit` clean. research-claims-check: no research or outcome copy added (only "Proven: binding constraint" / "Inferred reason" and the simulated-plan note). |

### W1-W01 port record

Ported unchanged from `b54ec7c`: `atlas-layout.test.ts`, `network-atlas.test.tsx`, `site-inspector.test.tsx`, `static-fixture.test.ts`, `status.test.ts` (plus a `// covers: V1-A21` first line). Not ported: `outlook.test.ts`, `outlook-chart.test.tsx`. First run: 18 failed / 29 passed. Test-side changes (no component edits):

- `static-fixture.test.ts` (8 failing): `overviewSourceFor` moved from `static-fixture.ts` to `sources.ts`, and its default is now `liveWithFallbackSource` (PP-51 `eb7cbaf`). Import from `sources`; expect the live-with-fallback default.
- `network-atlas.test.tsx` (4 failing): same move; spy on `sources.overviewSourceFor`.
- `static-fixture.test.ts` (tsc only, found in W1-W02): projection stock fields became nullable for live data → the test now fails loudly if the fixture has a null instead of using it unchecked.
- `site-inspector.test.tsx` (6 failing): `SiteInspector` gained a required `provenance` prop (`9d66945`) → pass the fixture provenance. Tab content now crossfades from opacity 0 (`16c47d7`), which jsdom never animates → mock `useReducedMotion` to `true`, a path the component already supports.

Visual check of 647f6a8: at 1440×900 the builder panel is 24rem and step-1 controls fit without wrapping; at 390×844 the layout is a single column. Pre-existing, unrelated: the full-page 1440 capture shows the fixed sidebar ending at the viewport height (screenshot artifact), and at 390 the "Simulated research preset" select sits a few px wider than its siblings.

## Resume (2026-11-07): verifier rerun and fixes

The verifier was rerun on ce7d7df (budgeted to report). It confirmed all 10 pause-point findings and added N1–N4. Unit 88 passed and v1 e2e 25 passed at ce7d7df.

Fixed test-first (each new test was run RED first, for the right reason):
- Finding 1: `lastHistoryDate` accepts only real calendar days. `2026-13-45`, `2026-11-31`, `2026-00-10` and `9999-12-31` no longer reach `dayAfter`.
- N2: only the latest scan sets the default date; Start a new import cancels a pending scan.
- N1: a failed status read after an accepted commit says "Lost contact with the import… It may still finish" and offers Check again, instead of "Nothing was saved". (commit 35bdcb9)
- Finding 2: an evaluated score with no WAPE says "accuracy not measurable: no recorded demand on the scored days" and keeps its bias.
- Finding 6: `send`/`apiText` refuse any `.`/`..` (also `%2e`) path segment, so no caller can be redirected. `encodeURIComponent` leaves dots alone, so this guard is the actual fix.
- Finding 4: Decisions shows no actions or export for a missing or unverified method result, and says why.
- Finding 3, part: the print page shows the network name and "Sample data — fictional". The capacity and inbound notes need CR-w1-web-6.
- Finding 8 / N3: the settings locations and routes remount per network, so a switch starts from loading and an attribute save can't target the old network's location.
- Nits: 7 (`Object.hasOwn`), 10 (`Select value ?? ""`; no controlled/uncontrolled warning in the import e2e), N4 (a freeze clears the previous frozen scenario first).

Not fixed:
- Finding 5: needs CR-w1-web-6.
- Finding 9: the untagged test title matches the wave-1 plan.
- `@V1-A13 selecting a row opens the site inspector`: waits for #103 (CR-1/CR-3).

## PR #104 review (2026-11-07): `/code-review medium 104`, recorded here only, no PR comments

The review read the `apps/web/src` diff at 231c70f and reported 10 unverified findings. Each one was checked against the code before any fix. These were fixed test-first, with each new test run RED first:
- 1. During the import "lost" state, "Check and import" is disabled, so a retry can't commit a second copy.
- 2. A failed job read after the comparison was accepted now says "Lost contact with the comparison job… check again before comparing again". Check again resumes polling the same job, and Freeze and Compare are disabled meanwhile. Before, the job id was dropped, and a second Compare queued a duplicate job.
- 3. The enrichment retry and Google fetch copy promised live updates, but nothing polls. `GET /jobs/{id}` serves only forecast and OR job kinds (forecasts.py:227-233 on v1-local). The copy now says to reload the page after the job finishes.
- 6. Both Decisions reads are scoped to the sidebar network, so another network's comparison comes back 404. It now says "Comparison not found in X. If it belongs to another network, choose that network in the sidebar."
- 7. Forecast trust remounts per job id, so a new job starts from loading instead of showing the previous job's accuracy.
- 8. The server's `RetailWeights` are strict integers from 0 to 1000 (v1_planning.py:189-191). The client accepted `1.5` and `1001`, and now says "Enter a whole number from 0 to 1000."

Cleanups with no behavior change, covered by the existing tests:
- 5. The CSV link is attached to the document, and the blob URL is kept for 60 s.
- 9. `apiText` reuses `send`.
- 10. A redundant ternary in the trust panel is removed.

Not fixed:
- 4. The unit of an effect stays CR-w1-web-5. v1-local has no scenario read, and Decisions has no ScenarioV3 to take product units from.
- 8, second half. Both weights 0 is valid on the server but makes the Optimized objective constant. V1-SPEC §6.2 is silent on this, so it is escalation E-1.

## Step 3 after #103 (2026-11-07)

`git merge origin/v1-local` (f0e559c, no rebase) merged cleanly as cd47da9. tsc was clean and Vitest passed 98 on the merged tree before any change. Then, test-first:
- Pantry planning window and policy (2de6536). Pantry must pick 1, 2 or 3 days (no default). λ, β and the poverty/SNAP shares start at `DEFAULT_PANTRY_POLICY` and are editable. Each is a whole number from 0 to 100, and the two shares must add up to 100. The scenario POST carries `planning_days` and the full `policy`. Retail sends neither field, and the frozen scenario line shows "Window 3 days · λ 100% · β 50% · poverty rate 50%, SNAP rate 50%".
- LocationList and the site inspector (be99c71). The proxy now allows `GET networks/{id}/locations` and `GET networks/{id}/projection` (query keys `forecast_run_id`, `location_id`, each at most once). The ranking shows "Archer Road Pantry (P-12)". Located sites are placed on a schematic map, and a site without coordinates is listed under "Not on the map (no coordinates)". Selecting a ranked row or a map marker opens the inspector on `LocationProjection`, and closing it returns focus to the row or marker that opened it.

## Batch 2 after #105 (2026-11-07)

`git merge origin/v1-local` (298880d, #105, no rebase) merged cleanly as e9805ab. tsc was clean and Vitest passed 107 on the merged tree. Then, test-first. Each new test was run RED first, for the right reason:
- CR-w1-web-5: effect lines and print rows use `ActionEffect.unit` ("Receiver unmet need: 40 cases lower"). The print page's "units as in the plan" stopgap is gone.
- CR-w1-web-6: /decisions and /decisions/print show "Plan notes", taken from `SavedComparisonV3.assumptions`, plus "no scheduled deliveries provided" when `inbound_file_provided` is false. The atlas danger section and the forecast trust section show "Scheduled deliveries: no scheduled deliveries provided…" only when `Network.inbound_file_provided` is false. When it is null (no dataset yet), they show nothing.
- CR-w1-solver-5 follow-up (PR review finding 3): settings re-reads the locations or routes when an `enrichment.v1` or `routes-google.v1` job ends. It polls `GET /jobs/{id}` every 2 s; if that read fails, it re-reads anyway. The copy again says "This list updates when they finish." / "Route labels update when the job finishes." `JOB_ENDED` (network-api.ts) is now shared with the comparison poll.
- Evidence: `npx vitest run` → 22 files, 110 passed. e2e `decisions.spec.ts`, `atlas-ranking.spec.ts`, `forecast-trust.spec.ts` → 16 passed; `enrichment.spec.ts` + `v1-comparison.spec.ts` → 5 passed. tsc and eslint clean.

## Pause point (2026-11-07, at Gabriel's request via the orchestrator)

**Done:** W1-W01 … W1-W08 committed and pushed. The reviewed candidate is b2f32ec; this commit adds only this file. Partial items, each with a CR or waiting on the v1-local merge (#103):
- W1-W05: map placement and the site inspector (CR-1/CR-3).
- W1-W06: method/fallback/donation rows from a live run (CR-4).
- W1-W07: the Pantry window picker and editable policy (ScenarioV3 merge).
- W1-W08: effect lines in the product's unit (CR-5).

**Gates at b2f32ec** (see Gates above for commands):
- quick PASS; full PASS (both with `PP19_TEST_SCHEMA_ISOLATION=1`).
- Backend: 1413 passed, 0 skipped (`require-test-evidence.py` OK).
- Vitest: 88 passed in 15 files.
- Playwright, whole suite: 173 passed, 6 skipped (all `connected:`).

**Ship-check:**
- Step 1 (project checks): PASS, as above.
- Step 2 (`verifier` review of b2f32ec): in progress at the pause. It hit its turn limit, then gave a partial report, recorded here and **not acted on**.
  - Its own runs: vitest 88 passed; the 8 v1 e2e specs 25 passed, 0 skipped.
  - Verdicts:
    - PASS: A05, A06, A07, A08, A10, A11, A14, A15, A20, A21, transfer labels, EGP copy, quantile wording, units never summed.
    - FAIL (partial): A12 (CR-4 plus finding 2), A16 (findings 3, 4), A23 (finding 5), path traversal (finding 6).
    - UNVERIFIED: A13 placement and inspector (CR-1/CR-3).
  - Findings:
    1. should-fix, reproduced in node, not yet in a browser: `lastHistoryDate` accepts an impossible date such as `2026-13-45`, and `dayAfter` then throws `RangeError` during render (network-settings.tsx:16,28,57,94).
    2. should-fix: trust-panel.tsx:62-68 says "accuracy not evaluated: needs 35+ days" for an *evaluated* score with null WAPE, and hides its bias.
    3. should-fix: the print page lacks "capacity not provided — no limit assumed", "no scheduled deliveries provided" and the sample label (V1-SPEC §6.1, §8).
    4. should-fix: decisions-view.tsx renders actions for an unverified or missing method result.
    5. should-fix: "no scheduled deliveries provided" shows only on the import summary, not on the atlas or forecast views; the Network contract has no inbound flag, so this needs a CR.
    6. should-fix (low): `?forecast_job_id=..` stays `..` after `encodeURIComponent`, and the browser normalizes it to `GET /api/v1/backtest`. Apply `isUuid` on /data and /overview ids.
    7. nit: `isV1Method` uses `in` (`method=constructor` passes).
    8. nit: settings `useLoad` doesn't reset to loading when the network changes.
    9. nit: v1-shell.spec.ts:41 title lacks an @V1-Axx tag.
    10. nit: the network Select switches between controlled and uncontrolled.
  - Not checked by the verifier: W1-W01 screenshots, the 647f6a8 visual, test names against each Step 1 list, the connected app.
- Step 3 (security): the automated MEDIUM path-traversal finding was fixed in b2f32ec; verifier finding 6 is a residual of it.
- Steps 4–6 (commit/PR, PR review, second opinion): not started.

**Next steps on resume, in order:**
1. Re-read or re-run the verifier on the current head.
2. Fix findings 1–4 and 6–10 test-first; file a CR for 5. Re-run quick, full and the full Playwright suite one at a time, nothing else running.
3. Open the PR `lane/w1-web → v1-local` (title "w1-web: every new v1 screen, against contract mocks"; body ends with the 🤖 line only, no Claude-Session or Co-Authored-By lines), then run `/code-review` on it.
4. When #103 merges: `git fetch && git merge origin/v1-local` (no rebase). Then wire LocationList (atlas placement, names) and add its GET to the proxy allowlist. Build the inspector on LocationProjection mocks, and the Pantry window picker and policy on the merged ScenarioV3. Re-run focused tests and the quick gate, then push.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` (standard env) | 71b116a | PASS (4 of 4). The api step ran 1394 passed and 77 skipped, all in the same eight PostgreSQL isolated-schema suites as at be99c71 (`pytest -q -rs`). |
| `node scripts/quality/run.cjs full` (`.env.lane` + `PP19_TEST_SCHEMA_ISOLATION=1`) | 71b116a | PASS (8 of 8) |
| `uv run --frozen pytest -q --junitxml=…` + `require-test-evidence.py` | 71b116a | 1471 passed, 0 skipped; "1471 backend tests completed without skips or failures" |
| `npx vitest run` / `node --test tests/*.test.mjs` | 71b116a | 22 files, 110 passed / 12 passed, 0 skipped |
| `PLAYWRIGHT_PORT=3003 npx playwright test` (whole suite, alone) | 71b116a | 178 passed, 6 skipped: the same six seeded-backend specs |
| `node scripts/quality/run.cjs quick` (standard env: `.env.lane`, no `PP19_TEST_SCHEMA_ISOLATION`) | be99c71 | PASS: web typecheck, web lint, api lint, api tests. The api step ran 1374 passed and 77 skipped. All 77 are the PostgreSQL isolated-schema suites that need the opt-in: `test_operational_postgres.py` (25), `test_stock_postgres.py` (17), `test_stock_adjustment_api_postgres.py` (9), `test_operations_api_postgres.py` (7), `test_forecast_api_postgres.py` (6), `test_inventory_api_postgres.py` (5), `test_planning_api_postgres.py` (4) and `test_planning_postgres.py` (4), all under `tests/integration/` (`pytest -q -rs`). |
| `node scripts/quality/run.cjs full` (`.env.lane` + `PP19_TEST_SCHEMA_ISOLATION=1`) | be99c71 | PASS: web typecheck, web lint, api lint, api tests, web unit tests, web build, contract drift, database migrations |
| `uv run --frozen pytest -q --junitxml=…` + `scripts/quality/require-test-evidence.py` (same env, lane DB) | be99c71 | 1451 passed, 0 skipped; "1451 backend tests completed without skips or failures" |
| `npx vitest run` / `node --test tests/*.test.mjs` (apps/web) | be99c71 | 21 files, 106 passed / proxy 12 passed |
| `PLAYWRIGHT_PORT=3003 npx playwright test` (apps/web, whole suite, nothing else running) | be99c71 | 177 passed, 6 skipped: the same six seeded-backend specs (five `connected:` titles plus `operations-api.spec.ts`, which needs `PP_RUN_CONNECTED=1`); none is a v1 lane spec |
| research-claims-check on the new copy (policy hints, inspector) | be99c71 | PASS. "EGP-PI-inspired" is named as such, with no outcome or reproduction claim. The inspector says "Forecasts are projections" and shows unknown values as "unknown". |
| `node scripts/quality/run.cjs full` (with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1`; its steps include all of quick's) | 12bf028 | PASS: web typecheck, web lint, api lint, api tests, web unit tests, web build, contract drift, database migrations |
| `uv run --frozen pytest -q --junitxml=…` + `scripts/quality/require-test-evidence.py` (apps/api, same env, lane DB `pantrypulse_web_test` on 127.0.0.1:55433) | 12bf028 | 1413 passed, 0 skipped; "1413 backend tests completed without skips or failures". Without `PP19_TEST_SCHEMA_ISOLATION=1`, 77 PostgreSQL isolated-schema tests skip. |
| `npx vitest run` (apps/web) | 12bf028 | 17 files, 94 passed |
| `PLAYWRIGHT_PORT=3003 npx playwright test` (apps/web, whole suite, nothing else running) | 12bf028 | 174 passed, 6 skipped — all six are `connected:` specs needing the seeded backend (`PP_RUN_CONNECTED=1`); none is a v1 lane spec |
| Earlier candidate b2f32ec | b2f32ec | quick PASS, full PASS, backend 1413/0 skipped, Playwright 173 passed / 6 connected-only skipped |
| `/devkit:ship-check` | 12bf028 | Step 1 PASS (above). Step 2: verifier rerun on ce7d7df, its should-fix findings fixed in 35bdcb9 and 12bf028 (finding 5 and part of 3 → CR-w1-web-6). Step 3: the security-review finding was fixed in b2f32ec, with its residual (finding 6) fixed in 12bf028. Steps 4–5 (PR, `/code-review`) wait for Gabriel's approval to open the PR. |

## Decisions made inside the lane

- Network switcher lives in the sidebar header (V1-SPEC §14 leaves header-vs-page to the builder): it is on every screen and goes off-canvas on mobile with the nav. The chosen network id is kept in `localStorage` as a per-browser convenience; it falls back to the first listed network. — W1-W02
- Stock-changing Data Explorer subviews (Operations Board, Inventory & Lots, Data input) are filtered out of the tab strip by a `stockChanging` flag in `tabs.ts`; their pages, in-page links and API stay (V1-SPEC §8). — W1-W02
- Template downloads are plain same-origin links (`download` attribute). When `example_available` is false the page reads the example route's error envelope once and shows its message and task beside a disabled button. — W1-W03a
- `as_of_date`: the import page scans the chosen `demand_history.csv` in 4 MB chunks for its latest `date`, shows the day after it as an editable default, and sends what is shown. If the scan finds no date it sends nothing and the job defaults it (decision W0-08). — W1-W03b
- Re-import: when the switcher's network is a non-sample network, the import page offers "A newer snapshot of <network>" (`{network_id}`); mode and timezone stay fixed. — W1-W03b
- Polling `GET /imports/{id}` every 1 s until `done`/`failed`; on `done` the switcher reloads and selects the new network. A failed import keeps the settings; "Start a new import" clears every file input (all files are checked again from the start). — W1-W03b
- `/settings` (sidebar footer link, now built): write-only Google key form, then the chosen network's enrichment (lookup state, retry, unmatched addresses, EGP blocker banner, per-location attribute editor with source line) and routes (method labels, Google fetch behind a lookup-count dialog). The key input is uncontrolled, so the key never enters React state or a DOM attribute (React mirrors controlled `value` into the attribute). — W1-W04
- Attribute values are sent as typed decimal strings (`"0.25"`), validated client-side as a share in [0, 1]; the API accepts number or string. — W1-W04
- Danger ranking is its own section on `/overview` for the chosen v1 network, never merged into the demo atlas snapshot (fixture and v1 data are never mixed). Bands: high = diamond, medium = triangle, low = open circle, each with a text label and a legend. Retail rows show the score's reason. — W1-W05
- The v1 site inspector is a new `LocationInspector` (`overview/location-inspector.tsx`), not the V5 `SiteInspector`. The V5 one is typed to the demo snapshot (one product and one day at a time, with V5 statuses), while `LocationProjection` gives every product's 7 days. The inspector follows the same pattern: name, role, provenance line and per-product facts. Each product is its own table in its own unit, `null` shows as "unknown", and a missing series says "not available for X". Nothing is added across products. — W1-W05 (after #103)
- Map: one uniform-scale equirectangular projection of the located sites in a 16:9 frame, with no basemap or tiles (V1-SPEC §6.6 allows a schematic projection). Markers are 24 px buttons showing the band shape, or a square for "not ranked", and carry no visible label; names are in the ranking and in each marker's accessible name. Sites without coordinates are listed and not placed. They can't be opened from that list, but a ranked one opens from its row. — W1-W05 (after #103)
- Forecast trust is a section on the `/data` dashboard for the chosen v1 network (`?forecast_job_id=` until CR-w1-web-2). `forecast-chart.tsx` was not changed: it already draws the p10–p90 band only for a single-site series with model quantiles, and says why otherwise. Bias wording follows V5 §7 (error = prediction − actual, so positive bias = "forecast too high"). — W1-W06
- The top-bar "Simulated network" pill is unchanged: the existing screens still read the demo network until they are rewired to v1 networks. — W1-W02

- v1 method comparison is a new section at the top of Scenario Lab for the chosen network (`?forecast_run_id=` until CR-w1-web-2), built from `ComparisonSetup` (wizard.tsx), `MethodComparisonResults` (results.tsx), `MethodVerification` (recommendations/vocabulary.tsx) and the flow in `scenario-lab/v1-comparison.tsx`. The v2 stepper and results below it are unchanged, so their specs still hold. `recommendations-screen.tsx` was not changed: v1 actions come from the Decisions page (W1-W08). API calls went into `lib/network-api.ts` with the other v1 calls rather than `planning-api.ts`. — W1-W07
- The comparison job's `result_url` is read as the path of `GET networks/{id}/comparisons/{comparison_id}` (the contract gives no other link from job to comparison). A requested method missing from the saved result shows "No result returned for this method."; nothing is filled in. Effects stay per location × product in each product's unit; the per-method `objective` is not shown, since there is no network-wide objective total. USD availability is computed from the frozen scenario's `unit_value_usd` and names the unpriced products; Retail must pick a measure, Pantry is units only. — W1-W07

- Decisions (`/decisions?comparison_id=&method=`) start from a verified method result: Scenario Lab links each verified method with transfers to it. Selection starts empty; the CSV is the server's export (`POST …/export` text) saved byte-for-byte as `pantrypulse-plan-<comparison 8>-<METHOD>.csv`; the print page (`/decisions/print?network_id=&comparison_id=&method=&actions=`) re-reads the same comparison and actions and shows the selected rows with full scenario ID and hash, the simulated-plan note and the non-additive label. No total or combined effect is computed anywhere. An effect delta is read as plan minus plan-without-this-transfer (negative = lower). Pantry shows no USD line; Retail shows the USD delta or "USD effect unavailable: <reason>". — W1-W08
- The Pantry policy defaults come from `DEFAULT_PANTRY_POLICY` on the server. The client keeps a copy (`scenario-lab/model.ts`), and a unit test pins it to the frozen `ScenarioV3` example. The full policy is always sent, so the scenario freezes exactly what the screen showed. Only λ, β and the two shares are editable: V1-SPEC §6.2 names those. Thresholds, caps, γ and ε keep the connected flow's values. — W1-W07 (after #103)
- CR-w1-solver-5 approved (lead, 2026-11-07): `GET /api/v1/jobs/{job_id}` keeps its URL and will answer for v1 jobs (`or-comparison.v3` and the other v1 kinds), resolving the job's network organization on the server. No client change: the comparison flow polls `jobs/{job_id}`, the same path as the `status_url` the submit returns (`ForecastAccepted.json`). Follow-up once it lands: if enrichment and Google route jobs are among those kinds, the settings page can poll them instead of saying "Reload this page…" (PR review finding 3). — W1-W07
- Lead call (2026-11-07): a v1 comparison's `comparison_id` is the comparison job's `job_id`; `result_url` = `/api/v1/networks/{id}/comparisons/{job_id}`, which W1-W07 already follows. — W1-W08

- Security review (automated, MEDIUM, client-side path traversal): ids from the page URL went into API paths. Now every `networkApi` path segment is `encodeURIComponent`-ed, `/decisions` and its print page refuse non-UUID `comparison_id`/`network_id` before any request, and a comparison job's `result_url` is followed only when it matches `/api/v1/networks/<uuid>/comparisons/<uuid>`. The proxy allowlist already rejected non-UUID paths; this closes it in the browser too. Tests: `tests/unit/network-api.test.ts` (2) and the decisions e2e "ids that are not UUIDs are never sent to the API" (RED before, PASS after). — W1-W08

## Gotchas

- The full Playwright suite and the gates compete for CPU: run them one at a time. A Stop-hook quick gate started during the e2e run never reported its api step, and the e2e run had 8 timing failures; all passed when re-run alone. — finish
- `.env.lane` points the PostgreSQL test URLs at the lane DB, but the isolated-schema tests also need `PP19_TEST_SCHEMA_ISOLATION=1` (as CI sets it); without it 77 backend tests skip. — finish

- W1-W05's danger section broke 4 ported `network-atlas.test.tsx` tests (mocked shell, no NetworkProvider); I hadn't run the whole unit suite at W05/W06. Fixed test-side in its own commit. Run `npx vitest run` (all files) before each task commit. — W1-W07
- `recommendations.spec.ts › verified plan … at 1440x900` failed once in a 35-test batch and passed alone (3/3) and in a rerun of the batch (33 passed): another load-sensitive spec. — W1-W07
- Legacy Scenario Lab destructive alerts tint `code` and buttons below AA contrast; the load-failure alert now sets `text-foreground` on them (found by the A14 axe scan, which sees the legacy load failure under v1-only mocks). — W1-W07

- `overview-layout.spec.ts › panels move by their grip handles at 1440` timed out once (32.9 s) under a 4-spec parallel run and passed twice alone (7–10 s): likely load-sensitive; watch it in the full run. — W1-W05

- e2e runs `next dev` with `reactStrictMode: true`, so every mount effect fires its GET twice; the first result is dropped by its `active` flag. Assert what a GET asked for, not how many times. — W1-W05 (after #103)
- `useRef` "alive" flags must be set to `true` in the effect body, not only cleared in cleanup: dev Strict Mode runs the cleanup once before the real mount, which silently stopped the import poll loop. — W1-W03b
- `getByRole("combobox", { name: "Network" })` also matches "Network timezone"; use `exact: true`. — W1-W03b

- In Vitest's jsdom environment `import.meta.url` is not a `file:` URL; `tests/unit/contract-examples.ts` uses `__dirname` to read contract examples. — W1-W03a

- Every shell page now reads `GET /networks`. Older e2e specs with strict "unexpected request" mocks must answer it (done for `forecasting-integration.spec.ts` with the `NetworkList` example). — W1-W02

- Components that fade in with `motion` (`initial: { opacity: 0 }`) stay invisible in jsdom; unit tests must render under reduced motion. — W1-W01

## Change requests

### CR-w1-web-1 — a read that returns each location's name, type and coordinates
- **File(s):** `apps/api/app/schemas/v1_networks.py`, `apps/api/app/routers/v1_networks.py`, `packages/contracts/**` (lead-only)
- **Exact change:** add `GET /networks/{network_id}/locations` → `LocationList{network_id, dataset_version_id, locations: [LocationSummary{location_id, name, type, city, state, latitude: str | null, longitude: str | null}]}` for the network's current dataset version (coordinates as decimal strings; null when geocoding failed), plus `examples/v1/LocationList.json`, and allow the GET in the Next proxy list (`apps/web/src/app/api/v1/[...path]/route.ts` is web-owned; I can add it once the route exists).
- **Why:** V1-SPEC §6.6 says the atlas places locations by real coordinates, but `DangerRow`, `EnrichmentStatus`, `RouteList` and `Network` carry only `location_id`; no frozen read returns names, roles or coordinates (checked `packages/contracts/src/schema.d.ts`). The ranking, decisions and trust panel can only show IDs.
- **Unblocks:** W1-W05 map placement (and names in W1-W06/W1-W08).
- **Status:** landed in #103 (f0e559c). The ranking, map and inspector use it on this branch. Names in W1-W06/W1-W08 are not wired yet.

### CR-w1-web-2 — a way to find a network's forecast runs
- **File(s):** `apps/api/app/schemas/v1_networks.py` (or a new forecasts read), `packages/contracts/**` (lead-only)
- **Exact change:** either add `latest_forecast_run_id: uuid | null` (with its `dataset_version_id`) to `Network`, or add `GET /networks/{network_id}/forecasts` → `[{forecast_run_id, job_id, dataset_version_id, recorded_at, state}]`.
- **Why:** `GET /networks/{id}/danger` requires `forecast_run_id`, and `GET /forecasts/{job_id}/backtest` a job id, but the only place either appears is the 202 `ForecastAccepted` from `POST /networks/{id}/forecasts`. After a reload the UI cannot find the run. Interim in this lane: `/overview?forecast_run_id=` (the danger e2e uses it).
- **Unblocks:** W1-W05 without the URL parameter, W1-W06 backtest fetch.
- **Status:** frozen in #103 as `GET /networks/{id}/forecasts` → `ForecastRunList`, still a 501 stub (W3-F03). The web keeps `?forecast_run_id=` until it is built.

### CR-w1-web-4 — v1 forecast series result, and a per-location accuracy roll-up
- **File(s):** `packages/contracts/examples/v1/` + forecast schemas (lead-only; service in w3-forecast)
- **Exact change:** (a) name the read that returns a `forecast.v1` network run's series and add its example, keyed by v1 `location_id`/`product_id`, with `basis`, `actual_provider`, `fallback_used`, `fallback_reason`, `diagnostics.missing_count`, `points` (p10/p90 only from quantile providers) and the donation forecast per location × product; (b) add per-location WAPE/bias to `BacktestResult` (e.g. `locations: [{location_id, score: BacktestScore}]`) computed on the pooled scored set.
- **Why:** V1-SPEC §6.4 requires method, fallback reason, missing days, quantile band and "rolled up per location". `BacktestResult` has only per-series scores, and WAPE percentages can't be averaged into a per-location figure without the underlying sums. The existing `ForecastSeriesResult` is keyed by v2 UUIDs, and no v1 example exists. `TrustPanel` already renders all of it from `ForecastSeriesResult` fields (unit-tested with a typed subset, since no example exists).
- **Unblocks:** W1-W06 method/fallback/donation rows on the live page; the per-location roll-up.
- **Status:** deferred to the W2 contract pass, together with the forecast-run interface for W3 (lead, 2026-11-07). Until then the trust panel stays on mocks. The gap: the live `/data` page shows only the backtest's per-series basis and score. It has no method, fallback reason, missing days, quantile band or donation forecast per series, and no per-location roll-up.

### CR-w1-web-5 — the unit of an action's effect
- **File(s):** `ActionEffect` schema + `DecisionActions.json` (lead-only)
- **Exact change:** add `unit` (the product's unit, e.g. "case") to `ActionEffect`, or the product's `name` and `unit`.
- **Why:** V1-SPEC §6.5 shows the effect at sender and receiver in units; the decisions page only has `product_id`, so it writes "40 units lower" and "Product WATER-24; units as in the plan" instead of "40 cases lower". There is no scenario read to look the unit up.
- **Unblocks:** W1-W08 effect lines and print rows in the product's own unit.
- **Status:** approved (lead, 2026-11-07) and landed in #105. Wired on this branch (batch 2 after #105).

### CR-w1-web-6 — plan notes for Decisions/print, and an inbound flag for the atlas and forecast views
- **File(s):** `SavedComparisonV3` (or a new `GET networks/{id}/scenarios/{scenario_id}` → `ScenarioV3`), `Network`, their examples (lead-only); the CSV export (W1-S07)
- **Exact change:** (a) give the Decisions and print pages the frozen scenario's `assumptions` and `inbound_file_provided`: add both to `SavedComparisonV3`, or add the scenario read. (b) add `inbound_file_provided: boolean` (latest dataset version) to `Network`. (c) the server's plan CSV carries the same notes.
- **Why:** V1-SPEC §6.1 says every plan export shows "capacity not provided — no limit assumed" and, without `inbound.csv`, "no scheduled deliveries provided"; the atlas and forecast views show the latter too. The web only has these on the frozen scenario inside Scenario Lab (`ScenarioV3.payload.assumptions` / `inbound_file_provided`); a deep-linked Decisions or print page and the atlas/forecast views have no source, and the UI must not guess. Verifier findings 3 (rest) and 5.
- **Unblocks:** the two notes on /decisions, /decisions/print, the atlas and the forecast trust section.
- **Status:** approved (lead, 2026-11-07), with no new route. `SavedComparisonV3` gains the frozen scenario's `assumptions` and `inbound_file_provided`, `Network` gains `inbound_file_provided`, and the solver lane adds the notes to the plan CSV. Landed in #105, and the web side is wired on this branch (batch 2 after #105). The plan CSV notes belong to the solver lane.

### CR-w1-web-3 — per-location projection for the site inspector
- **File(s):** contracts + a networks/forecast router (lead-only; service in w3-forecast's area)
- **Exact change:** add `GET /networks/{network_id}/projection?forecast_run_id=&location_id=` → per product: `product_id, unit, dates[7], target[7], served[7], unmet[7], eligible_stock_now, expiring_unsold[7] | null, donation_forecast[7] | null` (null stays null).
- **Why:** V1-SPEC §6.6 "selecting a location opens the existing site inspector"; `SiteInspector` renders per-day target/served/unmet per product, and no v1 contract returns them (`DangerRow` has only the driving product).
- **Unblocks:** W1-W05 `@V1-A13 selecting a row opens the site inspector`.
- **Status:** frozen in #103 as `LocationProjection` (a 501 stub until W3-F05). The inspector is built and e2e-tested against the example.

### Contract example notes (no change requested)
- `ImportStatus.json`'s failure message names "North County Pantry Network", which `NetworkList.json` also lists as existing. The A07 e2e therefore mocks the before-import list without that network.
- `ScenarioV3.json`/`SavedComparisonV3.json` are Pantry only and hold 3 of the 5 Pantry methods. `v1-comparison.spec.ts` clones them into Retail (roles, prices, methods `SOONEST_EXPIRY_FIRST`/`RETAIL_OPTIMIZED`). There is no `ForecastJob` example; the finished job is built from `ForecastAccepted.json`'s identities.
- `TemplateCatalog.json` lists two of the seven templates; `import-upload.spec.ts` clones those two entries to stand in for the other five.

## Escalations

### E-1: Retail weights both 0 (resolved)
`RetailWeights` accepts `w_exp = 0` and `w_lost = 0` together (v1_planning.py:189-191). Then RETAIL_OPTIMIZED minimizes a constant, so any feasible plan is "optimal". V1-SPEC §6.2 says only that the defaults are 1 and 1 and are editable. The question: should the client (or the server) require at least one weight above 0? Until there is a decision, the client allows it, as the server does.
- **Decision (Gabriel via the lead, 2026-11-07):** at least one weight must be above 0. The lead adds the server check in `RetailWeights`. The form now shows "At least one weight must be above 0." and blocks Freeze while both are 0. One weight at 0 stays allowed. Test-first: `method-comparison.test.tsx` "retail weights can't both be 0…" failed first (no message), then passed. `npx vitest run` → 21 files, 107 passed; `v1-comparison.spec.ts` → 2 passed.
