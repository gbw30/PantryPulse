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
| W1-W04 | todo | — | — |
| W1-W05 | todo | — | — |
| W1-W06 | todo | — | — |
| W1-W07 | todo | — | — |
| W1-W08 | todo | — | — |

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
- The top-bar "Simulated network" pill is unchanged: the existing screens still read the demo network until they are rewired to v1 networks. — W1-W02

## Gotchas

- `useRef` "alive" flags must be set to `true` in the effect body, not only cleared in cleanup: dev Strict Mode runs the cleanup once before the real mount, which silently stopped the import poll loop. — W1-W03b
- `getByRole("combobox", { name: "Network" })` also matches "Network timezone"; use `exact: true`. — W1-W03b

- In Vitest's jsdom environment `import.meta.url` is not a `file:` URL; `tests/unit/contract-examples.ts` uses `__dirname` to read contract examples. — W1-W03a

- Every shell page now reads `GET /networks`. Older e2e specs with strict "unexpected request" mocks must answer it (done for `forecasting-integration.spec.ts` with the `NetworkList` example). — W1-W02

- Components that fade in with `motion` (`initial: { opacity: 0 }`) stay invisible in jsdom; unit tests must render under reduced motion. — W1-W01

## Change requests

(none yet)

### Contract example notes (no change requested)
- `ImportStatus.json`'s failure message names "North County Pantry Network", which `NetworkList.json` also lists as existing. The A07 e2e therefore mocks the before-import list without that network.
- `TemplateCatalog.json` lists two of the seven templates; `import-upload.spec.ts` clones those two entries to stand in for the other five.

## Escalations
