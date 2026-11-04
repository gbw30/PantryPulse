# Status — `<lane>` (e.g. `w1-data`)

Copy this file to `docs/plans/v1/status/<lane>.md` on your own lane branch only, and commit it with every task. The orchestrator reads it with `git show origin/lane/<wave>-<lane>:docs/plans/v1/status/<lane>.md`. Never edit another lane's status file.

**Lane:** `<lane>` · **Branch:** `lane/<wave>-<lane>` · **Base SHA:** `<sha>` · **Last update:** `<YYYY-MM-DD HH:MM>` · **Head:** `<sha>`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W1-D01 | done | `abc1234` | `uv run --frozen pytest -q tests/enrichment/test_fixtures_shape.py` → 2 passed, 0 skipped |
| W1-D02 | in progress | — | — |
| W1-D03 | blocked (CR-w1-data-1) | — | failing: `<test id>` |

Status values: `todo`, `in progress`, `done`, `blocked (<reason or CR id>)`.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- `<decision>` — why — which task. (Only choices the plan left to the builder.)

## Gotchas

- `<non-obvious finding>` — the orchestrator moves durable ones to the vault at wave end.

## Change requests

### CR-`<lane>`-1 — `<title>`
- **File(s):** `<lead-only or out-of-lane path>`
- **Exact change:** `<what>`
- **Why:** `<reason, with evidence>`
- **Unblocks:** `<task IDs>`
- **Status:** open | approved | rejected (decided by the orchestrator with Gabriel)

## Escalations

- `<date>` — `<task>` — reason ([ORCHESTRATION.md §5](../ORCHESTRATION.md#5-escalation-stop-and-report) item n) — smallest failing case: `<path or snippet>`
