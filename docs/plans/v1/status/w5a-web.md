# Status — `w5a-web`


**Lane:** `w5a-web` · **Branch:** `lane/w5a-web` · **Base SHA:** `51dab11` · **Last update:** `<YYYY-MM-DD HH:MM>` · **Head:** `<sha>`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5A-L01 (lead) | done | this commit | `npm run check` → types, lint, ruff pass; 2269 API tests passed, 0 skipped. Added `d3-geo` 3.1.2, `topojson-client` 3.1.0, `us-atlas` 3.0.1 (all ISC), `@types/d3-geo` 3.1.1, `@types/topojson-client` 3.1.5; `us-cities.json` (281 places, Natural Earth, public domain) |
| W5A-01 | done | `8e2c7a0` (rename) + this commit | `vitest run tests/unit/tokens.test.ts tests/unit/ui-primitives.test.tsx` → 87 passed (red first: 37 failed on the old values); `npm run test:unit -w apps/web` → 32 files, 298 passed + 14 node tests, 0 skipped; `playwright test theme.spec.ts scaffold.spec.ts` → 6 passed (red first: 2 failed); `npm run typecheck`, `npm run lint` → pass. API suite not run (no Python change, lead call) |
| W5A-02 | done | this commit | `playwright test v1-shell.spec.ts v1-a11y.spec.ts presenter-session.spec.ts overview-layout.spec.ts --project=chromium --workers=2` → 42 passed, 0 skipped (red first: 5 of the 6 new or rewritten shell tests failed on the sidebar layout; the 390 px drawer test passed as a guard); whole e2e suite once before the last two edits → 244 passed, 23 skipped, 1 failed (`overview-layout.spec.ts:259`, fixed in the test, see Gotchas); `npm run test:unit -w apps/web` → 32 files, 299 passed + 14 node tests, 0 skipped; `npm run typecheck`, `npm run lint` → pass. API suite not run (no Python change, lead call). Look checked on local screenshots only (1440, 1280, 1024 dark, 390); the ux-critic review is still due |
| W5A-03 | done (parts a and b) | `44eb49d` (a) + this commit (b) | **Part b:** deleted the 14 orphans in `components/overview/`, their unit tests (`atlas-layout`, `site-inspector`, `static-fixture`) and `overview.spec.ts`, `overview-layout.spec.ts`, `overview-live.spec.ts` (every case tested the fixture atlas or the pre-v1 snapshot source; the v1 ranking, inspector and network switching are covered by `atlas-ranking.spec.ts`, `v1-shell.spec.ts`, `v1-connected-import.spec.ts`). `atlas-motion.ts` (kept by the plan) is now imported by nothing. Rewrote on a mocked v1 network: `scaffold.spec.ts` smoke, `theme.spec.ts` dark Overview axe (ranking + inspector, 1440 and 390). `v1-motion.spec.ts`: deleted the demo-atlas screen, the pause-control and the storage-unavailable cases (no screen draws the supply-link flow until the stage 2 map). `network-atlas.test.tsx`: fixture cases and `@ts-expect-error` lines deleted. `npm run typecheck` → exit 0; grep for each deleted module and for `W5A-03b` → no import, no mark. Whole mocked e2e suite (chromium, workers=2) → 180 passed, 0 failed, 22 skipped (all `PP_RUN_CONNECTED` gates); `npm run test:unit -w apps/web` → 30 files, 272 passed + 14 node tests, 0 skipped; `npm run check` with `.env.lane` → all checks passed, 2269 API tests passed, 0 skipped. Connected suite and `visual-evidence.capture.ts` not run (need the real API). **Part a:** Red first: `overview-states.spec.ts` 4 failed (headings not found), `units.test.ts` failed (no `lib/units`). Then `playwright test overview-states.spec.ts --project=chromium --workers=2` → 4 passed (signed out and no network, axe at 1440×900 and 390×844); whole mocked e2e suite once before the fixme marks → 170 passed, 79 failed, 23 skipped; after → 177 passed, 0 failed, 95 skipped (72 `test.fixme` "W5A-03b: fixture atlas removed" in overview, overview-layout, overview-live, scaffold, theme (dark atlas a11y) and v1-motion (demo atlas, pause control, storage unavailable) + the 23 skipped before); `npm run test:unit -w apps/web` → 33 files, 298 passed, 6 skipped (the fixture-atlas cases in `network-atlas.test.tsx`, `it.skip` with the same comment); `npm run typecheck`, `npm run lint` → exit 0. API suite not run (no API change). Part b deletes the orphans and the fixme/skip tests |
| Stage 1 gate (lead) | done | this commit | Candidate `68aad7e`. `PP_TEST_DATABASE_URL`/`PP19_TEST_DATABASE_URL`=lane DB, `PP19_TEST_SCHEMA_ISOLATION=1` `node scripts/quality/run.cjs full` → 8/8 PASS (web typecheck, web lint, api lint, api tests, web unit tests, web build, contract drift, database migrations); `uv run --frozen pytest -rs -q` (same env) → 2269 passed, 0 skipped. Production build with `.env.lane`; `RUN=/tmp/ppw5a1 stack-up.sh` (schema `ppor_demo_ppatlas_1116034750`, real API, PostgreSQL and production worker, no egress); `PP_E2E_PRODUCTION=1 PP_EVIDENCE_DIR=v1-w5a-look run-e2e.sh --config tests/e2e/connected/evidence.config.ts` → 1 passed, 54 screenshots (9 screens × 1440×900, 1280×720, 390×844 × light/dark) in `docs/pantrypulse/visual-evidence/v1-w5a-look/`; `run-e2e.sh tests/e2e/{v1-a11y,v1-full-journey,v1-connected-import}.spec.ts --project=chromium --workers=1` → 25 passed, 0 skipped. Stack stopped. The signed-out and no-network Overview states are not in the connected capture; `overview-states.spec.ts` (mocked) covers them |
| W5A-04 | todo | — | — |
| W5A-05 | todo | — | — |
| W5A-06 | todo | — | — |
| W5A-07 | todo | — | — |
| W5A-08 | todo | — | — |
| W5A-09 | todo | — | — |

Status values: `todo`, `in progress`, `done`, `blocked (<reason or CR id>)`.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- `--pp-action-soft` is an alias of `--pp-tint` (the prototype uses one sage for both) — W5A-01.
- New `--pp-warning-fill` `#d99a1c` for the medium marker and `--chart-3`; `--pp-warning` `#7d5a12` is the text and border color — W5A-01.
- `--pp-neutral` stays a mark-only color (icons, markers, borders), darkened to `#6f7c80` so it holds 3:1 on canvas, surface and surface-muted; never text — W5A-01.
- The neutral badge is `Badge variant="secondary"` (tint ground, ink text). Every current badge is `outline`, so none changes — W5A-01.
- `Card` loses its box, shadow and side padding; `CardTitle` is serif 19 px/500. `design-lab/layout.tsx` is unchanged: it inherits the root font variables and does not use the serif — W5A-01.

- The header is not sticky at 768 px and up (two rows are 118 px, and the prototype's header scrolls away); below 768 px the one-row bar stays sticky — W5A-02.
- At 768 px and up the header's sample label is the network switcher's badge in the context bar; the "Sample data — fictional" pill shows only below 768 px, where the switcher is in the drawer — W5A-02.
- In the menu row the session text ("Presenter session", "No account · read-only demo") is visually hidden below 1400 px so the row fits 1280 px; the button keeps its name — W5A-02.
- `PageActions` finds the slot with `header [data-slot='page-actions']` when it renders, so it only works inside `AppShell` — W5A-02.

## Gotchas

- `--pp-warning-fill` is 2.2:1 on canvas and 2.3:1 on surface (below 3:1 for marks), so a medium marker must keep its shape and text label (W5A-04).
- 35 files under `apps/web/src` draw their own `rounded-xl`/`rounded-lg border … bg-card` boxes instead of `Card` (only 8 files use `Card`), so the ruled `Card` does not reach them.

- Screen copy said "in the sidebar" or "from the sidebar" in 8 places; W5A-03a changed them to "in the menu" / "from the menu", with the three tests that assert the wording.
- Since W5A-03a the Overview is in the top bar's no-network-data set (`top-bar.tsx` `NO_NETWORK_DATA`): it no longer renders the fixture, so it has no "Simulated network" pill. `data-label.spec.ts` and `shell-labels.test.tsx` moved `/overview` into that group.
- `PresenterSignIn` (`shell/presenter-footer.tsx`) is the sign-in button and dialog, split out of `PresenterFooter` so the signed-out Overview opens the same dialog. Signed out, `/overview` has two "Presenter sign in" buttons (menu and page); `presenter-session.spec.ts` now starts on `/import` so its unscoped locators stay unique.
- The header is 118 px at 1280 and 1440, and 162 px at 1024 where the menu wraps. The fixture overview is 887 px tall, so at 1440×900 the page now scrolls 105 px (43 px before). `overview-layout.spec.ts:259` compared viewport positions across that scroll; it now scrolls to the top before the reset check. `network-atlas.tsx:385` still assumes a 3.5rem header (W5A-03 rewrites it).
- Pages render their own `<header>` inside main, so tests should find the shell header with `getByRole("banner")`, not `locator("header")`.

## Change requests

### CR-`<lane>`-1 — `<title>`
- **File(s):** `<lead-only or out-of-lane path>`
- **Exact change:** `<what>`
- **Why:** `<reason, with evidence>`
- **Unblocks:** `<task IDs>`
- **Status:** open | approved | rejected (decided by the orchestrator with Gabriel)

## Escalations

- `<date>` — `<task>` — reason ([ORCHESTRATION.md §5](../ORCHESTRATION.md#5-escalation-stop-and-report) item n) — smallest failing case: `<path or snippet>`
