# Status — `w5-polish`

**Lane:** `w5-polish` · **Branch:** `lane/w5-polish` · **Base SHA:** `81c551bc2e232362f0e63a7a00126ef1ca863fb8` · **Last update:** `2026-11-12` · **Head:** see `git log`

Skills check (2026-11-12): `/jmo-workflow:better-ui` loaded; `/jmo-workflow:animate` listed in this session. `visual-review` loaded.

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5-UI01 | done | (this commit) | Connected stack (`stack-up.sh`, schema `ppor_demo_pppolish_1112030601`, real API, PostgreSQL and production worker; real forecast.v1 runs and a Hub → pantries only, 2-day comparison through the queue), production build of base `81c551b`: `RUN=/tmp/pppol1 PP_E2E_PRODUCTION=1 PP_EVIDENCE_DIR=v1-before run-e2e.sh --config tests/e2e/connected/evidence.config.ts` → 1 passed (1.1 m); 54 screenshots (import, settings, atlas ranking Pantry and Retail, site inspector, forecast trust, comparison, decisions, print × 1440×900, 1280×720, 390×844 × light/dark) in `docs/pantrypulse/visual-evidence/v1-before/` |
| W5-UI02 | done | (this commit) | RED on base src first (7 new e2e failed for the expected reasons; 5 new unit tests failed on missing copy/props). GREEN: `npx vitest run` → 30 files, 190 passed; `npx playwright test tests/e2e/atlas-ranking.spec.ts --workers=2` → 13 passed; `tests/e2e/v1-a11y.spec.ts --workers=2` → 13 passed. UI02.4: Retail band meanings say "projected short or expiring unsold"; an expiry row says "first expiry <date>", the Retail table header "First day short or expiring"; a DC row carries "A DC has no sales; stock it doesn't send out counts as expiring". UI02.5: ranks #1–#3 in the first view at 1440×900 and 1280×720 for Pantry and Retail rows (map height capped at 16:9, caption beside it, legend beside the List/Table toggle, Retail reason on the product line); "Run forecast" moved beside the page header under a "Presenter" label (`group "Presenter controls"`); the inspector lists the driving product first, marked "Drives this location's danger rank"; a keyboard-focused marker shows its site name; Escape closes the live inspector and focus returns to the row or marker that opened it |
| W5-UI03 | todo | — | — |
| W5-UI04 | todo (depends on W5-D01 merged) | — | — |
| W5-UI05 | done (selector accessible name held, see below) | (this commit) | RED on base files first: `npx vitest run tests/unit/{e2e-runner,upload-form,template-guide}*` → 5 failed (port check, connected reuse, collapsed guides, "Optional." once); `npx playwright test tests/e2e/v1-shell.spec.ts --workers=2` → 7 failed (selector past the sidebar at 1440/1280; five screens wider than 390 px). GREEN: `npx vitest run` → 30 files, 190 passed; `npx playwright test tests/e2e/{v1-shell,overview,import-upload,import-templates,data-label,v1-a11y}.spec.ts --workers=2` → 68 passed; eslint, tsc clean. Changes: column guides start collapsed (`<details>`, "Column guide (n columns)"); file hints say "Optional."/"Required." once; `run-e2e.sh` exits with a clear message when `PLAYWRIGHT_PORT` is taken; `PP_RUN_CONNECTED=1` never reuses a server; the sidebar selector truncates (full name in `title`); at 390×844 the top bar stacks its labels so no v1 screen scrolls sideways (orchestrator request). Product picker: see the finding below |

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- The screenshot capture is `apps/web/tests/e2e/connected/visual-evidence.capture.ts`, run through its own `evidence.config.ts`, not a `*.spec.ts`: CI rejects any skipped test (`scripts/quality/require-test-evidence.py:8`), and a capture that needs the connected stack would skip there — W5-UI01/UI03.
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
- **CR-w5-screens-4 (approved, Gabriel 2026-11-12):** after that merge, delete `overview/live-source.ts`'s own `pluralize` (it writes "boxs"), re-export `pluralize` from `data-explorer/format`, and pin "boxes" on an Overview path (inspector or ranking). Same batch as the accessible-name change.

## Change requests

None filed by this lane.

## Escalations

None.
