# Status — `w5-screens`

**Lane:** `w5-screens` · **Branch:** `lane/w5-screens` · **Base SHA:** `81c551bc2e232362f0e63a7a00126ef1ca863fb8` · **Last update:** `2026-11-12` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5-UI02.1 | done (CI needs CR-w5-screens-1) | see W5-UI02.1 commit | RED: `npx playwright test tests/e2e/v1-screens-data.spec.ts` → 3 failed (`legacy content "Riverbend"`). GREEN: `npx playwright test tests/e2e/v1-screens-data.spec.ts tests/e2e/data-explorer.spec.ts tests/e2e/forecast-trust.spec.ts` → 27 passed, 1 skipped (the connected test, `PP_RUN_CONNECTED` unset; not counted). `data-label.spec.ts:66` → 2 failed, by design (CR-w5-screens-1) |
| W5-UI02.2 | done (connected check needs CR-w5-screens-2) | see W5-UI02.2 commit | RED: `npx playwright test tests/e2e/v1-comparison.spec.ts -g "fit at 1280"` → 1 failed (`one card per row`). GREEN: `npx playwright test tests/e2e/v1-comparison.spec.ts tests/e2e/scenario-lab.spec.ts --repeat-each=2` → 30 passed, 2 skipped (the connected test ×2, `PP_RUN_CONNECTED` unset; not counted). `npx vitest run tests/unit/method-comparison.test.tsx tests/unit/v1-comparison.test.tsx tests/unit/scenario-lab.test.tsx` → 19 passed |
| W5-UI02.3 | todo | — | — |
| W5-SC01 | todo | — | — |
| W5-SC02 | todo | — | — |

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- W5-UI02.1: with a v1 network chosen, `/data` renders the Data Explorer header (its description names the network) and that network's Forecast trust only. The legacy block renders only when no v1 network exists or the network list failed, the same rule `/scenarios` follows (W3 lead decision, `v1-mocks.ts` `withoutV1Networks`). While the list loads, nothing legacy is fetched. The "Seven-Day Pulse" tab stays; that view is legacy-only and its top bar says "Simulated network".
- W5-UI02.2: the effects rows sit in a native `<details>` ("Show rows · N location × product rows", "Hide rows" when open), so it needs no script and keyboard and screen readers get it for free. Table headers and cells wrap so all six columns fit a card at 1280; at 390 the table still scrolls inside its labeled region. The column texts are unchanged (pinned by `method-comparison.test.tsx`).
- The connected legacy check in `data-explorer.spec.ts` now calls `withoutV1Networks`, like the legacy connected Scenario Lab specs.

## Gotchas

- `textContent()` of `body` includes the Next dev RSC payload script; use `innerText()` for "page contains no X" checks.
- A 401 from a legacy read calls `onUnauthorized` and ends the presenter session in the browser; a mock that only wants the legacy fixture should answer 403.

## Change requests

### CR-w5-screens-1 — `data-label.spec.ts` pins the legacy block beside a chosen network
- **File(s):** `apps/web/tests/e2e/data-label.spec.ts` (w5-polish)
- **Exact change:** in the test at line 66 (`/data with a ${kind} chosen labels that network in the top bar and the legacy block as simulated`), replace `await expect(page.locator("[data-explorer-source]")).toContainText(/simulated network/i);` with `await expect(page.locator("[data-explorer-source]")).toHaveCount(0);`, retitle it `/data with a ${kind} chosen labels that network in the top bar and shows no legacy block`, and update the comment above it (lines 62-63) to say the legacy block no longer renders with a chosen network (W5-UI02.1). The top-bar assertions stay as they are and still pass.
- **Why:** W5-UI02.1 removes the legacy block when a v1 network is chosen; this test asserts that block is there, so it fails twice (`element(s) not found`) on this branch. The other five tests in the file pass.
- **Unblocks:** CI on the `w5-screens` PR (W5-UI02.1). The local `quick`/`full` gates do not run e2e.
- **Status:** open

### CR-w5-screens-2 — the connected journey reads collapsed effects rows
- **File(s):** `apps/web/tests/e2e/v1-connected-journey.spec.ts` (w5-polish / lead connected harness)
- **Exact change:** before line 51 (`const effects = results!.getByRole("region", { name: /^Effects table for EGP-PI-inspired/ })…`), add `await results!.getByRole("region", { name: "EGP-PI-inspired", exact: true }).getByText("Show rows").click();`, and after reading the headers add `expect(await effects.count()).toBeGreaterThan(0);` so the name check can't pass on zero rows.
- **Why:** W5-UI02.2 puts each card's rows behind a "Show rows" disclosure. Playwright's `getByRole` skips hidden elements, so without the click `allTextContents()` returns `[]` and the "locations are named" check passes vacuously.
- **Unblocks:** keeps the connected journey's location-name check meaningful (W5-UI02.2). Not run locally (connected).
- **Status:** open

## Escalations

- none
