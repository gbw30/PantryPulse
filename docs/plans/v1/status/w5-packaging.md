# Status — `w5-packaging`

**Lane:** `w5-packaging` · **Branch:** `lane/w5-packaging` · **Base SHA:** `81c551bc2e232362f0e63a7a00126ef1ca863fb8` · **Last update:** `2026-11-15 07:35` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5-PK01 | done | this commit | `node --test scripts/testing/tests/docker-tests.test.cjs` → 3 passed (RED first: `compose.test.yaml` missing). `npm run test:docker` (with `.env.lane`, project `pp-packaging-tests`) → `2220 passed, 2 warnings in 423.74s`; in-container `require-test-evidence.py` → "2220 backend tests completed without skips or failures"; exit 0, 7 min 22 s wall clock incl. image build; JUnit `artifacts/testing/api-linux.xml` |
| W5-PK03 | done | `083885b` (+ evidence commit) | `node --test scripts/testing/tests/egress-journey.test.cjs` → 6 passed (RED first: module missing). `node scripts/testing/egress-journey.cjs` (with `.env.lane`, fresh `pp-packaging` install, code at `083885b`) → PASS in 2 min 0 s: 12/12 journey steps (sign-in; A06; A07 rejected, no network created; A10 address import with live Census geocoding; A12 forecast + backtest and A13 ranking + projection on both samples; A14 Pantry both transfer modes 5/5 verified; A15 Retail units and USD 3/3 verified; A16 export), 1 outbound destination `geocoding.geo.census.gov:443` (allowed, the positive control), 0 violations, 0 secret findings in compose logs, `.next` output, Git tree and history. Report: [docs/testing/evidence/egress-2026-11-12.json](../../../testing/evidence/egress-2026-11-12.json) | **Re-run after verifier round 2 (2026-11-15):** `node scripts/testing/egress-journey.cjs` (with `.env.lane`) at `9541f6f`, tree clean → PASS in 2 min 32 s: 13/13 steps (the A11 step saves a random dummy Google key after enrichment), one destination `geocoding.geo.census.gov:443` (allowed, the positive control), 0 violations; secrets checked: password, proxy token, presenter password hash, dummy Google key, in compose logs, `.next` output, 103 API response bodies, Git tree and history → 0 findings. Report: [egress-2026-11-15.json](../../../testing/evidence/egress-2026-11-15.json); `node scripts/testing/check-egress-evidence.cjs` → `ok egress-2026-11-15.json`. An earlier run at `47de1bb` failed on a sniffer bug (546 IPv4 frames misread as IPv6 because a MAC began `0x6_`), fixed test-first in `30037e5`
| W5-PK04 | done | this commit | `node --test scripts/testing/tests/bench-report.test.cjs` → 2 passed (RED first: `run-all.cjs` and HARDWARE.md missing; a hand-edited number in the table fails it). `node scripts/bench/run-all.cjs` (with `.env.lane`) → exit 0 in 22 min 33 s: build `--no-cache` 2 min 07 s, first start 27 s, idle 420 MiB (peak 458), images 2.1 GiB; A09 import 4,500,000 demand rows + 200,000 batches, job steps 1 min 22 s, peak 503 MiB; A17 forecast 50,000 series 52 s, peak 1,092 MiB; Pantry comparison 100 × 500 324 s of 690 s, peak 1,076 MiB; Retail units 320 s + USD 210 s, peak 1,423 MiB; all optimizer products OPTIMAL, union check passed 11/11. Artifact: [docs/testing/evidence/bench-2026-11-12.json](../../../testing/evidence/bench-2026-11-12.json); [HARDWARE.md](../../../pantrypulse/HARDWARE.md) confirms 4 cores and 8 GiB for Docker and keeps 15 GB of disk as provisional (partly measured). **Pre-D02 bench:** `bench_import.py` at `d2c158b` (4,500,000 rows); after w5-data D02 (CR-w5-data-1) the maximum is 4,455,000; re-measure A09 when D02 merges (orchestrator, 2026-11-12) | **Re-measured after the w5-data merge (2026-11-15), on a quiet machine:** `node scripts/bench/run-all.cjs` (with `.env.lane`) at `d92021b`, tree clean, exit 0 in 13 min 56 s, host 1-minute load at most 9.5 (the other lanes held heavy work). Build `--no-cache` 60 s, first start 24 s, idle peak 332 MiB; A09 import of 4,500,000 demand rows and 200,000 batches (bench `09b6aba`: 100 pantries, no hub), job steps 53 s, peak 501 MiB; A17 forecast 34 s, peak 1,066 MiB; Pantry comparison 3 min 25 s of 690 s; Retail units 2 min 26 s and USD 2 min 31 s, peak 1,454 MiB; all optimizer products OPTIMAL, union check 11/11. HARDWARE.md, README and [bench-2026-11-15.json](../../../testing/evidence/bench-2026-11-15.json) in `894a5a2`. It replaces a loaded run at `5b56347` (build 4 min 22 s at load up to 43; committed in `d1d9800`). The runner records the host load per step (`5b56347`, RED first: `build load.start` missing), and `readme.test.cjs` also checks the README's import time (RED first: README said 1 min 22 s). Lane tests 29/29, `story-coverage --enforce` 24/24
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
| `node scripts/quality/run.cjs quick` (with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1` exported by hand) | `d1d9800` (after the merge of `v1-local` `2a42698`) | **FAIL** (2026-11-15T01:10Z, host load up to 25 while w5-polish ran its gate): web typecheck, web lint, api lint pass; api tests `9 failed, 2258 passed` in 12 min 16 s, all 9 in `tests/imports/test_import_job.py` with `AdmissionRejected`. Not caused by this lane (it changes nothing under `apps/`); see ESC-w5-packaging-1 |
| **After `/code-review` on #156, head `e45633d`** (with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1` exported by hand) | | |
| `node scripts/quality/run.cjs quick` | `e45633d` | **PASS**, exit 0, 2026-11-15T07:32:59Z: web typecheck, web lint, api lint, api tests all exit 0; `sourceUnchangedDuringRun` true |
| `npm run test:config` | `e45633d` | tests 82, pass 82, fail 0, skipped 0 |
| `node scripts/testing/story-coverage.cjs --enforce` | `e45633d` | exit 0; `covered 21/24; pending 3 (V1-A01, V1-A18, V1-A24)`; `check-egress-evidence.cjs` → `ok egress-2026-11-15.json`; `check-version-pin.cjs` → 0.1.0 |
| **Round 2, final head `8b04600`** (all with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1` exported by hand) | | |
| `node scripts/quality/run.cjs quick` | `8b04600` | **PASS**, exit 0, 2026-11-15T05:59:05Z: web typecheck, web lint, api lint, api tests all exit 0; `sourceUnchangedDuringRun` true (`.claude/state/quality/quick.json`) |
| `node scripts/quality/run.cjs full` | `8b04600` | **PASS**, exit 0, 2026-11-15T06:06:53Z: web typecheck, web lint, api lint, api tests, web unit tests, web build, contract drift, database migrations all exit 0; `sourceUnchangedDuringRun` true (`full.json`). The gate stores no test counts; CI's full job enforces zero API skips |
| `npm run test:config` | `8b04600` | tests 78, pass 78, fail 0, skipped 0 (3.2 s) |
| Fresh `git clone` of the branch without `--depth` (659 commits), `node --test scripts/quality/tests/*.test.cjs scripts/testing/tests/*.test.cjs` | `8b04600` | tests 78, pass 78, fail 0, skipped 0 |
| Same with `git clone --depth 1` (CI's `verify` checkout before CR-w5-packaging-3) | `8b04600` | tests 78, pass 77, fail 1, skipped 0: only `every measurement is tied to a real commit and a timestamp` (the bench commit `d92021b` is not in a depth-1 clone), which CR-3's `fetch-depth: 0` fixes |
| `node scripts/testing/story-coverage.cjs --enforce` | `8b04600` | exit 0; `covered 21/24; pending 3 (V1-A01, V1-A18, V1-A24)`: those three wait for recorded runs (`check-recorded-runs.cjs` exits 1) and print `pending`, never `ok`; A03 and A04 are ok on `egress-2026-11-15.json` (`check-egress-evidence.cjs` → `ok`) |
| **Earlier** | | |
| `node scripts/quality/run.cjs quick` (with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1` exported by hand) | `a1eb4d3` (after merging `v1-local` `8b4fff9`, the heartbeat fix #154) | **PASS** (2026-11-15T02:20Z, host load 4–5): web typecheck, web lint, api lint, api tests all exit 0; `sourceUnchangedDuringRun` true (`.claude/state/quality/quick.json`). The gate prints no test counts |
| (earlier) same, before the merge | `1e251ab` | PASS: web typecheck, web lint, api lint, api tests all exit 0; `sourceUnchangedDuringRun` true (`.claude/state/quality/quick.json`, 2026-11-12T09:44Z) |
| `node scripts/quality/run.cjs full` (with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1` exported by hand) | `1e251ab` | PASS: those four plus web unit tests, web build, contract drift, database migrations, all exit 0; `sourceUnchangedDuringRun` true (`full.json`, 09:51Z). The gate stores no skip counts, so the zero-skip evidence is the rows below. `1e251ab` differs from `0daecf8` only in this status file |
| Earlier quick and full at `0daecf8` (09:24Z, 09:30Z) | `0daecf8` | Both exit 0, but **without** `PP19_TEST_SCHEMA_ISOLATION`: `.env.lane` does not set it and neither did the shell, so the PP19 API suites may have skipped silently there. Not cited as evidence; superseded by the two rows above |
| API suite, zero skips: `uv run --frozen pytest --junitxml=…` then `scripts/quality/require-test-evidence.py` (with `.env.lane`, `PP19_TEST_SCHEMA_ISOLATION=1`) | `61bea71` (no `apps/` change to `0daecf8`: `git diff --stat 61bea71..0daecf8 -- apps` is empty) | `2220 passed, 2 warnings in 565.80s`; "2220 backend tests completed without skips or failures"; exit 0 |
| Web unit, zero skips: `npm run test:unit` in `apps/web` | `0daecf8` | Vitest `Tests 181 passed (181)`, 28 files; `node --test` 14 pass, 0 skipped |
| `npm run test:config` | `0daecf8` | 36 pass, 0 fail, 0 skipped |
| `node --test scripts/testing/tests/*.test.cjs` | `0daecf8` | 28 pass, 0 fail, 0 skipped |
| `/devkit:ship-check` | `0daecf8` / `1e251ab` | Step 1: the rows above. Step 2: local review by the project `verifier` agent at `9f635a8` (+ delta to `6e16e01`); its five findings are fixed in `0daecf8` (see "Review" below). Step 3: security-guidance is not installed (skipped). Steps 4–5: PR and `/code-review` wait for the orchestrator's go (after the w5-data merge). Step 6: not applicable (test tooling and docs) |

### `/code-review` on #156 (local only, `8b4fff9..81bc170`; Gabriel's decisions 2026-11-15)

| Item | Decision |
|---|---|
| 1: README and HARDWARE said 4 CPU cores, but compose.yaml gives the worker `cpus: 6`, and Docker refuses a CPU limit above its CPUs (reproduced: `docker run --cpus 64` → "range of CPUs is from 0.01 to 16.00, as there are only 16 CPUs available") | Fixed in `e45633d`: `renderSummary` reads the worker's limit from compose.yaml; the README states 6 CPUs; tests tie both to compose.yaml (RED first). compose.yaml unchanged; an adjustable worker CPU limit moves to W6, after a 4-CPU measurement |
| 9: bench artifacts recorded absolute `--out` paths (a home directory) | Fixed in `e45633d`: `--out` is passed relative to `apps/api`, where the benches run; `--render` rewrites absolute repo paths in an artifact's commands (RED first). Both artifacts re-rendered: `git diff --word-diff` shows only the three `command` fields per file; `grep -rn "/home/" docs/testing scripts README.md docs/pantrypulse/HARDWARE.md` is empty. `--render` on `bench-2026-11-12.json` fixes its JSON, then cannot render HARDWARE.md (that run predates host-load recording); HARDWARE.md is rendered from `bench-2026-11-15.json` |
| 2: egress staleness ignores `package.json`, `package-lock.json`, `packages/contracts`; 4: a crashed or timed-out check counts as `pending`; 7: `check-version-pin` runs in no gate | Follow-up PR after #156 merges |
| 3: no recorded `--build` run is required; 5: A10 accepts a failed enrichment (the committed run's A10 is "enrichment done"); 6: a failed early run leaves an old local `report.json`; 8: recorded runs never go stale; 10: `sh`/`must`/`sleep` duplicated between the two runners | Known limitations |

### Review round 2 (orchestrator's verifier at `9366474`: FAIL, one blocker; all fixes approved by Gabriel)

| Finding | Fix |
|---|---|
| F3 (blocker): README claimed Linux was tested on Ubuntu 24.04 | `5907f53`: "Ubuntu 24.04 is the supported target; no run on it is recorded yet". `readme.test.cjs` allows "tested on <OS>" only with a passing record in `docs/testing/evidence/runs/` (RED first) |
| F2: hand-typed figures in HARDWARE.md and README passed every test | `5907f53`: `renderSummary` generates the requirements and ceiling margin; the bench block also carries the optimizer outcome, host load and bench versions; a test rejects measured figures outside the blocks; the README's quickstart durations must equal the artifact's. The verifier's four hand-edits and two more each fail a test |
| F4: "4 cores confirmed", a summed memory total, CPU without PostgreSQL | `5907f53`: the rows say no step ran under a 4-CPU limit, give the idle stack and the largest bench process separately, and say PostgreSQL is not included |
| F6: `check-version-pin` accepted `latest` | `5907f53`: only a release version or a `sha256` digest pins (RED first) |
| F7: a listed path counted as coverage; A01/A18/A24 printed `ok` | `5226a6c`: checks move to a `checks` field and run; a failing check makes the story `pending`, never `ok`; under `--enforce` a `tests` entry must be a test file tagged with the story. A03/A04 use the new `check-egress-evidence.cjs` |
| F8: `minutes(119.6)` printed "1 min 60 s" | `5907f53`: rounds first (RED first) |
| F9: `compose.test.yaml` had no project name | `5907f53`: `name: pantrypulse-tests` (RED first) |
| F5: egress scan too narrow, Google key vacuous, IPv4 only, host DNS stored | `47de1bb`, `30037e5`: presenter hash, dummy Google key and API response bodies scanned; IPv6 to global addresses flagged; only the stack bridge is recorded; re-run PASS at `9541f6f` |
| F1: lane tests ran in no gate | CR-w5-packaging-2, `5907f53`; CR-w5-packaging-3 (`7af6359`) gives the CI `verify` job the history those tests need |

### Review (verifier, ship-check step 2)

| Finding | Fix in `0daecf8` |
|---|---|
| F1 (Medium): fixture tests of the checkers made A01, A03, A04, A18 and A24 look covered | Those test modules now cover V1-A21 (the test kit). A03 and A04 map to `scripts/testing/egress-journey.cjs` itself; A01, A18 and A24 to `check-recorded-runs.cjs`, which still exits 1. The guide says so |
| F2 (Low): the sniffer treated any UDP/53 as DNS, so a container's direct lookup to an outside server was never flagged | `packet_event` checks the bridge path before DNS and records that as `udp` (a violation); new test with crafted frames (RED first: `packet_event` missing). The PK03 capture (`artifacts/egress/capture.jsonl`) re-checked under the new rule: 0 DNS packets from the stack's subnet, so its PASS stands |
| F3 (Low): HARDWARE.md said "about 1.9 GiB"; 458 + 1,423 MiB = 1,881 MiB | Now "about 1.8 GiB (1,881 MiB)" |
| F4 (Low): the bench artifact lacks `bench_versions`; the runner was uncommitted when it ran | Disclosed in HARDWARE.md's limits; the post-D02 re-measurement uses the committed runner |
| F5 (Low): README said every published result passes the verifier, but failed methods are returned unverified | "Every plan shown passes an independent verifier; a method that fails verification is shown as failed, never replaced or turned into suggested actions" (`results.tsx:286`, `decisions-view.tsx:18-20`) |

## Next, on the orchestrator's go (after the w5-data merge, PR #151)

Agreed with the orchestrator on 2026-11-12. Go received 2026-11-15: steps 1–3 done (merge `b92c1a6`; bench `09b6aba` read: 100 pantries, no hub, `MAX_ROWS` 4,500,000). The first run at `5b56347` was loaded; the orchestrator had it re-run on a quiet machine at `d92021b` (HARDWARE.md in `894a5a2`). Step 4: the quick gate at `d1d9800` failed on ESC-w5-packaging-1; it re-runs after the lead's heartbeat-fix PR merges and is merged here.
1. `git fetch && git merge origin/v1-local`, then commit the merge.
2. Read the merged `apps/api/scripts/bench_import.py`. The data lane's revision `09b6aba` (not pushed at the time of writing) has 100 pantries, no hub and 4,500,000 rows. #151 at `e4d8b05` still had one hub and 4,455,000 rows. Record what the merged bench actually generates, with its commit.
3. With a clean tree and no commits during the run, run the whole `node scripts/bench/run-all.cjs` (about 22 min) on that committed head with `.env.lane`. Regenerate HARDWARE.md from the new artifact, and replace the "predates D02" and "uncommitted runner" notes with the new run's commit and bench version. Commit.
4. Run the focused tests, then the quick gate with `PP19_TEST_SCHEMA_ISOLATION=1` exported by hand.
5. Push and open the PR, both after Gabriel approves in the terminal. Run `/code-review` locally only: its findings go to this file and to the orchestrator, never as GitHub comments. The orchestrator runs its own verifier before the merge.

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
- Every measured figure in HARDWARE.md is in one of two blocks generated from the JSON artifact (`renderSummary`: requirements and ceiling margin; `renderTable`: measurements, optimizer outcome, host load, bench versions), and `bench-report.test.cjs` re-renders both. The hand-written text may state only V1-SPEC figures (a test lists every number-with-unit outside the blocks), and every duration in the README quickstart must be the artifact's (`readme.test.cjs`). — W5-PK04, verifier round 2 (F2).

## Gotchas

- `.env.lane` does not set `PP19_TEST_SCHEMA_ISOLATION`; without it the PP19 API suites skip silently and the quality gate prints no counts. Export `PP19_TEST_SCHEMA_ISOLATION=1` by hand for every gate run you cite.

- Don't commit while a benchmark runs: `bench_forecast.py` and `bench_v1.py` record `git rev-parse HEAD` when they start, so a mid-run commit splits one run across two commits (PK04 recorded `083885b` and the docs-only `016b429`).
- The reference laptop is shared: at the A17 forecast the 1-minute load average was 28 on 16 CPUs. Re-measure on an idle machine before quoting tight margins.
- Docker Desktop forwards container DNS from the VM itself (`192.168.65.6 → 192.168.65.7` on `services1`), never across the project bridge, so DNS cannot be attributed to a stack there. Outbound TCP SYNs and TLS ClientHellos do cross the bridge with the container's address.

- `apps/api/tests` read repo-root files (`compose.compute.yaml`, `docs/plans/v1/README.md`, `data/**`, `scripts/or/**`, `packages/contracts/examples`). A new root-level read needs a new mount in `compose.test.yaml`, or `npm run test:docker` fails with a missing file.

## Change requests

### CR-w5-packaging-1: list HARDWARE.md as a docs file that tests read
- **File(s):** `scripts/quality/docs-only.cjs` (outside this lane's paths)
- **Exact change:** add one entry to `TEST_READ`:
  `'docs/pantrypulse/HARDWARE.md', // scripts/testing/tests/bench-report.test.cjs, scripts/bench/run-all.cjs`
- **Why:** `bench-report.test.cjs` reads HARDWARE.md and `run-all.cjs` rewrites its table, so a docs-only PR that edits HARDWARE.md must still run the checks. `npm run test:config` → `✖ every docs/ Markdown path quoted in code is in TEST_READ` (`scripts/quality/tests/docs-only.test.cjs:86`, actual `['docs/pantrypulse/HARDWARE.md']`) at `61bea71`; CI's `verify` job runs `test:config` (`.github/workflows/pantrypulse-ci.yml:26`), so the lane PR's CI fails until this lands. Building the path from parts would get past the guard, but its own comment names that as a blind spot, so I didn't.
- **Unblocks:** the lane PR's CI (W5-PK04 is otherwise done).
- **Status:** approved (Gabriel, 2026-11-12), done in `0286cc0`. Evidence: `npm run test:config` → exit 0, tests 36, pass 36, fail 0, skipped 0; "every docs/ Markdown path quoted in code is in TEST_READ" passes.

### CR-w5-packaging-2: run the lane's tests in `test:config`
- **File(s):** `package.json` (lead-owned), the `test:config` script line only.
- **Change:** `node --test scripts/quality/tests/*.test.cjs scripts/testing/tests/*.test.cjs`.
- **Why:** verifier round 2 (F1): the lane's tests ran in no gate and no CI.
- **Status:** approved (Gabriel, 2026-11-15) as a one-time exception; done in `5907f53`. `npm run test:config` → 78 tests, 78 pass, 0 fail, 0 skipped, 3.2 s.

### CR-w5-packaging-3: full history for the CI `verify` job
- **File(s):** `.github/workflows/pantrypulse-ci.yml` (lead-owned), the `verify` job's `actions/checkout@v4` step (line 19).
- **Exact change:** add `with: { fetch-depth: 0 }` to that step.
- **Why:** with CR-2, `verify` runs `scripts/testing/tests/bench-report.test.cjs`, which checks that the bench artifact's commit (`d92021b`) exists with `git cat-file -e`. The default depth-1 checkout has no history, so the test fails there. Reproduced: a `git clone --depth 1` of this branch at `5907f53` → `node --test scripts/quality/tests/*.test.cjs scripts/testing/tests/*.test.cjs` → 70 of 71 pass, `✖ every measurement is tied to a real commit and a timestamp`. Making the test skip in a shallow clone would hide the check, so I didn't. (`check-egress-evidence.cjs` and `check-recorded-runs.cjs` also read history; in a shallow clone their stories show `pending`, which fails nothing.)
- **Unblocks:** the lane PR's `verify` job.
- **Status:** approved (Gabriel, 2026-11-14) as a one-time exception; done in `7af6359` (the `verify` checkout gains `with: fetch-depth: 0`; the other two checkouts are unchanged).

## Escalations

### ESC-w5-packaging-1: `tests/imports/test_import_job.py` fails when its module runs longer than 15 s
- **Seen:** quick gate at `d1d9800` (with `PP19_TEST_SCHEMA_ISOLATION=1`, host load up to 25): 9 tests in this file fail with `app.repositories.jobs.AdmissionRejected: new computation rejected` (`jobs.py:590`). The file alone at low load: 29 passed in 5.6 s.
- **Root cause:** the module-scoped `queue` fixture (`apps/api/tests/imports/test_import_job.py:51-62`) stamps the supervisor's heartbeat once, when the module starts, and never refreshes it. Admission requires a heartbeat younger than `PRODUCTION_PROFILE.heartbeat_stale_s` = 15 s (`app/services/jobs/policies.py:66-74`), so once the module has run more than 15 s every later `submit` is rejected. A slow, loaded machine reaches that.
- **Minimal failing case:** a pytest plugin that sleeps 16 s before the 10th test (`def pytest_runtest_setup(item): …; if n == 10: time.sleep(16)`), then `PYTHONPATH=<plugin dir> uv run --frozen pytest -q -p no:cacheprovider -p slow_after_ten tests/imports/test_import_job.py` → `16 failed, 13 passed`, all `AdmissionRejected`. Without the plugin: 29 passed.
- **Suggested fix (owner: lead or w5-data, outside this lane):** keep the fixture's `Ownership` and refresh the heartbeat in the function-scoped `rt` fixture (`queue.heartbeat(own)`, `jobs.py:1043`) before each test, so the heartbeat never depends on how long the module runs.
- **Status:** resolved by the lead in #154 (`8b4fff9`: the module supervisor beats in the background); merged here as `a1eb4d3`, where the quick gate passes.
