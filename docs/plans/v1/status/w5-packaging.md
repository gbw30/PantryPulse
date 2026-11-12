# Status — `w5-packaging`

**Lane:** `w5-packaging` · **Branch:** `lane/w5-packaging` · **Base SHA:** `81c551bc2e232362f0e63a7a00126ef1ca863fb8` · **Last update:** `2026-11-12 03:20` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5-PK01 | done | this commit | `node --test scripts/testing/tests/docker-tests.test.cjs` → 3 passed (RED first: `compose.test.yaml` missing). `npm run test:docker` (with `.env.lane`, project `pp-packaging-tests`) → `2220 passed, 2 warnings in 423.74s`; in-container `require-test-evidence.py` → "2220 backend tests completed without skips or failures"; exit 0, 7 min 22 s wall clock incl. image build; JUnit `artifacts/testing/api-linux.xml` |
| W5-PK03 | done | `083885b` (+ evidence commit) | `node --test scripts/testing/tests/egress-journey.test.cjs` → 6 passed (RED first: module missing). `node scripts/testing/egress-journey.cjs` (with `.env.lane`, fresh `pp-packaging` install, code at `083885b`) → PASS in 2 min 0 s: 12/12 journey steps (sign-in; A06; A07 rejected, no network created; A10 address import with live Census geocoding; A12 forecast + backtest and A13 ranking + projection on both samples; A14 Pantry both transfer modes 5/5 verified; A15 Retail units and USD 3/3 verified; A16 export), 1 outbound destination `geocoding.geo.census.gov:443` (allowed, the positive control), 0 violations, 0 secret findings in compose logs, `.next` output, Git tree and history. Report: [docs/testing/evidence/egress-2026-11-12.json](../../../testing/evidence/egress-2026-11-12.json) |
| W5-PK04 | done | this commit | `node --test scripts/testing/tests/bench-report.test.cjs` → 2 passed (RED first: `run-all.cjs` and HARDWARE.md missing; a hand-edited number in the table fails it). `node scripts/bench/run-all.cjs` (with `.env.lane`) → exit 0 in 22 min 33 s: build `--no-cache` 2 min 07 s, first start 27 s, idle 420 MiB (peak 458), images 2.1 GiB; A09 import 4,500,000 demand rows + 200,000 batches, job steps 1 min 22 s, peak 503 MiB; A17 forecast 50,000 series 52 s, peak 1,092 MiB; Pantry comparison 100 × 500 324 s of 690 s, peak 1,076 MiB; Retail units 320 s + USD 210 s, peak 1,423 MiB; all optimizer products OPTIMAL, union check passed 11/11. Artifact: [docs/testing/evidence/bench-2026-11-12.json](../../../testing/evidence/bench-2026-11-12.json); [HARDWARE.md](../../../pantrypulse/HARDWARE.md) confirms 4 cores and 8 GiB for Docker and keeps 15 GB of disk as provisional (partly measured). **Pre-D02 bench:** `bench_import.py` at `d2c158b` (4,500,000 rows); after w5-data D02 (CR-w5-data-1) the maximum is 4,455,000; re-measure A09 when D02 merges (orchestrator, 2026-11-12) |
| W5-PK02 | done | this commit | Step 1 on the base tree: `node scripts/testing/story-coverage.cjs --enforce` → exit 1, uncovered A01, A03, A18, A19. After: → exit 0, `covered 24/24`, no stale entries. `node --test scripts/testing/tests/story-coverage.test.cjs scripts/testing/tests/recorded-runs.test.cjs scripts/quality/tests/story-coverage.test.cjs` → 10 passed (RED first: stale manifest path accepted; `check-recorded-runs.cjs` missing). `node scripts/testing/check-recorded-runs.cjs` → exit 1: A01, A18 and A24 (pull) have no recorded runs yet (open until a person records them; never skipped). Guide: [docs/testing/README.md](../../../testing/README.md) |
| W5-PK05 | done | this commit | `node --test scripts/testing/tests/check-version-pin.test.cjs scripts/testing/tests/readme.test.cjs` → 9 passed (RED first: script missing, then the real README had no pin and no quickstart). `node scripts/testing/check-version-pin.cjs` → "README.md and compose.yaml both pin 0.1.0". README: quickstart at the top (prerequisites, `git clone` + `docker compose up --build` with the no-published-images note, the login line, first-run time 2 min 07 s + 27 s from HARDWARE.md, sample, import, `down -v` warning, troubleshooting, macOS untested, the W2-06 known limits). INSTALLATION.md: contributor setups table and compose files; stale statements fixed (vitest, migrations, gates). `research-claims-check` on README.md → PASS (table below) |

Order: PK01 → PK03 → PK04 → PK02 → PK05. PK02's `--enforce` can reach exit 0 only once A03 (PK03's test) and A19 (PK04's test) are mapped; the wave file lists PK02–PK04 as "depends on: none".

### research-claims-check (W5-PK05, README.md at this commit)

| Check | Result | Where |
|---|---|---|
| EGP-PI named "inspired", bounded; DOI 10.1111/itor.70252, first published online 11 September 2026 | PASS | README.md:83-85 |
| Adapted and not-reproduced constructs listed | PASS | README.md:87-88 |
| Simulated data, locations not individuals; no real-world outcome claims ("in this simulated scenario") | PASS | README.md:89-91 |
| Quantiles not calibrated, no stockout probabilities; "never changes your stock", simulation only | PASS | README.md:3, 78 |
| No "exact reproduction", "reduces poverty", "fairer distribution", "AI approves", "auto-order" | PASS | `scripts/testing/tests/readme.test.cjs` guards it |
| `GET /api/v1/allocation-methodology` returns DOI, date, adapted constructs and limitations | **FAIL (not this lane's file)**: it returns methods, modes and limitations but no DOI, date or adapted constructs | `apps/api/app/routers/planning.py:37-50`; for the owner (lead) |
| Methodology screen shows the date | UNVERIFIED here (the DOI appears in `apps/web/src/components/methodology/methodology-view.tsx`) | — |
| A forced EGP failure shows method-unavailable; TEST-ELIG-01 exists | UNVERIFIED; no test named TEST-ELIG-01 found in `apps/api/tests` | — |

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

- Egress is captured by packet headers on the project bridge (`scripts/testing/egress-sniff.py`, profile `egress` in `compose.test.yaml`), not by a logging HTTP proxy: Next.js's Node `fetch` ignores `HTTPS_PROXY`, so a proxy would miss web-side calls such as telemetry. Each outbound TCP connection is named by its TLS server name; one without a server name, and any outbound UDP except DNS, is flagged. — W5-PK03.
- The journey is driven over HTTP through the web's same-origin proxy, not by the connected Playwright specs: those need direct PostgreSQL access (`db_probe.py`, `seed_samples.py`), which the installed stack doesn't publish. — W5-PK03.
- The egress harness and the benchmark build with lane-local image tags (`<project>-api:local`, `<project>-web:local`) through a generated override that changes only `image:`; `docker compose build` with `compose.yaml` alone would retag `ghcr.io/gbw30/pantrypulse-*:0.1.0`, which the main install on this machine also uses. — W5-PK03/PK04.
- `user-stories.json` is not a hand-copied list of test files: coverage comes from the `@V1-Axx` / `covers:` tags, which the script finds, so other lanes' new tests count without editing this lane's file. `tests` holds only untagged evidence checks, and `--enforce` now fails if one names a missing file. `--report` lists the full map. — W5-PK02.
- A01, A18 and A24 (pull path) map to `scripts/testing/check-recorded-runs.cjs`, which validates per-OS run records in `docs/testing/evidence/runs/` and exits 1 while none exist. It is never skipped; those criteria stay open until a person records the runs. — W5-PK02.

- The benches run natively under `taskset -c 0-5`, not inside the worker container: `scripts/or/bench_v1.py` calls `git`, which the API image lacks, and `scripts/or/` is outside this lane. Peak RSS and CPU time come from `getrusage(RUSAGE_CHILDREN)`. — W5-PK04.
- HARDWARE.md's measurement table is generated from the JSON artifact by `renderTable`, and the test re-renders it, so no number can be typed by hand. The requirement prose around it states what is measured and what is not. — W5-PK04.

## Gotchas

- Don't commit while a benchmark runs: `bench_forecast.py` and `bench_v1.py` record `git rev-parse HEAD` when they start, so a mid-run commit splits one run across two commits (PK04 recorded `083885b` and the docs-only `016b429`).
- The reference laptop is shared: at the A17 forecast the 1-minute load average was 28 on 16 CPUs. Re-measure on an idle machine before quoting tight margins.
- Docker Desktop forwards container DNS from the VM itself (`192.168.65.6 → 192.168.65.7` on `services1`), never across the project bridge, so DNS cannot be attributed to a stack there. Outbound TCP SYNs and TLS ClientHellos do cross the bridge with the container's address.

- `apps/api/tests` read repo-root files (`compose.compute.yaml`, `docs/plans/v1/README.md`, `data/**`, `scripts/or/**`, `packages/contracts/examples`). A new root-level read needs a new mount in `compose.test.yaml`, or `npm run test:docker` fails with a missing file.

## Change requests

None.

## Escalations

None.
