# Status — `w5-polish`

**Lane:** `w5-polish` · **Branch:** `lane/w5-polish` · **Base SHA:** `81c551bc2e232362f0e63a7a00126ef1ca863fb8` · **Last update:** `2026-11-12` · **Head:** see `git log`

Skills check (2026-11-12): `/jmo-workflow:better-ui` loaded; `/jmo-workflow:animate` listed in this session. `visual-review` loaded.

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5-UI01 | done | (this commit) | Connected stack (`stack-up.sh`, schema `ppor_demo_pppolish_1112030601`, real API, PostgreSQL and production worker; real forecast.v1 runs and a Hub → pantries only, 2-day comparison through the queue), production build of base `81c551b`: `RUN=/tmp/pppol1 PP_E2E_PRODUCTION=1 PP_EVIDENCE_DIR=v1-before run-e2e.sh --config tests/e2e/connected/evidence.config.ts` → 1 passed (1.1 m); 54 screenshots (import, settings, atlas ranking Pantry and Retail, site inspector, forecast trust, comparison, decisions, print × 1440×900, 1280×720, 390×844 × light/dark) in `docs/pantrypulse/visual-evidence/v1-before/` |
| W5-UI02 | todo | — | — |
| W5-UI03 | todo | — | — |
| W5-UI04 | todo (depends on W5-D01 merged) | — | — |
| W5-UI05 | todo | — | — |

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

- The connected stack's run directory must be short (`/tmp/pppol1`): AF_UNIX socket paths are capped at 107 bytes, and the session scratchpad path is longer.
- The API log (`$RUN/api.log`) is block-buffered, so it can look empty while the browser is talking to the API.
- Full-page screenshots draw the sidebar only to the first viewport height (it is `h-svh`); that is a capture artifact, not a layout bug.

## Held until `w5-screens` merges (orchestrator, 2026-11-12)

- **Do not edit** `apps/web/tests/e2e/data-label.spec.ts` (CR-w5-screens-1) or `apps/web/tests/e2e/v1-connected-journey.spec.ts` (CR-w5-screens-2); both arrive with the post-screens `origin/v1-local` merge.
- **W5-UI05 network selector, accessible-name part:** the full network name joins the switcher's accessible name only after that merge, in the same commit as the update to `data-label.spec.ts:43,69` (they find the switcher as `{ name: "Network", exact: true }`). The truncation lands now.
- **CR-w5-screens-4 (approved, Gabriel 2026-11-12):** after that merge, delete `overview/live-source.ts`'s own `pluralize` (it writes "boxs"), re-export `pluralize` from `data-explorer/format`, and pin "boxes" on an Overview path (inspector or ranking). Same batch as the accessible-name change.

## Change requests

None filed by this lane.

## Escalations

None.
