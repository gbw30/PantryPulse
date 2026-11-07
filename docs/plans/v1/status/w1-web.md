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
| W1-W05 | done, except map placement and inspector (blocked: CR-w1-web-1, -2, -3) | see `git log` (W1-W05) | `npx vitest run tests/unit/danger-ranking.test.tsx` → 5 passed; `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/atlas-ranking.spec.ts` → 4 passed (@V1-A13 table alternative; @V1-A20 axe + keyboard toggle at 1440×900, 1280×720, 390×844; mocked `DangerRanking`). Not written: `@V1-A13 selecting a row opens the site inspector`, and placement by real coordinates. Both need data no frozen route returns (see CRs). |
| W1-W06 | done, except method/fallback/donations from a live run (CR-w1-web-4) | see `git log` (W1-W06) | `npx vitest run tests/unit/trust-panel.test.tsx` → 6 passed; `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/forecast-trust.spec.ts` → 1 passed (mocked `BacktestResult`). RED was not run before implementing; instead a mutation check (bias sign flipped, quantile check removed) failed 2 of 6 unit tests, and they passed again after restoring. |
| W1-W07 | done, except the Pantry window picker and editable policy (waiting for the ScenarioV3 `planning_days`/`policy` merge from v1-local) | see `git log` (W1-W07) | RED run first: unit 6 failed, e2e 2 failed. After: `npx vitest run tests/unit/method-comparison.test.tsx` → 6 passed; `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/v1-comparison.spec.ts` → 2 passed (A14 both transfer modes + axe, A15 units and USD); `npx vitest run` → 81 passed; `scenario-lab.spec.ts` + `recommendations*.spec.ts` → 33 passed, 2 skipped (both connected-only, `PP_RUN_CONNECTED`). research-claims-check on the new EGP copy (`results.tsx` method card): PASS — "inspired", DOI, no reproduction or outcome claim. |
| W1-W08 | done; effect lines say "units" until the effect carries its unit (CR-w1-web-5) | see `git log` (W1-W08) | RED run first: unit import failed, e2e 5 failed. After: `npx vitest run tests/unit/action-card.test.tsx` → 5 passed; `PLAYWRIGHT_PORT=3003 npx playwright test tests/e2e/decisions.spec.ts tests/e2e/v1-comparison.spec.ts` → 7 passed (A16 CSV download + print rows, A20 keyboard/axe/reduced motion at 1440, 1280 and 390); `npx vitest run` → 86 passed; eslint and `tsc --noEmit` clean. research-claims-check: no research or outcome copy added (only "Proven: binding constraint" / "Inferred reason" and the simulated-plan note). |

### W1-W01 port record

Ported unchanged from `b54ec7c`: `atlas-layout.test.ts`, `network-atlas.test.tsx`, `site-inspector.test.tsx`, `static-fixture.test.ts`, `status.test.ts` (plus a `// covers: V1-A21` first line). Not ported: `outlook.test.ts`, `outlook-chart.test.tsx`. First run: 18 failed / 29 passed. Test-side changes (no component edits):

- `static-fixture.test.ts` (8 failing): `overviewSourceFor` moved from `static-fixture.ts` to `sources.ts`, and its default is now `liveWithFallbackSource` (PP-51 `eb7cbaf`). Import from `sources`; expect the live-with-fallback default.
- `network-atlas.test.tsx` (4 failing): same move; spy on `sources.overviewSourceFor`.
- `static-fixture.test.ts` (tsc only, found in W1-W02): projection stock fields became nullable for live data → the test now fails loudly if the fixture has a null instead of using it unchecked.
- `site-inspector.test.tsx` (6 failing): `SiteInspector` gained a required `provenance` prop (`9d66945`) → pass the fixture provenance. Tab content now crossfades from opacity 0 (`16c47d7`), which jsdom never animates → mock `useReducedMotion` to `true`, a path the component already supports.

Visual check of 647f6a8: at 1440×900 the builder panel is 24rem and step-1 controls fit without wrapping; at 390×844 the layout is a single column. Pre-existing, unrelated: the full-page 1440 capture shows the fixed sidebar ending at the viewport height (screenshot artifact), and at 390 the "Simulated research preset" select sits a few px wider than its siblings.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

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
- Forecast trust is a section on the `/data` dashboard for the chosen v1 network (`?forecast_job_id=` until CR-w1-web-2). `forecast-chart.tsx` was not changed: it already draws the p10–p90 band only for a single-site series with model quantiles, and says why otherwise. Bias wording follows V5 §7 (error = prediction − actual, so positive bias = "forecast too high"). — W1-W06
- The top-bar "Simulated network" pill is unchanged: the existing screens still read the demo network until they are rewired to v1 networks. — W1-W02

- v1 method comparison is a new section at the top of Scenario Lab for the chosen network (`?forecast_run_id=` until CR-w1-web-2), built from `ComparisonSetup` (wizard.tsx), `MethodComparisonResults` (results.tsx), `MethodVerification` (recommendations/vocabulary.tsx) and the flow in `scenario-lab/v1-comparison.tsx`. The v2 stepper and results below it are unchanged, so their specs still hold. `recommendations-screen.tsx` was not changed: v1 actions come from the Decisions page (W1-W08). API calls went into `lib/network-api.ts` with the other v1 calls rather than `planning-api.ts`. — W1-W07
- The comparison job's `result_url` is read as the path of `GET networks/{id}/comparisons/{comparison_id}` (the contract gives no other link from job to comparison). A requested method missing from the saved result shows "No result returned for this method."; nothing is filled in. Effects stay per location × product in each product's unit; the per-method `objective` is not shown, since there is no network-wide objective total. USD availability is computed from the frozen scenario's `unit_value_usd` and names the unpriced products; Retail must pick a measure, Pantry is units only. — W1-W07

- Decisions (`/decisions?comparison_id=&method=`) start from a verified method result: Scenario Lab links each verified method with transfers to it. Selection starts empty; the CSV is the server's export (`POST …/export` text) saved byte-for-byte as `pantrypulse-plan-<comparison 8>-<METHOD>.csv`; the print page (`/decisions/print?network_id=&comparison_id=&method=&actions=`) re-reads the same comparison and actions and shows the selected rows with full scenario ID and hash, the simulated-plan note and the non-additive label. No total or combined effect is computed anywhere. An effect delta is read as plan minus plan-without-this-transfer (negative = lower). Pantry shows no USD line; Retail shows the USD delta or "USD effect unavailable: <reason>". — W1-W08
- Lead call (2026-11-07): a v1 comparison's `comparison_id` is the comparison job's `job_id`; `result_url` = `/api/v1/networks/{id}/comparisons/{job_id}`, which W1-W07 already follows. — W1-W08

- Security review (automated, MEDIUM, client-side path traversal): ids from the page URL went into API paths. Now every `networkApi` path segment is `encodeURIComponent`-ed, `/decisions` and its print page refuse non-UUID `comparison_id`/`network_id` before any request, and a comparison job's `result_url` is followed only when it matches `/api/v1/networks/<uuid>/comparisons/<uuid>`. The proxy allowlist already rejected non-UUID paths; this closes it in the browser too. Tests: `tests/unit/network-api.test.ts` (2) and the decisions e2e "ids that are not UUIDs are never sent to the API" (RED before, PASS after). — W1-W08

## Gotchas

- W1-W05's danger section broke 4 ported `network-atlas.test.tsx` tests (mocked shell, no NetworkProvider); I hadn't run the whole unit suite at W05/W06. Fixed test-side in its own commit. Run `npx vitest run` (all files) before each task commit. — W1-W07
- `recommendations.spec.ts › verified plan … at 1440x900` failed once in a 35-test batch and passed alone (3/3) and in a rerun of the batch (33 passed): another load-sensitive spec. — W1-W07
- Legacy Scenario Lab destructive alerts tint `code` and buttons below AA contrast; the load-failure alert now sets `text-foreground` on them (found by the A14 axe scan, which sees the legacy load failure under v1-only mocks). — W1-W07

- `overview-layout.spec.ts › panels move by their grip handles at 1440` timed out once (32.9 s) under a 4-spec parallel run and passed twice alone (7–10 s): likely load-sensitive; watch it in the full run. — W1-W05

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
- **Status:** open

### CR-w1-web-2 — a way to find a network's forecast runs
- **File(s):** `apps/api/app/schemas/v1_networks.py` (or a new forecasts read), `packages/contracts/**` (lead-only)
- **Exact change:** either add `latest_forecast_run_id: uuid | null` (with its `dataset_version_id`) to `Network`, or add `GET /networks/{network_id}/forecasts` → `[{forecast_run_id, job_id, dataset_version_id, recorded_at, state}]`.
- **Why:** `GET /networks/{id}/danger` requires `forecast_run_id`, and `GET /forecasts/{job_id}/backtest` a job id, but the only place either appears is the 202 `ForecastAccepted` from `POST /networks/{id}/forecasts`. After a reload the UI cannot find the run. Interim in this lane: `/overview?forecast_run_id=` (the danger e2e uses it).
- **Unblocks:** W1-W05 without the URL parameter, W1-W06 backtest fetch.
- **Status:** open

### CR-w1-web-4 — v1 forecast series result, and a per-location accuracy roll-up
- **File(s):** `packages/contracts/examples/v1/` + forecast schemas (lead-only; service in w3-forecast)
- **Exact change:** (a) name the read that returns a `forecast.v1` network run's series and add its example, keyed by v1 `location_id`/`product_id`, with `basis`, `actual_provider`, `fallback_used`, `fallback_reason`, `diagnostics.missing_count`, `points` (p10/p90 only from quantile providers) and the donation forecast per location × product; (b) add per-location WAPE/bias to `BacktestResult` (e.g. `locations: [{location_id, score: BacktestScore}]`) computed on the pooled scored set.
- **Why:** V1-SPEC §6.4 requires method, fallback reason, missing days, quantile band and "rolled up per location". `BacktestResult` has only per-series scores, and WAPE percentages can't be averaged into a per-location figure without the underlying sums. The existing `ForecastSeriesResult` is keyed by v2 UUIDs, and no v1 example exists. `TrustPanel` already renders all of it from `ForecastSeriesResult` fields (unit-tested with a typed subset, since no example exists).
- **Unblocks:** W1-W06 method/fallback/donation rows on the live page; the per-location roll-up.
- **Status:** open

### CR-w1-web-5 — the unit of an action's effect
- **File(s):** `ActionEffect` schema + `DecisionActions.json` (lead-only)
- **Exact change:** add `unit` (the product's unit, e.g. "case") to `ActionEffect`, or the product's `name` and `unit`.
- **Why:** V1-SPEC §6.5 shows the effect at sender and receiver in units; the decisions page only has `product_id`, so it writes "40 units lower" and "Product WATER-24; units as in the plan" instead of "40 cases lower". There is no scenario read to look the unit up.
- **Unblocks:** W1-W08 effect lines and print rows in the product's own unit.
- **Status:** open

### CR-w1-web-3 — per-location projection for the site inspector
- **File(s):** contracts + a networks/forecast router (lead-only; service in w3-forecast's area)
- **Exact change:** add `GET /networks/{network_id}/projection?forecast_run_id=&location_id=` → per product: `product_id, unit, dates[7], target[7], served[7], unmet[7], eligible_stock_now, expiring_unsold[7] | null, donation_forecast[7] | null` (null stays null).
- **Why:** V1-SPEC §6.6 "selecting a location opens the existing site inspector"; `SiteInspector` renders per-day target/served/unmet per product, and no v1 contract returns them (`DangerRow` has only the driving product).
- **Unblocks:** W1-W05 `@V1-A13 selecting a row opens the site inspector`.
- **Status:** open

### Contract example notes (no change requested)
- `ImportStatus.json`'s failure message names "North County Pantry Network", which `NetworkList.json` also lists as existing. The A07 e2e therefore mocks the before-import list without that network.
- `ScenarioV3.json`/`SavedComparisonV3.json` are Pantry only and hold 3 of the 5 Pantry methods. `v1-comparison.spec.ts` clones them into Retail (roles, prices, methods `SOONEST_EXPIRY_FIRST`/`RETAIL_OPTIMIZED`). There is no `ForecastJob` example; the finished job is built from `ForecastAccepted.json`'s identities.
- `TemplateCatalog.json` lists two of the seven templates; `import-upload.spec.ts` clones those two entries to stand in for the other five.

## Escalations
