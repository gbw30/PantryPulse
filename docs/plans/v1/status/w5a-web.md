# Status — `w5a-web`


**Lane:** `w5a-web` · **Branch:** `lane/w5a-web` · **Base SHA:** `51dab11` · **Last update:** `<YYYY-MM-DD HH:MM>` · **Head:** `<sha>`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5A-L01 (lead) | done | this commit | `npm run check` → types, lint, ruff pass; 2269 API tests passed, 0 skipped. Added `d3-geo` 3.1.2, `topojson-client` 3.1.0, `us-atlas` 3.0.1 (all ISC), `@types/d3-geo` 3.1.1, `@types/topojson-client` 3.1.5; `us-cities.json` (281 places, Natural Earth, public domain) |
| W5A-01 | done | `8e2c7a0` (rename) + this commit | `vitest run tests/unit/tokens.test.ts tests/unit/ui-primitives.test.tsx` → 87 passed (red first: 37 failed on the old values); `npm run test:unit -w apps/web` → 32 files, 298 passed + 14 node tests, 0 skipped; `playwright test theme.spec.ts scaffold.spec.ts` → 6 passed (red first: 2 failed); `npm run typecheck`, `npm run lint` → pass. API suite not run (no Python change, lead call) |
| W5A-02 | todo | — | — |
| W5A-03 | todo | — | — |
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

## Gotchas

- `--pp-warning-fill` is 2.2:1 on canvas and 2.3:1 on surface (below 3:1 for marks), so a medium marker must keep its shape and text label (W5A-04).
- 35 files under `apps/web/src` draw their own `rounded-xl`/`rounded-lg border … bg-card` boxes instead of `Card` (only 8 files use `Card`), so the ruled `Card` does not reach them.

## Change requests

### CR-`<lane>`-1 — `<title>`
- **File(s):** `<lead-only or out-of-lane path>`
- **Exact change:** `<what>`
- **Why:** `<reason, with evidence>`
- **Unblocks:** `<task IDs>`
- **Status:** open | approved | rejected (decided by the orchestrator with Gabriel)

## Escalations

- `<date>` — `<task>` — reason ([ORCHESTRATION.md §5](../ORCHESTRATION.md#5-escalation-stop-and-report) item n) — smallest failing case: `<path or snippet>`
