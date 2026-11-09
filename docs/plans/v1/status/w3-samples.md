# Status — `w3-samples`

**Lane:** `w3-samples` · **Branch:** `lane/w3-samples` · **Base SHA:** `0a4959359a447233e8ca5eea87b1917d70bd7de8` · **Last update:** `2026-11-09` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W3-P01 | done | `def31ca` | `uv run --frozen pytest -q tests/samples/test_pantry_sample.py` → 7 passed, 0 skipped |
| W3-P02 | done | `6bea81c` | `uv run --frozen pytest -q tests/samples/test_retail_sample.py` → 5 passed, 0 skipped (`tests/samples/` → 12 passed) |
| W3-P03 | done | `be0f8e0` | `uv run --frozen pytest -q tests/samples tests/imports/test_templates.py tests/test_v1_contract.py` → 88 passed, 0 skipped |
| W3-P04 | done | `55026c0` | `uv run --frozen pytest -q tests/samples` → 23 passed, 0 skipped; `tests/test_local_bootstrap.py` → 10 passed, 0 skipped (with `.env.lane`); compose: seed log "samples loaded: 2", both networks `is_sample`, as-of 2026-11-09, 0 jobs queued; offline seed on an `--internal` network (outbound probe blocked) loaded both on a fresh DB |

Status values: `todo`, `in progress`, `done`, `blocked (<reason or CR id>)`.

### Next step

`/devkit:ship-check` (local review by the project `verifier` agent), then the PR `lane/w3-samples → v1-local`. When the lead's CR-w3-samples-1/2 PR merges: `git merge origin/v1-local`, re-run `tests/samples` and the quick gate, push.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` (standard env) | `55026c0` | PASS (4/4). Without a DB, pytest is 1669 passed, 383 skipped: every skip is a PostgreSQL suite reporting `NOT RUN: PP_TEST_DATABASE_URL is not set` (e.g. `test_supervisor` 63, `test_job_queue` 38, `test_build_scenario` 22, `test_import_postgres` 21, `test_seed` 7); not counted as validated, all run in `full` below |
| `node scripts/quality/run.cjs full` (with `.env.lane`, `PP19_TEST_SCHEMA_ISOLATION=1`) | `55026c0` | PASS (8/8); same env `uv run --frozen pytest -q -rs` → 2052 passed, 0 skipped in 314 s |
| `/devkit:ship-check` | `0053567` → fixes in the next commit | step 1 quick+full PASS; step 2 project `verifier`: pass with findings (106 focused tests incl. PostgreSQL 0 skipped, generator `--check` clean, own W1-rule sweep over 1,100 Pantry and 134 Retail dates 0 failures, partial-failure and concurrent-seed runs held). F1 and F2 fixed; F3–F5 recorded below. Step 3: security-guidance not installed. Steps 5–6 after the PR |

## Decisions made inside the lane

- Samples are generated as CSV text per template (`SampleNetwork.files`) and validated by `validate_files`, so the seed, the template examples and the tests share one source — W3-P01.
- City-level coordinates are rounded to 2 decimals and the required `street` column reads "No street address (sample)" (no digits), so no sample points at a real building — W3-P01.
- Retail chain is the invented "Heronfield Market"; products are generic descriptions ("Toasted oat cereal, 12 oz"), checked against a ~120-name denylist of real US grocery chains and CPG brands kept in `test_retail_sample.py` — W3-P02.
- Retail history uses `basis=sales` (stores record sales), so the app shows the sales undercount label; Retail donation history is a weekly vendor promotion at the DC, only so both optional files are exercised — W3-P02.
- Examples are the Pantry sample on a fixed as-of date (`EXAMPLE_AS_OF = 2026-11-04` in `templates.py`), computed by the `example` branch like the blank branch computes its header; `scripts/generate_samples.py` writes `data/templates/examples/*.csv` from that branch, and `--check` is the drift test. `example_available` is now `True` in the catalog (part of the example feature) — W3-P03.
- Approved by Gabriel 2026-11-08: the lane removed two stub pins in lead-owned tests, `tests/imports/test_templates.py::test_examples_kind_returns_501_until_w3` (W3-P03) and `tests/test_local_bootstrap.py:180` (W3-P04), plus the permitted STUBS row for `/templates/locations.csv?kind=example` in `tests/test_v1_contract.py` — W3-P03/P04.
- Verifier F1 (fixed): the catalog advertised the Pantry example in Retail mode, where it fails validation (`type: hub`). `template_catalog("RETAIL")` now reports `example_available=False` (`test_catalog_offers_examples_only_where_they_validate`); the web shows "Example not available yet." Real Retail examples are CR-w3-samples-3. Verifier F2 (fixed): `SampleNetwork.label`/`rate_source` were constants no app code read; removed with their assertions — W3-P03/P01.
- Demand follows real weekdays (busy Saturdays, quiet Sundays), so a sample generated on a later day has different quantities; determinism is per (seed, date) — W3-P01.

## Gotchas

- **Seed deadlock (confirmed, fixed in W3-P04):** `local_bootstrap.run` calls the seed inside one ORM transaction that has already run `INSERT INTO organizations` (ROW EXCLUSIVE). Publishing an import runs `ALTER TABLE net_batches ATTACH PARTITION …`, which requests SHARE ROW EXCLUSIVE on `organizations` (the partition's FK to it is cloned at attach, `staging.py:64-67`). Observed in `pg_stat_activity`/`pg_locks`: the ATTACH (pid 5305) waited on the seed's own idle-in-transaction connection (pid 5304), a client-side deadlock PostgreSQL can't detect; the test hung until killed. Fix: `ensure_samples` commits the caller's session before importing (each sample import already commits on its own connections, so the seed was never atomic). `test_seed.py` sets `lock_timeout = 30s` per transaction, so a regression fails in ~60 s instead of hanging the 480 s api-tests step. **Any future caller that imports or publishes while holding an open write on `organizations`, `dataset_versions`, `net_locations` or `net_products` will deadlock the same way.**
- `tests/test_local_bootstrap.py`'s `db` fixture truncates `organizations` before each test, so once `ensure_samples` is real, each of its ~10 `run()` calls imports both samples (Retail is ~90k sales rows). Measured: about 1.1 s per `run()`, 14.5 s for the module (10 tests).
- The fixture forecast job in `tests/networks/test_build_scenario.py` caps output at 10,000 bytes (`OUTPUT_TOO_LARGE` even for the 48-series Pantry sample). `test_seed.py`'s `sample_sized_forecasts` fixture swaps in the same registration with 50 MB caps; it must be requested before `forecasts`.
- psycopg 3 connects through libpq (C sockets), so patching Python's `socket` in the no-outbound test can't break the test's own database connection.

## Known limitations (verifier F3–F5, accepted for the PR)

- F3: a failed sample import leaves its import run (`failed`) and, for a new network, its organization row; abandoned-import cleanup is deferred to W5 (W2-06 §5 D). A restart imports the missing sample once; nothing is duplicated (verified).
- F4: a sample import error raises, so the `seed` service fails and compose doesn't start `api`/`worker`. Chosen deliberately: the samples are our own generated files, and the verifier's date sweep found no failing date. Lead call whether a sample failure should instead be logged and skipped.
- F5: `ensure_samples` commits the caller's session (the deadlock fix), so the caller can't use that session's transaction afterwards; `local_bootstrap.run` doesn't. Two concurrent seeds on an empty DB: PostgreSQL aborts one with `DeadlockDetected`, the other loads both, no duplicates (compose runs one seed).

## Change requests

### CR-w3-samples-1 — sample rates read "sample values", not "manual"
- **File(s):** `apps/api/app/services/enrichment/service.py` (merged W1 code; no W3 lane owns it), a test in `apps/api/tests/enrichment/`.
- **Exact change:** `_ATTRIBUTES` also selects `EXISTS (SELECT 1 FROM dataset_versions v JOIN networks n ON n.id = v.network_id WHERE v.id = net_locations.dataset_version_id AND n.is_sample) AS is_sample`; in `_attributes`, the all-manual branch sets `source = "sample values" if r.is_sample else "manual"` (state stays `manual`). `scenario.py:327`'s `a.source or "manual"` then freezes "sample values" too. Test: a network imported with `create_import(..., is_sample=True)` whose locations.csv gives both rates reports `source == "sample values"` from `location_attributes`, and a non-sample network still reports `"manual"`.
- **Why:** W2-06 §3 carry-in and V1-SPEC §8 ("poverty/SNAP values pre-filled and labeled 'sample values'"). The label is hard-coded at `enrichment/service.py:170`. The samples, `SampleNetwork.rate_source` and `data/samples/README.md` already say "sample values"; only the in-app label is missing.
- **Unblocks:** the in-app half of the "sample values" carry-in (W3-P01 is otherwise done).
- **Status:** approved (Gabriel, 2026-11-09); the lead builds it on a lead branch into `v1-local`. The lane merges `origin/v1-local` when told and re-runs its focused tests.

### CR-w3-samples-2 — keep template CSVs LF on a Windows checkout
- **File(s):** `.gitattributes` (lead-only).
- **Exact change:** add `data/templates/**/*.csv text eol=lf`.
- **Why:** `.gitattributes` covers `*.sh`, `*.py`, `*.yaml` but not CSV. With `core.autocrlf=true` (the Git for Windows default) the blank and example templates check out as CRLF, so `test_blank_templates_are_header_only` (W1) and `test_example_files_equal_generator_output` (W3-P03) fail when the tests run on that checkout (e.g. `npm run test:api:docker` on the Windows host). The importer itself accepts CRLF; only the byte-equality drift checks break.
- **Unblocks:** nothing on Linux/CI; Windows-host test runs.
- **Status:** approved (Gabriel, 2026-11-09); the lead builds it.

### CR-w3-samples-3 — Retail template examples (a `mode` on the example download)
- **File(s):** `apps/api/app/routers/v1_networks.py:55` (lead), the frozen `template_csv(name, kind)` signature, `packages/contracts/**` (regenerated), the web's `templateUrl` (w3-web paths).
- **Exact change:** `GET /templates/{name}.csv?kind=example&mode=PANTRY|RETAIL` (mode optional, default PANTRY); `template_csv(name, kind, mode=None)`. The lane then adds the Retail branch (the Retail sample on `EXAMPLE_AS_OF`), `data/templates/examples/retail/*.csv` with the same drift check, and `example_available=True` for Retail.
- **Why:** V1-SPEC §6.1 gives every template a filled example; today Retail has none (verifier F1, mitigated by reporting `example_available=False` in Retail mode).
- **Unblocks:** Retail example downloads. Non-blocking for this PR.
- **Status:** open.

## Escalations
