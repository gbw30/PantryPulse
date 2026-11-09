# Status — `w3-samples`

**Lane:** `w3-samples` · **Branch:** `lane/w3-samples` · **Base SHA:** `0a4959359a447233e8ca5eea87b1917d70bd7de8` · **Last update:** `2026-11-09` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W3-P01 | done | `def31ca` | `uv run --frozen pytest -q tests/samples/test_pantry_sample.py` → 7 passed, 0 skipped |
| W3-P02 | done | `6bea81c` | `uv run --frozen pytest -q tests/samples/test_retail_sample.py` → 5 passed, 0 skipped (`tests/samples/` → 12 passed) |
| W3-P03 | done | `be0f8e0` | `uv run --frozen pytest -q tests/samples tests/imports/test_templates.py tests/test_v1_contract.py` → 88 passed, 0 skipped |
| W3-P04 | in progress (code done; compose check, gates, PR next) | see `git log` (W3-P04) | `uv run --frozen pytest -q tests/samples` → 23 passed, 0 skipped; `tests/test_local_bootstrap.py` → 10 passed, 0 skipped (with `.env.lane`) |

Status values: `todo`, `in progress`, `done`, `blocked (<reason or CR id>)`.

### Next step (W3-P04)

wave-3 Step 3 compose check (`COMPOSE_PROJECT_NAME=pp-samples PP_WEB_PORT=3102 docker compose up --build -d --wait`, both samples listed, then `down -v`), then `quick`, `full`, `/devkit:ship-check`, PR into `v1-local`.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- Samples are generated as CSV text per template (`SampleNetwork.files`) and validated by `validate_files`, so the seed, the template examples and the tests share one source — W3-P01.
- City-level coordinates are rounded to 2 decimals and the required `street` column reads "No street address (sample)" (no digits), so no sample points at a real building — W3-P01.
- Retail chain is the invented "Heronfield Market"; products are generic descriptions ("Toasted oat cereal, 12 oz"), checked against a ~120-name denylist of real US grocery chains and CPG brands kept in `test_retail_sample.py` — W3-P02.
- Retail history uses `basis=sales` (stores record sales), so the app shows the sales undercount label; Retail donation history is a weekly vendor promotion at the DC, only so both optional files are exercised — W3-P02.
- Examples are the Pantry sample on a fixed as-of date (`EXAMPLE_AS_OF = 2026-11-04` in `templates.py`), computed by the `example` branch like the blank branch computes its header; `scripts/generate_samples.py` writes `data/templates/examples/*.csv` from that branch, and `--check` is the drift test. `example_available` is now `True` in the catalog (part of the example feature) — W3-P03.
- Approved by Gabriel 2026-11-08: the lane removed two stub pins in lead-owned tests, `tests/imports/test_templates.py::test_examples_kind_returns_501_until_w3` (W3-P03) and `tests/test_local_bootstrap.py:180` (W3-P04), plus the permitted STUBS row for `/templates/locations.csv?kind=example` in `tests/test_v1_contract.py` — W3-P03/P04.
- Demand follows real weekdays (busy Saturdays, quiet Sundays), so a sample generated on a later day has different quantities; determinism is per (seed, date) — W3-P01.

## Gotchas

- **Seed deadlock (confirmed, fixed in W3-P04):** `local_bootstrap.run` calls the seed inside one ORM transaction that has already run `INSERT INTO organizations` (ROW EXCLUSIVE). Publishing an import runs `ALTER TABLE net_batches ATTACH PARTITION …`, which requests SHARE ROW EXCLUSIVE on `organizations` (the partition's FK to it is cloned at attach, `staging.py:64-67`). Observed in `pg_stat_activity`/`pg_locks`: the ATTACH (pid 5305) waited on the seed's own idle-in-transaction connection (pid 5304), a client-side deadlock PostgreSQL can't detect; the test hung until killed. Fix: `ensure_samples` commits the caller's session before importing (each sample import already commits on its own connections, so the seed was never atomic). `test_seed.py` sets `lock_timeout = 30s` per transaction, so a regression fails in ~60 s instead of hanging the 480 s api-tests step. **Any future caller that imports or publishes while holding an open write on `organizations`, `dataset_versions`, `net_locations` or `net_products` will deadlock the same way.**
- `tests/test_local_bootstrap.py`'s `db` fixture truncates `organizations` before each test, so once `ensure_samples` is real, each of its ~10 `run()` calls imports both samples (Retail is ~90k sales rows). Measured: about 1.1 s per `run()`, 14.5 s for the module (10 tests).
- The fixture forecast job in `tests/networks/test_build_scenario.py` caps output at 10,000 bytes (`OUTPUT_TOO_LARGE` even for the 48-series Pantry sample). `test_seed.py`'s `sample_sized_forecasts` fixture swaps in the same registration with 50 MB caps; it must be requested before `forecasts`.
- psycopg 3 connects through libpq (C sockets), so patching Python's `socket` in the no-outbound test can't break the test's own database connection.

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

## Escalations
