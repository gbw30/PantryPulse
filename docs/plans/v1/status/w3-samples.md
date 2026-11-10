# Status — `w3-samples`

**Lane:** `w3-samples` · **Branch:** `lane/w3-samples` · **Base SHA:** `0a4959359a447233e8ca5eea87b1917d70bd7de8` · **Last update:** `2026-11-09` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W3-P01 | done | `def31ca` | `uv run --frozen pytest -q tests/samples/test_pantry_sample.py` → 7 passed, 0 skipped |
| W3-P02 | done | `6bea81c` | `uv run --frozen pytest -q tests/samples/test_retail_sample.py` → 5 passed, 0 skipped (`tests/samples/` → 12 passed) |
| W3-P03 | done | `be0f8e0` | `uv run --frozen pytest -q tests/samples tests/imports/test_templates.py tests/test_v1_contract.py` → 88 passed, 0 skipped |
| W3-P04 | done | `55026c0` | `uv run --frozen pytest -q tests/samples` → 23 passed, 0 skipped; `tests/test_local_bootstrap.py` → 10 passed, 0 skipped (with `.env.lane`); compose: seed log "samples loaded: 2", both networks `is_sample`, as-of 2026-11-09, 0 jobs queued; offline seed on an `--internal` network (outbound probe blocked) loaded both on a fresh DB |

| Follow-up: CR-3 Retail examples, CR-4 commit removal, N1 | done | `46e4706` (merge `915b98c` adds `origin/v1-local` `a2c7258`) | `uv run --frozen pytest -q -rs tests/samples tests/imports tests/enrichment tests/test_v1_contract.py tests/test_local_bootstrap.py` (with `.env.lane`) → 340 passed, 0 skipped |

Status values: `todo`, `in progress`, `done`, `blocked (<reason or CR id>)`.

### Next step

PR #121 merged (`77da30e`). The follow-up (`46e4706`, merge `915b98c` of `origin/v1-local` `a2c7258`) passed its gates and the `verifier` (pass with findings). Next: the follow-up PR to `v1-local`, ship-check step 5 (`/code-review`) on it, then the lead's review. **Merge order:** the w3-web `&mode=` fix for `network-api.ts:18` must land with this PR or before it (verifier finding, Medium), or a Retail import page offers the Pantry examples. Gabriel approves the merge.

## Save point 2026-11-09

- **Head:** the status commit on top of `a172430` (merge of `origin/v1-local` = lead PR #122 `5c5fbe7`, CR-1 and CR-2) and `8d1fe06` (review fixes).
- **Verifier review of `51b65aa`: all 3 Low findings fixed** in `8d1fe06` (L1 serialized seed, L2 recorded outbound attempts, L3 mutant-killing tests; details under Decisions).
- **Evidence on `a172430`:** `uv run --frozen pytest -q -rs tests/samples tests/enrichment tests/imports tests/test_v1_contract.py tests/test_local_bootstrap.py` (with `.env.lane`) → 332 passed, 0 skipped; `node scripts/quality/run.cjs quick` → PASS 4/4. The concurrency test ran green 3 times in a row on `8d1fe06`. Full gate not re-run since `c5dce80`.
- **Exact next step:** wait for the verifier's re-check of `51b65aa..` this head on PR #121 and fix any findings test-first. Optionally run `node scripts/quality/run.cjs full` (with `.env.lane`, `PP19_TEST_SCHEMA_ISOLATION=1`) on this head. CR-3 and CR-4 are with Gabriel. No merge before Gabriel's next session.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` (standard env) | `55026c0`, rerun `f7d996e`, `c5dce80`, `a172430` | PASS (4/4) each time. Without a DB, pytest is 1669 passed, 383 skipped: every skip is a PostgreSQL suite reporting `NOT RUN: PP_TEST_DATABASE_URL is not set` (e.g. `test_supervisor` 63, `test_job_queue` 38, `test_build_scenario` 22, `test_import_postgres` 21, `test_seed` 7); not counted as validated, all run in `full` below |
| `node scripts/quality/run.cjs full` (with `.env.lane`, `PP19_TEST_SCHEMA_ISOLATION=1`) | `55026c0`, rerun `f7d996e`, `c5dce80` | PASS (8/8) each time; same env `uv run --frozen pytest -q -rs` → 2052 passed, 0 skipped (`55026c0`); 2053 passed, 0 skipped in 291 s (`f7d996e`); 2054 passed, 0 skipped in 333 s (`c5dce80`). Focused (`tests/samples`, `test_templates`, `test_v1_contract`, `test_local_bootstrap`) on `c5dce80`: 107 passed, 0 skipped |
| Follow-up gates (with `.env.lane`; quick in the standard env) | `915b98c` | focused (`tests/samples tests/imports tests/enrichment tests/test_v1_contract.py tests/test_local_bootstrap.py`) 340 passed, 0 skipped; quick PASS 4/4; full (`PP19_TEST_SCHEMA_ISOLATION=1`) PASS 8/8; `uv run --frozen pytest -q -rs` 2077 passed, 0 skipped in 401 s |
| Follow-up ship-check step 2 (project `verifier`) | `915b98c` | pass with findings: CR-3, CR-4, N1, the authorized edit and the sample rules PASS (54 focused tests, 0 skipped; `--check` 14 examples clean; drift mutants caught; commit mutant caught; Pantry examples unchanged; the other 6 Retail files byte-identical on 4 dates). Medium: the web's example URL sends no `mode` (w3-web fix, merge order). Info: an install seeded before this keeps its old Retail sample, without `routes.csv`, for up to 7 days |
| `/devkit:ship-check` | `0053567` → fixes in the next commit | step 1 quick+full PASS; step 2 project `verifier`: pass with findings (106 focused tests incl. PostgreSQL 0 skipped, generator `--check` clean, own W1-rule sweep over 1,100 Pantry and 134 Retail dates 0 failures, partial-failure and concurrent-seed runs held). F1 and F2 fixed; F3–F5 recorded below. Step 3: security-guidance not installed. Step 5 `/code-review medium` on PR #121: 10 findings, outcome under Decisions (R1–R10). Step 6 not needed (no auth, payments, migrations or permissions) |

## Decisions made inside the lane

- Samples are generated as CSV text per template (`SampleNetwork.files`) and validated by `validate_files`, so the seed, the template examples and the tests share one source — W3-P01.
- City-level coordinates are rounded to 2 decimals and the required `street` column reads "No street address (sample)" (no digits), so no sample points at a real building — W3-P01.
- Retail chain is the invented "Heronfield Market"; products are generic descriptions ("Toasted oat cereal, 12 oz"), checked against a ~120-name denylist of real US grocery chains and CPG brands kept in `test_retail_sample.py` — W3-P02.
- Retail history uses `basis=sales` (stores record sales), so the app shows the sales undercount label; Retail donation history is a weekly vendor promotion at the DC, only so both optional files are exercised — W3-P02.
- Examples are the Pantry sample on a fixed as-of date (`EXAMPLE_AS_OF = 2026-11-04` in `templates.py`), computed by the `example` branch like the blank branch computes its header; `scripts/generate_samples.py` writes `data/templates/examples/*.csv` from that branch, and `--check` is the drift test. `example_available` is now `True` in the catalog (part of the example feature) — W3-P03.
- Approved by Gabriel 2026-11-08: the lane removed two stub pins in lead-owned tests, `tests/imports/test_templates.py::test_examples_kind_returns_501_until_w3` (W3-P03) and `tests/test_local_bootstrap.py:180` (W3-P04), plus the permitted STUBS row for `/templates/locations.csv?kind=example` in `tests/test_v1_contract.py` — W3-P03/P04.
- Verifier F1 (fixed): the catalog advertised the Pantry example in Retail mode, where it fails validation (`type: hub`). `template_catalog("RETAIL")` now reports `example_available=False` (`test_catalog_offers_examples_only_where_they_validate`); the web shows "Example not available yet." Real Retail examples are CR-w3-samples-3. Verifier F2 (fixed): `SampleNetwork.label`/`rate_source` were constants no app code read; removed with their assertions — W3-P03/P01.
- PR #121 `/code-review` (R1–R10), each checked against the code before acting:
  - R1 (fixed): duplicate sample names (two seeds racing) made the freshness lookup raise `MultipleResultsFound` on every later start. The lookup now takes the freshest network (`test_duplicate_sample_names_do_not_stop_the_seed`).
  - R4 (fixed): the mode-less catalog also offered the Pantry-only example. Only `template_catalog("PANTRY")` offers it now.
  - R7 (fixed): a batch could be received longer before its expiry than its product keeps (a 6-day produce batch received 21 days ago). One shared `network.batch` helper bounds the receipt date by shelf life (`assert_plausible_ages`); it also replaces the two copies of `_batch` (R9). The examples were regenerated: 2 files changed.
  - R8 (fixed): the drift check compared `read_text` output, which turns CRLF into LF, and `--check` created the folder. Both the script and the test now compare bytes; `--check` writes nothing.
  - R2 and R6 (lead, CR-w3-samples-4): the bootstrap passes UTC `date.today()` while the samples are New York-dated; seeding outside the login transaction would make the `commit()` in `ensure_samples` unnecessary.
  - R3 (w3-web note): `exampleUnavailableReason` expected a 501; for a template with no example it now gets a 200 and shows the generic text. CR-w3-samples-3 removes the case.
  - R5 (accepted): a user can re-import into a sample network through the API; the web blocks it. R10 (not taken): `templates.py` importing the sample module loads the importer stack, which the router already loads.
- PR #121 verifier review at `51b65aa` (no High/Medium; three Low), each fixed test-first:
  - L1: two seeds at once on stale (or absent) samples both passed the freshness check and both imported: a duplicate version, or a `DeadlockDetected` on the partition attach. `ensure_samples` now holds a transaction-scoped advisory lock (`hashtextextended(current_schema() || 'samples.seed', 0)`, the codebase's key form) around check and import. The lock's transaction takes no table locks. `test_concurrent_seeds_load_each_sample_once[empty|stale]` holds each import at a barrier until both seeds have passed the check: red (DeadlockDetected) before, green 3 runs in a row after.
  - L2: the no-outbound test raised inside the patched call, so a caught `urlopen` passed. It now records attempts and asserts none. Verified with the mutant (a swallowed `urlopen` to 192.0.2.1): the test fails.
  - L3: two surviving mutants are now killed, each checked by applying it: dropping `n.is_sample` from the lookup (`test_user_network_named_like_a_sample_is_left_alone`) and an ASC tie-break (the duplicate test now has a stale and a fresh duplicate).
- Follow-up after lead PR #125 (CR-3 and CR-4 approved by Gabriel 2026-11-09), each test-first:
  - CR-3: `template_csv(name, "example", "RETAIL")` returns the Retail sample on `EXAMPLE_AS_OF`; `data/templates/examples/retail/*.csv` are generated by `generate_samples.py` with the same byte drift check; `template_catalog("RETAIL")` offers examples (a mode-less catalog still offers none). The Retail sample gained a `routes.csv` (DC→each store with a cost, a 400-unit batch cap to S07, S01→S02 disabled), so every template has a filled example in both modes; its RNG draws come last, so the other Retail files are byte-identical. The Retail `demand_history` example is 2.77 MB (20 stores × 50 products × 90 days), because the examples are the sample itself.
  - Lead-authorized edit (2026-11-09) in lead-owned `tests/imports/test_templates.py::test_example_route_takes_an_optional_mode`: only the RETAIL+example assertion changed, from 404 `TEMPLATE_EXAMPLE_UNAVAILABLE` to 200 with the Retail text, which differs from Pantry. The rest of the test is unchanged. The `AccessError` import left `templates.py` with its only use.
  - CR-4: `ensure_samples` no longer commits its caller's session; `local_bootstrap.run` commits the organization first (lead, #125). `test_leaves_the_callers_transaction_to_the_caller` failed before the change.
  - Verifier N1: `test_seed.seed()` commits the organization, then seeds in its own transaction, as the bootstrap now does; the module and helper docstrings say so.
  - The web's example URL (`network-api.ts:18`) needs `&mode=`; the w3-web lane has that follow-up (lead, 2026-11-09).
- Demand follows real weekdays (busy Saturdays, quiet Sundays), so a sample generated on a later day has different quantities; determinism is per (seed, date) — W3-P01.

## Gotchas

- **Seed deadlock (confirmed, fixed in W3-P04):** `local_bootstrap.run` calls the seed inside one ORM transaction that has already run `INSERT INTO organizations` (ROW EXCLUSIVE). Publishing an import runs `ALTER TABLE net_batches ATTACH PARTITION …`, which requests SHARE ROW EXCLUSIVE on `organizations` (the partition's FK to it is cloned at attach, `staging.py:64-67`). Observed in `pg_stat_activity`/`pg_locks`: the ATTACH (pid 5305) waited on the seed's own idle-in-transaction connection (pid 5304), a client-side deadlock PostgreSQL can't detect; the test hung until killed. Fix: `ensure_samples` commits the caller's session before importing (each sample import already commits on its own connections, so the seed was never atomic). `test_seed.py` sets `lock_timeout = 30s` per transaction, so a regression fails in ~60 s instead of hanging the 480 s api-tests step. **Any future caller that imports or publishes while holding an open write on `organizations`, `dataset_versions`, `net_locations` or `net_products` will deadlock the same way.**
- `tests/test_local_bootstrap.py`'s `db` fixture truncates `organizations` before each test, so once `ensure_samples` is real, each of its ~10 `run()` calls imports both samples (Retail is ~90k sales rows). Measured: about 1.1 s per `run()`, 14.5 s for the module (10 tests).
- The fixture forecast job in `tests/networks/test_build_scenario.py` caps output at 10,000 bytes (`OUTPUT_TOO_LARGE` even for the 48-series Pantry sample). `test_seed.py`'s `sample_sized_forecasts` fixture swaps in the same registration with 50 MB caps; it must be requested before `forecasts`.
- psycopg 3 connects through libpq (C sockets), so patching Python's `socket` in the no-outbound test can't break the test's own database connection.

## Known limitations (verifier F3–F5, accepted for the PR)

- F3: a failed sample import leaves its import run (`failed`) and, for a new network, its organization row; abandoned-import cleanup is deferred to W5 (W2-06 §5 D). A restart imports the missing sample once; nothing is duplicated (verified).
- F4: a sample import error raises, so the `seed` service fails and compose doesn't start `api`/`worker`. Chosen deliberately: the samples are our own generated files, and the verifier's date sweep found no failing date. Lead call whether a sample failure should instead be logged and skipped.
- Follow-up: an install seeded before the Retail `routes.csv` keeps that Retail version (estimated routes only) until it's more than 7 days old; freshness is by date only (verifier, Info).
- Follow-up: until the w3-web `&mode=` fix lands, the Retail import page's example links download the Pantry examples (verifier, Medium; merge order above).
- F5 (resolved by CR-4): `ensure_samples` no longer commits its caller's session; the caller must not hold an organizations write (see the deadlock gotcha). Concurrent seeds are serialized by an advisory lock since the PR review (L1).

## Change requests

### CR-w3-samples-1 — sample rates read "sample values", not "manual"
- **File(s):** `apps/api/app/services/enrichment/service.py` (merged W1 code; no W3 lane owns it), a test in `apps/api/tests/enrichment/`.
- **Exact change:** `_ATTRIBUTES` also selects `EXISTS (SELECT 1 FROM dataset_versions v JOIN networks n ON n.id = v.network_id WHERE v.id = net_locations.dataset_version_id AND n.is_sample) AS is_sample`; in `_attributes`, the all-manual branch sets `source = "sample values" if r.is_sample else "manual"` (state stays `manual`). `scenario.py:327`'s `a.source or "manual"` then freezes "sample values" too. Test: a network imported with `create_import(..., is_sample=True)` whose locations.csv gives both rates reports `source == "sample values"` from `location_attributes`, and a non-sample network still reports `"manual"`.
- **Why:** W2-06 §3 carry-in and V1-SPEC §8 ("poverty/SNAP values pre-filled and labeled 'sample values'"). The label is hard-coded at `enrichment/service.py:170`. The samples and `data/samples/README.md` already say "sample values"; only the in-app label is missing.
- **Unblocks:** the in-app half of the "sample values" carry-in (W3-P01 is otherwise done).
- **Status:** merged (lead PR #122, `5c5fbe7`); merged into the lane at `a172430`.

### CR-w3-samples-2 — keep template CSVs LF on a Windows checkout
- **File(s):** `.gitattributes` (lead-only).
- **Exact change:** add `data/templates/**/*.csv text eol=lf`.
- **Why:** `.gitattributes` covers `*.sh`, `*.py`, `*.yaml` but not CSV. With `core.autocrlf=true` (the Git for Windows default) the blank and example templates check out as CRLF. Correction (code review R8): the original justification said both drift tests fail on CRLF. They didn't, because both used `read_text`, which turns CRLF into LF, so the drift check missed it. Since R8, `test_example_files_equal_generator_output` and `generate_samples.py --check` compare bytes, so a CRLF checkout fails them (e.g. `npm run test:api:docker` on the Windows host). `test_blank_templates_are_header_only` (W1) still uses `read_text` and passes. The importer accepts CRLF, and the downloads are computed, not read from disk.
- **Unblocks:** nothing on Linux/CI; Windows-host test runs.
- **Status:** merged (lead PR #122, `5c5fbe7`); merged into the lane at `a172430`.

### CR-w3-samples-3 — Retail template examples (a `mode` on the example download)
- **File(s):** `apps/api/app/routers/v1_networks.py:55` (lead), the frozen `template_csv(name, kind)` signature, `packages/contracts/**` (regenerated), the web's `templateUrl` (w3-web paths).
- **Exact change:** `GET /templates/{name}.csv?kind=example&mode=PANTRY|RETAIL` (mode optional, default PANTRY); `template_csv(name, kind, mode=None)`. The lane then adds the Retail branch (the Retail sample on `EXAMPLE_AS_OF`), `data/templates/examples/retail/*.csv` with the same drift check, and `example_available=True` for Retail.
- **Why:** V1-SPEC §6.1 gives every template a filled example; today Retail has none (verifier F1, mitigated by reporting `example_available=False` in Retail mode).
- **Unblocks:** Retail example downloads. Non-blocking for this PR.
- **Status:** approved (Gabriel, 2026-11-09). The lead built the route `mode` (#125); the lane built the Retail examples in its follow-up.

### CR-w3-samples-4 — the bootstrap's seed date and transaction
- **File(s):** `apps/api/scripts/local_bootstrap.py:104-125` (lead).
- **Exact change:** (a) pass `today=datetime.now(ZoneInfo("America/New_York")).date()` (the samples' timezone, `samples.network.TIMEZONE`) instead of `date.today()`, which is the container's UTC date; (b) call `seed_local.seed` after the login transaction commits (its own `Session`), so `ensure_samples` no longer has to commit the caller's session.
- **Why:** (a) between 20:00 and 24:00 New York time (UTC is already the next day), a seed dates the samples one day ahead of their own timezone: the as-of date is "tomorrow" for a New York user, and history ends "today". (b) code review R6 / verifier F5: the bootstrap is no longer atomic, and the commit in `ensure_samples` exists only because of the shared transaction (see the deadlock gotcha).
- **Unblocks:** removing F5. Non-blocking for this PR.
- **Status:** approved (Gabriel, 2026-11-09). The lead built (a) and (b) (#125); the lane removed the commit from `ensure_samples` in its follow-up.

## Escalations
