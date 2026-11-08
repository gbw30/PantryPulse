# Status — `w3-samples`

**Lane:** `w3-samples` · **Branch:** `lane/w3-samples` · **Base SHA:** `0a4959359a447233e8ca5eea87b1917d70bd7de8` · **Last update:** `2026-11-08` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W3-P01 | done | see `git log` (W3-P01) | `uv run --frozen pytest -q tests/samples/test_pantry_sample.py` → 7 passed, 0 skipped |
| W3-P02 | done | see `git log` (W3-P02) | `uv run --frozen pytest -q tests/samples/test_retail_sample.py` → 5 passed, 0 skipped (`tests/samples/` → 12 passed) |
| W3-P03 | done | see `git log` (W3-P03) | `uv run --frozen pytest -q tests/samples tests/imports/test_templates.py tests/test_v1_contract.py` → 88 passed, 0 skipped |
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
- Retail chain is the invented "Heronfield Market"; products are generic descriptions ("Toasted oat cereal, 12 oz"), checked against a ~120-name denylist of real US grocery chains and CPG brands kept in `test_retail_sample.py` — W3-P02.
- Retail history uses `basis=sales` (stores record sales), so the app shows the sales undercount label; Retail donation history is a weekly vendor promotion at the DC, only so both optional files are exercised — W3-P02.
- Examples are the Pantry sample on a fixed as-of date (`EXAMPLE_AS_OF = 2026-11-04` in `templates.py`), computed by the `example` branch like the blank branch computes its header; `scripts/generate_samples.py` writes `data/templates/examples/*.csv` from that branch, and `--check` is the drift test. `example_available` is now `True` in the catalog (part of the example feature) — W3-P03.
- Approved by Gabriel 2026-11-08: the lane removed two stub pins in lead-owned tests, `tests/imports/test_templates.py::test_examples_kind_returns_501_until_w3` (W3-P03) and `tests/test_local_bootstrap.py:180` (W3-P04), plus the permitted STUBS row for `/templates/locations.csv?kind=example` in `tests/test_v1_contract.py` — W3-P03/P04.
- Demand follows real weekdays (busy Saturdays, quiet Sundays), so a sample generated on a later day has different quantities; determinism is per (seed, date) — W3-P01.

## Gotchas

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
