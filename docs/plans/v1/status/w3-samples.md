# Status — `w3-samples`

**Lane:** `w3-samples` · **Branch:** `lane/w3-samples` · **Base SHA:** `0a4959359a447233e8ca5eea87b1917d70bd7de8` · **Last update:** `2026-11-08` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W3-P01 | done | see `git log` (W3-P01) | `uv run --frozen pytest -q tests/samples/test_pantry_sample.py` → 7 passed, 0 skipped |
| W3-P02 | todo | — | — |
| W3-P03 | todo | — | — |
| W3-P04 | todo | — | — |

Status values: `todo`, `in progress`, `done`, `blocked (<reason or CR id>)`.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- Samples are generated as CSV text per template (`SampleNetwork.files`) and validated by `validate_files`, so the seed, the template examples and the tests share one source — W3-P01.
- City-level coordinates are rounded to 2 decimals and the required `street` column reads "No street address (sample)" (no digits), so no sample points at a real building — W3-P01.
- Demand follows real weekdays (busy Saturdays, quiet Sundays), so a sample generated on a later day has different quantities; determinism is per (seed, date) — W3-P01.

## Gotchas

## Change requests

## Escalations
