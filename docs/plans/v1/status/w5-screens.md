# Status — `w5-screens`

**Lane:** `w5-screens` · **Branch:** `lane/w5-screens` · **Base SHA:** `81c551bc2e232362f0e63a7a00126ef1ca863fb8` · **Last update:** `2026-11-12` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5-UI02.1 | done (CI needs CR-w5-screens-1) | see W5-UI02.1 commit | RED: `npx playwright test tests/e2e/v1-screens-data.spec.ts` → 3 failed (`legacy content "Riverbend"`). GREEN: `npx playwright test tests/e2e/v1-screens-data.spec.ts tests/e2e/data-explorer.spec.ts tests/e2e/forecast-trust.spec.ts` → 27 passed, 1 skipped (the connected test, `PP_RUN_CONNECTED` unset; not counted). `data-label.spec.ts:66` → 2 failed before CR-w5-screens-1; 5 passed after it (`0790cf1`) |
| W5-UI02.1b (D03 copy) | done | see the W5-UI02.1b commit | Approved by Gabriel 2026-11-12 (orchestrator). RED: `npx playwright test tests/e2e/v1-screens-data.spec.ts -g "all-zero"` → 1 failed (panel said "accuracy not evaluated: needs 35+ days"). GREEN: `npx playwright test tests/e2e/v1-screens-data.spec.ts tests/e2e/forecast-trust.spec.ts` → 5 passed; `npx vitest run tests/unit/trust-panel.test.tsx tests/unit/forecast-trust.test.tsx` → 13 passed. `not_evaluated_zero_actual` reads "accuracy not measurable: every scored day's actual was zero" in the panel and the location table, with no percentage; the short-history status keeps "needs 35+ days" |
| W5-UI02.2 | done (connected check needs CR-w5-screens-2) | see W5-UI02.2 commit | RED: `npx playwright test tests/e2e/v1-comparison.spec.ts -g "fit at 1280"` → 1 failed (`one card per row`). GREEN: `npx playwright test tests/e2e/v1-comparison.spec.ts tests/e2e/scenario-lab.spec.ts --repeat-each=2` → 30 passed, 2 skipped (the connected test ×2, `PP_RUN_CONNECTED` unset; not counted). `npx vitest run tests/unit/method-comparison.test.tsx tests/unit/v1-comparison.test.tsx tests/unit/scenario-lab.test.tsx` → 19 passed |
| W5-UI02.3 | done | see the W5-UI02.3 commit | After merging `origin/v1-local` at `372a3cb` (W5-L02). RED: `npx playwright test tests/e2e/decisions.spec.ts` → 1 failed (`Plan covers Nov 6–8 (3 days) only; unmet need after Nov 8 is not planned.` not found). GREEN: same command → 11 passed; `npx vitest run tests/unit/action-card.test.tsx tests/unit/decisions-view.test.tsx` → 15 passed, then 11 passed in `decisions-view.test.tsx` with the new period test (cross-month, one day, Retail wording). `npm run typecheck` → 1 error, only in `tests/unit/action-card.test.tsx:17` (its `card()` helper lacked the new required `period` prop); after CR-5 (`d6834e0`): `npm run typecheck` → no errors, `npx vitest run tests/unit/action-card.test.tsx tests/unit/decisions-view.test.tsx` → 16 passed. research-claims-check on the lane's `apps/web/src` diff: PASS (the only matches are "saved" for the stored print selection; no outcome, fairness or calibration claims) |
| W5-SC01 | done in `data-explorer/format.ts`; the v1 screens' tables still read "boxs" until CR-w5-screens-4 (w5-polish, after the screens merge) | see W5-SC01 commit | Plural — RED: `npx vitest run tests/unit/scenario-lab.test.tsx` → 1 failed (`box: "boxs"`, `each: "eachs"`, `glass: "glass"`); GREEN → 4 passed. Print selection — RED: `npx vitest run tests/unit/decisions-view.test.tsx` → 1 failed (`expected 1 to be +0`: selecting already saved); GREEN with the three older selection tests updated to follow the print link → `npx vitest run tests/unit/decisions-view.test.tsx tests/unit/action-card.test.tsx` 15 passed. `npx playwright test tests/e2e/decisions.spec.ts` → 10 passed (the print link saves before it navigates). 700-action test: explicit 20 s timeout (a timeout can't be shown RED on demand; it exceeded 5 s once under load on `977f7c6`) |
| W5-SC02 | done | see the SC02 evidence commits | Connected capture on the lane stack (`pp-screens`, 3105): `PP_RUN_CONNECTED=1 PLAYWRIGHT_PORT=3105 npx playwright test tests/e2e/v1-screens-evidence.spec.ts` → 2 passed (axe on /data, the comparison and Decisions) on `d6834e0`, after W5-L02. `/data`, comparison, comparison-rows-open and Decisions shots at 1440×900, 1280×720 and 390×844 in `docs/pantrypulse/visual-evidence/w5-screens/`. The capture found the setup column stretching once a card's rows are open (fixed test-first: RED `transfer-mode options stay together` 105.6 px; GREEN `npx playwright test tests/e2e/v1-comparison.spec.ts tests/e2e/scenario-lab.spec.ts --repeat-each=2` → 30 passed, 2 skipped = connected test ×2) |

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | `7e94d4c` | PASS (web typecheck, web lint, api lint, api tests); standard env, so the PostgreSQL suites skip (458) and are not counted. The Stop hook's run just before failed once on `test_actions.py::test_actions_equal_the_full_network_replay[bench-retail-RETAIL_OPTIMIZED-receiving-None]` (see Gotchas) |
| `node scripts/quality/run.cjs quick` (with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1` exported by hand) | `3a62ca6` | PASS (web typecheck, web lint, api lint, api tests) |
| `node scripts/quality/run.cjs full` (with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1` exported by hand) | `3a62ca6` | PASS, exit 0 (typecheck, lint, api lint, api tests, web unit tests, web build, contract drift, database migrations). The gate prints no counts, so its commands were rerun in the same env with `-rs`: `uv run --frozen pytest -q -rs` → 2222 passed, 0 skipped; `uv run --frozen pytest -q -rs tests/integration/test_job_migrations.py tests/integration/test_operational_postgres.py` → 36 passed, 0 skipped; `npx vitest run` → 184 passed (28 files), 0 skipped. e2e is CI's |
| `node scripts/quality/run.cjs quick` (with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1`), after merging `origin/v1-local` (W5-D01, `a6d08a1`) | `3f8d35c` | PASS. Same env: `uv run --frozen pytest -q -rs` → 2253 passed, 0 skipped; `npx vitest run` → 185 passed |
| `/devkit:ship-check` | `60f7137` → fixes after | Step 1: quick and full above. Step 2: the lane's `verifier` agent on `60f7137`. It reported two items this lane fixed test-first: (a) a middle-click or "Open in new tab" on the print link fired no `click`, so the selection wasn't saved (RED `expected +0 to be 1`; fix: `onMouseDown` for non-primary buttons in `export-bar.tsx`), and (b) the new plural rule wrote "ozes" (RED; fix: oz, g, kg, ml, l stay as they are). GREEN: `npx vitest run tests/unit/decisions-view.test.tsx tests/unit/scenario-lab.test.tsx tests/unit/action-card.test.tsx` → 21 passed; `npx playwright test tests/e2e/decisions.spec.ts` → 11 passed; quick (with `PP19_TEST_SCHEMA_ISOLATION=1`) PASS. Its other notes: "boxs" on the v1 screens (CR-4), missing window dates render "Invalid Date" (the contract makes them required, so not guarded), the Seven-Day Pulse tab (a lane decision), and the 20 s timeout on the 700 test (recorded). The orchestrator's independent verifier: `60f7137` PASS WITH NOTES (all notes outside the lane or minor). Step 3: security-guidance not installed. Steps 5–6: `/code-review` kept local; no auth, payment or migration change, so no second-model review |

## Pull request

- PR: https://github.com/gbw30/PantryPulse/pull/152 (`lane/w5-screens` → `v1-local`), opened at head `2b45894`. This status commit follows it; it changes only this file.
- Gates (with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1`): quick PASS at `3f8d35c` after merging `origin/v1-local` (2253 API passed, 0 skipped; 185 web unit passed). Full PASS at `3a62ca6` (2222 API, 36 migrations, 184 web unit; 0 skipped). Since the full run: the two review fixes in `b40bcc5`, plus the API-only W5-D01 merge.
- Independent verifier: `60f7137` PASS WITH NOTES (orchestrator). Merging nothing; waiting for the orchestrator and Gabriel.

## Decisions made inside the lane

- W5-UI02.1: with a v1 network chosen, `/data` renders the Data Explorer header (its description names the network) and that network's Forecast trust only. The legacy block renders only when no v1 network exists or the network list failed, the same rule `/scenarios` follows (W3 lead decision, `v1-mocks.ts` `withoutV1Networks`). While the list loads, nothing legacy is fetched. The "Seven-Day Pulse" tab stays; that view is legacy-only and its top bar says "Simulated network".
- W5-UI02.2: the effects rows sit in a native `<details>` ("Show rows · N location × product rows", "Hide rows" when open), so it needs no script and keyboard and screen readers get it for free. Table headers and cells wrap so all six columns fit a card at 1280; at 390 the table still scrolls inside its labeled region. The column texts are unchanged (pinned by `method-comparison.test.tsx`).
- The connected legacy check in `data-explorer.spec.ts` now calls `withoutV1Networks`, like the legacy connected Scenario Lab specs.

- W5-UI02.3: every effect quantity ends with "over Nov 6–12 (7 days)" (`DecisionActions.effect_window_*`), in a muted span after the unchanged line, so the quantity reads first; "USD effect unavailable" is not a quantity and gets no period. Above the cards and on the print page: "Plan covers Nov 6–8 (3 days) only; unmet need after Nov 8 is not planned." (Retail: "lost sales after … are not planned"), from `plan_window_*`. Dates are formatted as UTC calendar days, so the browser's zone can't shift them. Each card's effect list is named by its "Effect" heading.
- W5-SC01 plural: `-es` after s/x/z/ch/sh endings, `-ies` after a consonant y, an existing plural ending in one s kept ("lbs", "meals"), and "each" unchanged (the new ch rule would otherwise write "eaches").
- W5-SC01 print: the selection is saved in the print link's `onClick`, before Next navigates. Selecting alone writes nothing, so another tab's Decisions can't replace it; a failed save still removes the stored one.

## Gotchas

- `apps/api/tests/optimization/test_actions.py::test_actions_equal_the_full_network_replay[bench-retail-RETAIL_OPTIMIZED-receiving-None]` failed once in a Stop-hook quick run on `7e94d4c` (1 failed, 1761 passed, 458 skipped), at a load average of about 27. This lane changed no API code (`git diff 81c551b..HEAD -- apps/api` is empty). It then passed 105/105 for the whole test, 6/6 alone (about 1.5 s each), and in a full quick rerun. The hook output had no assertion text. The test runs a real CP-SAT solve (`run_method`, line 281), so a time-limited solve under load is the likely cause, but that is unverified. For the solver owner.

- Under heavy machine load (load average 37 with four lanes and a compose stack up), legacy `scenario-lab.spec.ts` tests time out at 5 s with the page still on "Loading networks…" (:350, :361). They passed 5/5 alone and 30/30 with the lane stack stopped. Local e2e numbers are only meaningful on a quiet machine.
- At 390×844 every screen is 481 px wide: the top bar's right cluster (`top-bar.tsx:83`, `ml-auto flex shrink-0 items-center gap-3`) overflows. Found by the W5-SC02 capture; w5-polish's file, reported to the orchestrator.

- `textContent()` of `body` includes the Next dev RSC payload script; use `innerText()` for "page contains no X" checks.
- A 401 from a legacy read calls `onUnauthorized` and ends the presenter session in the browser; a mock that only wants the legacy fixture should answer 403.

## Change requests

### CR-w5-screens-1 — `data-label.spec.ts` pins the legacy block beside a chosen network
- **File(s):** `apps/web/tests/e2e/data-label.spec.ts` (w5-polish)
- **Exact change:** in the test at line 66 (`/data with a ${kind} chosen labels that network in the top bar and the legacy block as simulated`), replace `await expect(page.locator("[data-explorer-source]")).toContainText(/simulated network/i);` with `await expect(page.locator("[data-explorer-source]")).toHaveCount(0);`, retitle it `/data with a ${kind} chosen labels that network in the top bar and shows no legacy block`, and update the comment above it (lines 62-63) to say the legacy block no longer renders with a chosen network (W5-UI02.1). The top-bar assertions stay as they are and still pass.
- **Why:** W5-UI02.1 removes the legacy block when a v1 network is chosen; this test asserts that block is there, so it failed twice (`element(s) not found`) on this branch. The file's other three tests passed.
- **Unblocks:** CI on the `w5-screens` PR (W5-UI02.1). The local `quick`/`full` gates do not run e2e.
- **Status:** approved (Gabriel, 2026-11-12), done in `0790cf1`. Evidence: `npx playwright test tests/e2e/data-label.spec.ts` → 5 passed, 0 failed, 0 skipped. The file has 5 tests (`--list`), not 6.

### CR-w5-screens-2 — the connected journey reads collapsed effects rows
- **File(s):** `apps/web/tests/e2e/v1-connected-journey.spec.ts` (w5-polish / lead connected harness)
- **Exact change:** before line 51 (`const effects = results!.getByRole("region", { name: /^Effects table for EGP-PI-inspired/ })…`), add `await results!.getByRole("region", { name: "EGP-PI-inspired", exact: true }).getByText("Show rows").click();`, and after reading the headers add `expect(await effects.count()).toBeGreaterThan(0);` so the name check can't pass on zero rows.
- **Why:** W5-UI02.2 puts each card's rows behind a "Show rows" disclosure. Playwright's `getByRole` skips hidden elements, so without the click `allTextContents()` returns `[]` and the "locations are named" check passes vacuously.
- **Unblocks:** keeps the connected journey's location-name check meaningful (W5-UI02.2). Not run locally (connected).
- **Status:** approved (Gabriel, 2026-11-12), done in `5448824`; connected, not run locally (typecheck and lint pass).

### CR-w5-screens-3 — Decisions needs the plan window and the effect period
- **File(s):** `apps/api/app/schemas/v1_planning.py` (`DecisionActions`), `apps/api/app/services/optimization/actions.py` (`decision_actions`), regenerated `packages/contracts` (OpenAPI, `schema.d.ts`, `examples/v1/DecisionActions.json`). All lead-only.
- **Exact change:** add four required dates (inclusive, local days in the scenario's timezone) to `DecisionActions`, filled in `decision_actions` from the frozen scenario:
  - `plan_window_start = dates(s)[0]` and `plan_window_end = dates(s)[window_days(s) - 1]`: the days the plan is built for (Pantry: `planning_days`, 1–3; Retail: all 7, `v3.py:43-45`).
  - `effect_window_start = dates(s)[0]` and `effect_window_end = dates(s)[-1]`: the days every remove-one effect is summed over. `_effect` (`actions.py:129-139`) sums `project_v3(...).days`, and `project_v3` runs over `dates(scenario)`, all 7 forecast days (`projection.py:190-193`), in both modes.
  - Optional, lead's call: the same four in the export CSV header, so an exported plan names its period too.
- **Why:** W5-UI02.3 must state each effect's dates and window length, and that the plan covers only its window ("Plan covers Nov 6–8 only; unmet need after Nov 8 is not planned"). Decisions reads only `SavedComparisonV3` (no dates; `result` has `scenario_id`, `scenario_hash`, `mode`, `measure`, `methods`) and `DecisionActions` (no dates). There is no GET for a frozen v1 scenario (`/networks/{id}/scenarios` is POST only), and `/networks/{id}/projection` is the current data, not the frozen scenario. Parsing `action_text`/`why_text` or carrying dates in the Decisions URL would show dates that aren't the frozen plan's.
- **Note for the lead:** in a Pantry plan the effect period (7 days) is longer than the plan window (1–3 days). The UI will say both: e.g. "Receiver unmet need, Nov 6–12 (7 days): 40 cases lower" and "Plan covers Nov 6–8 (3 days) only; unmet need after Nov 8 is not planned."
- **Unblocks:** W5-UI02.3 (Decisions and its print page).
- **Status:** approved (Gabriel, 2026-11-12), lead W5-L02 in progress. Dates in the `DecisionActions` response only, not in the CSV export.

### CR-w5-screens-4 — the Overview keeps its own copy of the plural
- **File(s):** `apps/web/src/components/overview/live-source.ts` (w5-polish)
- **Exact change:** replace the local `pluralize` (lines 10-15) with `export { pluralize } from "@/components/data-explorer/format";` and import it there for `formatUnits` (`import { pluralize } from "@/components/data-explorer/format";`). Nothing else changes.
- **Why:** W5-SC01 fixed `data-explorer/format.ts` ("boxes", "bunches", "dishes", "glasses"; "each" kept), pinned by `tests/unit/scenario-lab.test.tsx`. The Overview inspector (`location-inspector.tsx:7,38`) and every `formatUnits` caller (the danger ranking, the comparison effects tables, Decisions effect lines) use the duplicate in `overview/live-source.ts`, which still writes "boxs".
- **Unblocks:** the rest of the W5-SC01 plural fix (the ux-critic's "boxs" note).
- **Status:** approved (Gabriel, 2026-11-12), w5-polish after the screens merge.

### CR-w5-screens-5 — the ActionCard unit test's helper needs the effect period
- **File(s):** `apps/web/tests/unit/action-card.test.tsx` (not owned by this lane)
- **Exact change:** line 17, in `card()`, add `period="Nov 6–12 (7 days)"` after `usdUnavailableReason={null}`. Nothing else changes.
- **Why:** W5-UI02.3 makes `period` a required `ActionCard` prop, so a card can't render an effect quantity without its period. Vitest passes (15 passed; it doesn't typecheck), but `npm run typecheck` fails at that line, so the quick gate fails until the helper passes the prop.
- **Unblocks:** the quick gate and CI on the `w5-screens` PR.
- **Status:** approved (Gabriel, 2026-11-12), done in `d6834e0`. Evidence: `npm run typecheck` → no errors; `npx vitest run tests/unit/action-card.test.tsx tests/unit/decisions-view.test.tsx` → 16 passed.

## Escalations

- none
