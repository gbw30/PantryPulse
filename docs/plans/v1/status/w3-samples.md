# Status — `w3-samples`

**Lane:** `w3-samples` · **Branch:** `lane/w3-samples` · **Base SHA:** `0a4959359a447233e8ca5eea87b1917d70bd7de8` · **Last update:** `2026-11-08` · **Head:** see `git log` (paused at a save point, 2026-11-08)

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W3-P01 | done | `def31ca` | `uv run --frozen pytest -q tests/samples/test_pantry_sample.py` → 7 passed, 0 skipped |
| W3-P02 | done | `6bea81c` | `uv run --frozen pytest -q tests/samples/test_retail_sample.py` → 5 passed, 0 skipped (`tests/samples/` → 12 passed) |
| W3-P03 | done | `be0f8e0` | `uv run --frozen pytest -q tests/samples tests/imports/test_templates.py tests/test_v1_contract.py` → 88 passed, 0 skipped |
| W3-P04 | in progress (recon only; no code yet) | — | next step below |

Status values: `todo`, `in progress`, `done`, `blocked (<reason or CR id>)`.

### Next step (W3-P04, resume here)

1. RED: write `apps/api/tests/samples/test_seed.py` (`pytest.mark.integration`, own schema `w3_samples_seed_test`, module-scoped migrated engine, per-test `TRUNCATE organizations CASCADE` like `tests/test_local_bootstrap.py`). Drive the seed exactly as `scripts/local_bootstrap.py:105` does: `with Session(engine) as s, s.begin(): seed_local.ensure_local_organization(s); samples.ensure_samples(s, today)`. Tests: `test_first_start_loads_both_samples`, `test_second_start_loads_nothing`, `test_new_freshly_dated_version_when_newest_older_than_7_days` (today+7 loads nothing, today+8 loads both, same network ids, `is_sample` kept), `test_older_versions_and_results_untouched` (md5 fingerprint of the old version's `net_*` rows plus a frozen `planning_scenarios_v3` row, before and after), `test_no_outbound_network_calls` (patch `socket.socket.connect`/`connect_ex`/`socket.create_connection` to raise), `test_never_resets` (a user network imported first keeps identical rows; no DELETE/TRUNCATE/DROP/UPDATE in `app/services/samples/**`), `test_each_sample_freezes_cleanly` (W1 rule list), plus "no `enrichment.v1` job queued".
2. GREEN: `ensure_samples(session, today)`: engine = `session.get_bind()`; per sample, find `networks WHERE is_sample AND name = :name` and its newest `dataset_versions.as_of_date`; absent → `create_import(SimpleNamespace(engine=engine), None, ImportCreate(network=NewNetwork(...)), is_sample=True)`; newest older than 7 days → `ImportCreate(network_id=...)`; write the files with `staging.write_upload` into a private `tempfile.TemporaryDirectory()` (COPY is `FROM STDIN`, so no shared volume is needed), `repo.record_file`, then `staging.run_import(engine, import_id, today, base, actor="seed")`; raise if the outcome isn't ok. Return `SeedReport(loaded=names)`.
3. Delete the approved stub pin `tests/test_local_bootstrap.py:180`, run `tests/samples` + `tests/test_local_bootstrap.py`, then the compose check (wave-3 Step 3), `quick`, `full`, `/devkit:ship-check`, PR.

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

- **Possible lock wait in the seed (unverified, test it first in P04):** `local_bootstrap.run` calls the seed inside one ORM transaction that has already run `INSERT INTO organizations` (ROW EXCLUSIVE on `organizations`), while `run_import` publishes on its own connections. If publish's `ATTACH PARTITION` (the `net_batches` FK to `organizations` is cloned at attach, `staging.py:64-67`) needs SHARE ROW EXCLUSIVE on `organizations`, it waits on the seed's own open transaction: a client-side deadlock PostgreSQL can't detect. The P04 tests must reproduce the bootstrap transaction exactly (above) and run under a shell `timeout` the first time.
- `tests/test_local_bootstrap.py`'s `db` fixture truncates `organizations` before each test, so once `ensure_samples` is real, each of its ~10 `run()` calls imports both samples (Retail is ~90k sales rows). Measure the added time against the 480 s api-tests step.
- The fixture forecast job in `tests/networks/test_build_scenario.py` caps input at 1,000,000 bytes; the Retail sample has 1,000 demand series and may exceed it. A freeze with fewer series is valid (`scenario.py:_demand` lists missing series as an assumption, not an error), or use a registration with a larger cap.
- psycopg 3 connects through libpq (C sockets), so patching Python's `socket` in the no-outbound test can't break the test's own database connection.

## Change requests

### CR-w3-samples-1 — sample rates read "sample values", not "manual"
- **File(s):** `apps/api/app/services/enrichment/service.py` (merged W1 code; no W3 lane owns it), a test in `apps/api/tests/enrichment/`.
- **Exact change:** `_ATTRIBUTES` also selects `EXISTS (SELECT 1 FROM dataset_versions v JOIN networks n ON n.id = v.network_id WHERE v.id = net_locations.dataset_version_id AND n.is_sample) AS is_sample`; in `_attributes`, the all-manual branch sets `source = "sample values" if r.is_sample else "manual"` (state stays `manual`). `scenario.py:327`'s `a.source or "manual"` then freezes "sample values" too. Test: a network imported with `create_import(..., is_sample=True)` whose locations.csv gives both rates reports `source == "sample values"` from `location_attributes`, and a non-sample network still reports `"manual"`.
- **Why:** W2-06 §3 carry-in and V1-SPEC §8 ("poverty/SNAP values pre-filled and labeled 'sample values'"). The label is hard-coded at `enrichment/service.py:170`. The samples, `SampleNetwork.rate_source` and `data/samples/README.md` already say "sample values"; only the in-app label is missing.
- **Unblocks:** the in-app half of the "sample values" carry-in (W3-P01 is otherwise done).
- **Status:** open — Gabriel chose "file a CR for the lead" (2026-11-08).

### CR-w3-samples-2 — keep template CSVs LF on a Windows checkout
- **File(s):** `.gitattributes` (lead-only).
- **Exact change:** add `data/templates/**/*.csv text eol=lf`.
- **Why:** `.gitattributes` covers `*.sh`, `*.py`, `*.yaml` but not CSV. With `core.autocrlf=true` (the Git for Windows default) the blank and example templates check out as CRLF, so `test_blank_templates_are_header_only` (W1) and `test_example_files_equal_generator_output` (W3-P03) fail when the tests run on that checkout (e.g. `npm run test:api:docker` on the Windows host). The importer itself accepts CRLF; only the byte-equality drift checks break.
- **Unblocks:** nothing on Linux/CI; Windows-host test runs.
- **Status:** open (non-blocking).

## Escalations
