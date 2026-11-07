# Status — `w1-web`

**Lane:** `w1-web` · **Branch:** `lane/w1-web` · **Base SHA:** `39090104222e6a67b60f8d9fa0c9e798c68a38d7` · **Last update:** `2026-11-07` · **Head:** see `git log`

Mocked e2e runs prove UI behavior against the contract examples in `packages/contracts/examples/v1/`, not the connected app.

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W1-W01 | done | `a79162b` (cherry-pick 647f6a8) + test port commit | `npm run test:unit --workspace @pantrypulse/web` → Vitest 6 files / 47 passed; node --test 11 passed, 0 skipped (includes `forecast-proxy.test.mjs`). Screenshots `artifacts/w1-web/647f6a8-1440x900.png`, `647f6a8-390x844.png` (artifacts/ is gitignored). |
| W1-W02 | todo | — | — |
| W1-W03a | todo | — | — |
| W1-W03b | todo | — | — |
| W1-W04 | todo | — | — |
| W1-W05 | todo | — | — |
| W1-W06 | todo | — | — |
| W1-W07 | todo | — | — |
| W1-W08 | todo | — | — |

### W1-W01 port record

Ported unchanged from `b54ec7c`: `atlas-layout.test.ts`, `network-atlas.test.tsx`, `site-inspector.test.tsx`, `static-fixture.test.ts`, `status.test.ts` (plus a `// covers: V1-A21` first line). Not ported: `outlook.test.ts`, `outlook-chart.test.tsx`. First run: 18 failed / 29 passed. Test-side changes (no component edits):

- `static-fixture.test.ts` (8 failing): `overviewSourceFor` moved from `static-fixture.ts` to `sources.ts`, and its default is now `liveWithFallbackSource` (PP-51 `eb7cbaf`). Import from `sources`; expect the live-with-fallback default.
- `network-atlas.test.tsx` (4 failing): same move; spy on `sources.overviewSourceFor`.
- `site-inspector.test.tsx` (6 failing): `SiteInspector` gained a required `provenance` prop (`9d66945`) → pass the fixture provenance. Tab content now crossfades from opacity 0 (`16c47d7`), which jsdom never animates → mock `useReducedMotion` to `true`, a path the component already supports.

Visual check of 647f6a8: at 1440×900 the builder panel is 24rem and step-1 controls fit without wrapping; at 390×844 the layout is a single column. Pre-existing, unrelated: the full-page 1440 capture shows the fixed sidebar ending at the viewport height (screenshot artifact), and at 390 the "Simulated research preset" select sits a few px wider than its siblings.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

## Gotchas

- Components that fade in with `motion` (`initial: { opacity: 0 }`) stay invisible in jsdom; unit tests must render under reduced motion. — W1-W01

## Change requests

## Escalations
