# Status — `w5-polish`

**Lane:** `w5-polish` · **Branch:** `lane/w5-polish` · **Base SHA:** `81c551bc2e232362f0e63a7a00126ef1ca863fb8` · **Last update:** `2026-11-12` · **Head:** `8726dfd` + this status commit (paused for the `w5-screens` merge; last code commit `7f23051`, which includes the `a6d08a1` merge)

Skills check (2026-11-12): `/jmo-workflow:better-ui` loaded; `/jmo-workflow:animate` listed in this session. `visual-review` loaded.

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5-UI01 | done | (this commit) | Connected stack (`stack-up.sh`, schema `ppor_demo_pppolish_1112030601`, real API, PostgreSQL and production worker; real forecast.v1 runs and a Hub → pantries only, 2-day comparison through the queue), production build of base `81c551b`: `RUN=/tmp/pppol1 PP_E2E_PRODUCTION=1 PP_EVIDENCE_DIR=v1-before run-e2e.sh --config tests/e2e/connected/evidence.config.ts` → 1 passed (1.1 m); 54 screenshots (import, settings, atlas ranking Pantry and Retail, site inspector, forecast trust, comparison, decisions, print × 1440×900, 1280×720, 390×844 × light/dark) in `docs/pantrypulse/visual-evidence/v1-before/` |
| W5-UI02 | done | (this commit) | RED on base src first (7 new e2e failed for the expected reasons; 5 new unit tests failed on missing copy/props). GREEN: `npx vitest run` → 30 files, 190 passed; `npx playwright test tests/e2e/atlas-ranking.spec.ts --workers=2` → 13 passed; `tests/e2e/v1-a11y.spec.ts --workers=2` → 13 passed. UI02.4: Retail band meanings say "projected short or expiring unsold"; an expiry row says "first expiry <date>", the Retail table header "First day short or expiring"; a DC row carries "A DC has no sales; stock it doesn't send out counts as expiring". UI02.5: ranks #1–#3 in the first view at 1440×900 and 1280×720 for Pantry and Retail rows (map height capped at 16:9, caption beside it, legend beside the List/Table toggle, Retail reason on the product line); "Run forecast" moved beside the page header under a "Presenter" label (`group "Presenter controls"`); the inspector lists the driving product first, marked "Drives this location's danger rank"; a keyboard-focused marker shows its site name; Escape closes the live inspector and focus returns to the row or marker that opened it |
| W5-UI03 | in progress: Steps 1, 2 and 4 done (Step 4 accepted closed by the orchestrator); Step 3 waits for the `w5-screens` merge | (this commit) | Step 1 RED: `npx playwright test tests/e2e/v1-motion.spec.ts --workers=2` → demo atlas failed (infinite `pp-supply-flow`, `pp-supply-flow-in` 1100 ms, last marker's entrance 1010 ms, skeleton `pulse` infinite), the inspector-entrance and pause-control tests failed (nothing recorded; no button). The recorder (`tests/e2e/motion.ts`) now also times script-driven motion: inline-transform and SVG `stroke-dash*` runs (it used to give them no duration). Step 2 GREEN (`/jmo-workflow:animate`): site inspector enters in 200 ms (fade + 6 px lift, `cubic-bezier(0.23,1,0.32,1)`, fade only under reduced motion); flow-in starts at 0.5 s; marker stagger capped at 0.3 s; the skeleton is static (ART-DIRECTION Loading row); the supply-link pause control (decision below). `v1-motion.spec.ts` → 7 passed; `overview`, `overview-layout`, `atlas-ranking`, `v1-a11y` → 69 passed; `design-lab` + `v1-motion` → 12 passed; `npx vitest run` → 190 passed; eslint, tsc clean. Step 4: see the escalation below; 10 isolated runs of `overview-layout.spec.ts:216` against the production build → 10/10 passed |
| W5-UI04 | done; Step 2's import-guide part done by w5-data (Gabriel 2026-11-12: the guide names the three places, the Forecast trust panels, the danger ranking and the site inspector, not "everywhere", since Scenario Lab and Decisions don't show it) | `7f23051` | Merged `origin/v1-local` at `a6d08a1` (W5-D01, W5-L02) first. research-claims-check on the new copy: PASS (a data-basis label; no research, outcome or probability claim). RED: 3 new unit tests failed (`danger-ranking.test.tsx` list and table; `location-inspector.test.tsx`). GREEN: a row or product whose `basis` is `sales` shows "Basis: sales (undercounts demand when shelves were empty)" (`SALES_LABEL` from `data-explorer/trust-panel.tsx`): in the ranking list on the driving-product line, in the table under the driving product, and under that product's table in the inspector; `demand` and null show nothing. The donations why line: `tests/e2e/v1-donations-why.spec.ts` (`@V1-A08`) pins the why text with "At Pantry 12, expected donations (forecast, not confirmed): … not counted as supply." rendering unchanged on Decisions. It passed on first run (the page passes `why_text` through), so it is a guard, not RED. Retail rows from sales history now wrap their second line, and rank #3 ended 10 px below the fold (`atlas-ranking.spec.ts` first-view test, now built with `basis: "sales"` on Retail rows), so the live map's height cap went from `100svh-36rem` to `100svh-37rem`. `npx vitest run` → 30 files, 195 passed; `npx playwright test tests/e2e/{atlas-ranking,v1-donations-why,v1-motion,overview,v1-a11y}.spec.ts --workers=2` → 53 + 26 passed; eslint, tsc clean |
| W5-UI05 | done (selector accessible name held, see below) | (this commit) | RED on base files first: `npx vitest run tests/unit/{e2e-runner,upload-form,template-guide}*` → 5 failed (port check, connected reuse, collapsed guides, "Optional." once); `npx playwright test tests/e2e/v1-shell.spec.ts --workers=2` → 7 failed (selector past the sidebar at 1440/1280; five screens wider than 390 px). GREEN: `npx vitest run` → 30 files, 190 passed; `npx playwright test tests/e2e/{v1-shell,overview,import-upload,import-templates,data-label,v1-a11y}.spec.ts --workers=2` → 68 passed; eslint, tsc clean. Changes: column guides start collapsed (`<details>`, "Column guide (n columns)"); file hints say "Optional."/"Required." once; `run-e2e.sh` exits with a clear message when `PLAYWRIGHT_PORT` is taken; `PP_RUN_CONNECTED=1` never reuses a server; the sidebar selector truncates (full name in `title`); at 390×844 the top bar stacks its labels so no v1 screen scrolls sideways (orchestrator request). Product picker: see the finding below |

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` (with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1`) | `7f23051` (interim, after merging `a6d08a1`) | PASS (exit 0). The final run comes after the post-screens batch |
| `uv run --frozen pytest` in `apps/api` (with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1`) | `10552c7` (interim, before the `a6d08a1` merge) | 2220 passed, 0 skipped (404 s) |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- **Gate evidence (orchestrator, 2026-11-12):** `.env.lane` does not set `PP19_TEST_SCHEMA_ISOLATION`, and without it the PP19 PostgreSQL suites (`apps/api/tests/integration/test_{operational,forecast_api,planning}_postgres.py`) skip silently. Every quick or full run cited here exports `PP19_TEST_SCHEMA_ISOLATION=1` alongside `.env.lane`; an earlier quick run without it is not evidence.

- The screenshot capture is `apps/web/tests/e2e/connected/visual-evidence.capture.ts`, run through its own `evidence.config.ts`, not a `*.spec.ts`: CI rejects any skipped test (`scripts/quality/require-test-evidence.py:8`), and a capture that needs the connected stack would skip there — W5-UI01/UI03.
- **Supply-link flow (Gabriel, 2026-11-12, via the orchestrator):** keep the always-on `.pp-supply-flow` loop (PP-52 #4) and add a pause control for WCAG 2.2.2. "Pause link animation" in the map's "Map controls" group: a toggle button with `aria-pressed` (stable name, pressed = paused), remembered per browser in localStorage (`pp-atlas-flow-paused`, try/catch, playing when storage is unavailable); paused links show static, as under reduced motion. `v1-motion.spec.ts` exempts only that loop, by name; everything else stays finite and ≤ 1 s — W5-UI03.
- `connected/stack-up.sh` and `run-e2e.sh` take their ports from `.env.lane` (`PP_API_PORT`, `PLAYWRIGHT_PORT`) instead of the hardcoded 8003/3003, which are `w5-data`'s ports this wave — W5-UI01 (prerequisite).

## Gotchas

- Running several mocked e2e files at once against the dev server (default worker count) times out or aborts navigations while Next compiles; the same files pass with `--workers=2`. The first run after a source edit also pays the compile.
- The connected stack's run directory must be short (`/tmp/pppol1`): AF_UNIX socket paths are capped at 107 bytes, and the session scratchpad path is longer.
- The API log (`$RUN/api.log`) is block-buffered, so it can look empty while the browser is talking to the API.
- Full-page screenshots draw the sidebar only to the first viewport height (it is `h-svh`); that is a capture artifact, not a layout bug.

- **W5-UI05 product picker finding:** the plan's premise does not hold. Under `slowTimers(2000)` the closed card's late focus return does fire while the picker is in use, but Radix Select schedules its own focus return later, so focus ends on the picker and the chosen product stays. Both new tests (`overview.spec.ts`, click and keyboard) pass on the current code, and still pass with #143's `lost` guard removed (mutation run; the #143 card test does fail then). No production change; the tests are regression coverage. The first keyboard version failed because Radix moves the ArrowDown highlight in a 0 ms timer that `slowTimers` also delays; the test now waits for the highlight before Enter.

## Held until `w5-screens` merges (orchestrator, 2026-11-12)

- **Do not edit** `apps/web/tests/e2e/data-label.spec.ts` (CR-w5-screens-1) or `apps/web/tests/e2e/v1-connected-journey.spec.ts` (CR-w5-screens-2); both arrive with the post-screens `origin/v1-local` merge.
- **W5-UI05 network selector, accessible-name part:** the full network name joins the switcher's accessible name only after that merge, in the same commit as the update to `data-label.spec.ts:43,69` (they find the switcher as `{ name: "Network", exact: true }`). The truncation lands now.
- **Do not edit** `apps/web/tests/unit/action-card.test.tsx` (CR-w5-screens-5: screens adds a `period` prop to its `card()` helper).
- **W5-UI03 Step 3:** merge `origin/v1-local`, rebuild, capture `v1-after/` (connected stack, `PP_EVIDENCE_DIR=v1-after`), then run `v1-a11y.spec.ts` and `v1-full-journey.spec.ts`.
- **CR-w5-screens-4 (approved, Gabriel 2026-11-12):** after that merge, delete `overview/live-source.ts`'s own `pluralize` (it writes "boxs"), re-export `pluralize` from `data-explorer/format`, and pin "boxes" on an Overview path (inspector or ranking). Same batch as the accessible-name change.

## Change requests

None filed by this lane.

- **CR-w5-data-2** (from w5-data; approved, Gabriel, 2026-11-12; done in `43df904`): `commit()` in `import-view.tsx` answers 409 `IMPORT_ALREADY_FINISHED` by reading the run (`track`) instead of "Import request failed … Nothing was saved". This fixes a Retry after a commit whose phase write was lost and whose job then finished. Test first: `tests/unit/import-view.test.tsx` adds two tests (a done run shows "Import finished"; a failed run keeps its row-error report). RED: both failed (the page said the request failed). GREEN: `npx vitest run` → 30 files, 192 passed; tsc, eslint clean. Keyed on the code, so harmless before W5-D04 lands.

## Escalations

- **W5-UI03 Step 4, `overview-layout.spec.ts:216` (drop clamp): root cause not established; it does not reproduce.** Reported to the orchestrator 2026-11-12; accepted as closed the same day (as with the w5-data replay flake). If any CI log shows it again, send it to the orchestrator with the failure text. The recorded occurrences (GAP-REPORT 2026-11-03 WSL run; #110 CI, BOARD W1 row, 2026-11-07) predate two fixes for the closed card's late focus return: W3-W02 `ee2ae4c` (the test waits for focus to return) and #143 (the `lost` guard in `network-atlas.tsx`). None of the 9 failed `pantrypulse-ci.yml` runs whose logs GitHub still keeps mention the test. Tried, none of which failed (dev server unless noted):
  - repeated runs: 20 at 4 workers; the whole spec 8 times at 8 workers (72 tests); the production build 40 times at 10 workers;
  - CPU throttling (CDP): 4× and 8× on the production build, 20 runs each;
  - hypothesis 1, the late focus return: Radix's 0 ms timers slowed to 300 ms, and both fixes reverted (test and app) on the production build at 8×. Pass, so it isn't this test's failure path;
  - hypothesis 2, a layout shift after the markers render: the map and legend boxes are the same at marker time and 2.5 s later, with the API answering at 0 and at 1.5 s.

  No speculative fix landed (lane stop rule: 3 focused attempts). The test is unchanged; 10/10 isolated runs pass. If CI flags it again, its junit and trace give the failing assertion to work from.
