# Status — `w5-packaging`

**Lane:** `w5-packaging` · **Branch:** `lane/w5-packaging` · **Base SHA:** `81c551bc2e232362f0e63a7a00126ef1ca863fb8` · **Last update:** `2026-11-12 03:20` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5-PK01 | done | this commit | `node --test scripts/testing/tests/docker-tests.test.cjs` → 3 passed (RED first: `compose.test.yaml` missing). `npm run test:docker` (with `.env.lane`, project `pp-packaging-tests`) → `2220 passed, 2 warnings in 423.74s`; in-container `require-test-evidence.py` → "2220 backend tests completed without skips or failures"; exit 0, 7 min 22 s wall clock incl. image build; JUnit `artifacts/testing/api-linux.xml` |
| W5-PK03 | in progress | — | — |
| W5-PK04 | todo | — | — |
| W5-PK02 | todo | — | — |
| W5-PK05 | todo | — | — |

Order: PK01 → PK03 → PK04 → PK02 → PK05. PK02's `--enforce` can reach exit 0 only once A03 (PK03's test) and A19 (PK04's test) are mapped; the wave file lists PK02–PK04 as "depends on: none".

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- `compose.test.yaml` runs the suite with `pytest --junitxml` and then `scripts/quality/require-test-evidence.py` on the same file (the CI skip check). The backup's `--require-no-skips` flag is not a pytest option in this tree. — W5-PK01.
- The runner always uses its own project, `${COMPOSE_PROJECT_NAME:-pantrypulse}-tests`, so its `down -v` can never reach the app stack, even with a lane's `COMPOSE_PROJECT_NAME` loaded. — W5-PK01.
- Mounts are the exact read-only paths the suite reads (`apps/api/{app,tests,scripts,migrations,alembic.ini,pyproject.toml,uv.lock}`, `data`, `docs`, `packages/contracts`, `scripts`, `compose.compute.yaml`), not the whole repo, so `.env*` and `.pantrypulse/` never enter the container; the test asserts that. Only `artifacts/testing` is writable. — W5-PK01.

## Gotchas

- `apps/api/tests` read repo-root files (`compose.compute.yaml`, `docs/plans/v1/README.md`, `data/**`, `scripts/or/**`, `packages/contracts/examples`). A new root-level read needs a new mount in `compose.test.yaml`, or `npm run test:docker` fails with a missing file.

## Change requests

None.

## Escalations

None.
