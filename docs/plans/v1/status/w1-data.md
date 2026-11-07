# Status — `w1-data`

**Lane:** `w1-data` · **Branch:** `lane/w1-data` · **Base SHA:** `39090104222e6a67b60f8d9fa0c9e798c68a38d7` · **Last update:** 2026-11-07 · **Head:** see `git log -1 origin/lane/w1-data`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W1-D01 | done, except the ACS poverty/SNAP fixture (blocked, CR-w1-data-1) | `5b5e45e` | `uv run --frozen pytest -q tests/enrichment/test_fixtures_shape.py` → 4 passed, 0 skipped |
| W1-D02 | done | `2d14868` | `uv run --frozen pytest -q tests/imports/test_validation.py` → 39 passed, 0 skipped; `ruff check .` → clean |
| W1-D03 | done | `22fb017` | `uv run --frozen pytest -q tests/imports tests/enrichment tests/test_v1_contract.py` → 121 passed, 0 skipped (22 in `test_templates.py`); `ruff check .` → clean |
| W1-D04 | done | see `git log --grep W1-D04` | `uv run --frozen pytest -q tests/test_v1_contract.py tests/imports tests/enrichment` (PostgreSQL `pantrypulse_data_test`, schema `w1_data_import_test`) → 132 passed, 0 skipped; `ruff check .` → clean |
| W1-D05 | in progress: create, commit admission, status, network reads done; worker waits for the lead's load hook (CR-w1-data-2 decided) | see `git log --grep W1-D05` | `uv run --frozen pytest -q tests/imports/test_import_job.py` → 11 passed, 0 skipped |
| W1-D06 | done; auto-start of enrichment after an import comes with the import.v1 worker (CR-w1-data-2 hook) | see `git log --grep W1-D06` | `uv run --frozen pytest -q tests/workers/test_v1_job_kinds.py tests/enrichment tests/imports tests/test_v1_contract.py` → 179 passed, 0 skipped; `node scripts/quality/run.cjs quick` PASS |
| W1-D07 | done | see `git log --grep W1-D07` | `uv run --frozen pytest -q tests/enrichment tests/imports tests/test_v1_contract.py` → 149 passed, 0 skipped; quick gate PASS |
| W1-D08 | todo | — | — |
| W1-D09 | todo | — | — |

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- Census fixtures wrap the raw response text in JSON (`recorded`, `request`, `response.body`), because the batch geocoder answers with CSV. The test transport replays `body` byte for byte. — W1-D01.
- Google endpoint: Routes API `computeRouteMatrix`, `TRAFFIC_UNAWARE` (Essentials SKU), one request per receiver so the preview count equals the billed element count. — W1-D01, S6.

- One validator implementation: the pure streaming `Validator` (W1-D02) also runs inside the import job while it COPYs trimmed cells into `import_staging` (W1-D04). Staging then feeds the set-based commit (casts and external-ID joins in SQL); the eight error classes are not re-implemented in SQL. Why: one tested rule set instead of two that can drift; S4 measured `csv.reader` → COPY at 5.5 s for 4.5 M rows. Bench in W1-D05 checks the total. — W1-D02/D04.
- Error codes stay within the frozen `ErrorCode` set: a bad date, non-US state, unknown role, bad header and non-UTF-8 file are `MALFORMED`; a quantity above the or-input-v3 `Count` bound (100,000) and history older than 90 days are `OVER_ENVELOPE`. — W1-D02.
- Header problems give one error per file (all unknown/missing columns in one reason). An ID that appears in its file counts as known for references even if its row has another error, and a file that can't be read suppresses UNKNOWN_ID checks against it, so one root cause isn't repeated per reference. — W1-D02.
- `3.0` counts as FRACTIONAL (digits only), as in S4. Donation rows for the same location × product × day are summed and donors joined; demand duplicates are errors. Inbound arrivals on or before `as_of_date` are rejected (they belong in inventory.csv); arrivals after the seven-day horizon are kept and marked. — W1-D02.

- Blank templates are generated from `columns.COLUMNS` (one list for validator, templates and guide); the files in `data/templates/blank/` are checked byte-equal by a test. `GET /templates` without a mode lists all four location types. Guide copy for `poverty_rate`/`snap_rate` went through `research-claims-check` (names `EGP_PI_INSPIRED`, no outcome claims). Removed the two W1-D03 rows from `STUBS` in `tests/test_v1_contract.py`. — W1-D03.

- The import runs in ONE transaction (staging partition, validation + COPY, commit, ATTACH, DROP staging); a failure is a rollback, then the report is written in its own transaction. Progress goes through a second connection. Phases: `staging` = the streaming read/check pass (rows), `validating` = end-of-pass result (checks = files), `committing` (rows). — W1-D04.
- A failed import keeps its run, errors and uploaded files (W0-08 §4); a successful commit deletes the files. W0-08 §2 says files go "after a commit or an abort"; I read "abort" as an explicit user abort, which no route offers yet. — W1-D04.
- `routes.csv` rows are stored with the computed routes at commit (`distance.route_rows`). A blank `travel_days` overrides nothing: the straight-line estimate and its `straight_line_estimate` label stay, and the row is marked `override`. A blank `travel_days` where either end has no coordinates is an import row error (`travel_days`, MALFORMED, fix: enter days or add latitude/longitude), so no stored route lacks `travel_days` (orchestrator guidance). — W1-D04/D07.
- Routes are computed at import only for locations with coordinates; locations geocoded later get theirs when W1-D06 refreshes routes after geocoding. `net_routes.distance_miles` stores road miles (straight × 1.3); `road_hours` = road miles / 45. — W1-D07.
- Enrichment fills only unknown fields: given coordinates are never geocoded (and so get no tract and no ACS rates: they stay EGP blockers until a manual value or an exclusion), geocoded coordinates and looked-up rates are never overwritten, and manual values (template or `PUT …/attributes`) live in their own columns beside the looked-up ones. The attribute state is excluded > manual > known (both rates) > unknown. — W1-D06.
- Census `Non_Exact` matches are stored but listed with the unmatched addresses, the hint showing the address Census matched (S5 found it can flip the street direction). — W1-D06.
- ACS source text is `ACS 5-year {year}, tract {11-character GEOID}` (the full GEOID; a 6-digit tract code repeats across counties). `fetched_at` is the bundled table's `generated_at`, when the numbers left Census. `acs_source` stores `ACS5 B17001,B22003`. A missing table leaves rates unknown and says so in `last_error`. — W1-D06.
- EGP blockers are pantries only (EGP weighs receiving pantries; hubs never receive). — W1-D06.
- enrichment.v1: the payload carries the addresses still unlocated (read at submit), the one `geocode` step calls Census with no DB access, and `publish` writes about 100 location rows plus the refreshed routes (no bulk load, so no `prepare`). A Census outage is a completed step, so the job SUCCEEDS and the status says `failed` with `last_error` and a retry. Status reads the latest enrichment.v1 job for the version (`compute_jobs.input_package.input.dataset_version_id`) and its published manifest (unmatched + last_error). A retry while one runs is 409 `ENRICHMENT_IN_PROGRESS`. The job tests run a real `Supervisor` with the integration `FakeDriver` (its fixture-behavior hooks monkeypatched to a no-op), so admission, claim, step, publish and status are all exercised. — W1-D06.
- Candidate routes: "k=10 nearest pantries + all hubs ≤150 mi (lead call 2026-11-07)". Each receiver gets every hub/DC within 150 miles plus the 10 nearest other senders within 150 miles; hubs never use up a pantry slot. A receiver with no hub within 150 miles gets no hub route (unreachable in HUB_ONLY; the radius is not stretched). — W1-D07.
- Removed the W1-D04 upload row from `STUBS`; its "streams past the 64 KB boundary" proof moved to `test_upload_over_cap_is_413_and_partial_file_deleted` (a 70,000-byte upload returns 200). — W1-D04.

- Commit admission needs a READY supervisor advertising `import.v1` (`policies.admission_outcome`), so in production `POST /imports/{id}/commit` answers 503 `COMPUTE_UNAVAILABLE` until the worker is built. Job tests simulate an advertising supervisor and cancel their queued jobs (`max_queued` is 2). `import_status` reports a run whose job ended FAILED/TIMED_OUT/INTERRUPTED/CANCELLED/EXPIRED without a commit as `failed` / `JOB_FAILED`. Committing is one-shot: a repeated commit returns the run's existing job. — W1-D05.

## Gotchas

- The Census Data API now requires a key for every data request (302 to `missing_key.html`); variable metadata still works keyless. — S5.
- Batch geocoder rows come back out of input order, coordinates are `lon,lat`, and errors come back as an HTML page, not CSV. — S5.
- Geocoder `Non_Exact` matches can flip the street direction (S → N, W → E); list them for review. — S5.
- Legacy Distance Matrix can't be enabled for new Google projects since October 2026. — S6.

## Change requests

### CR-w1-data-1 — The Census Data API needs a key; decide how v1 gets ACS attributes
- **File(s):** depends on the option: `docs/pantrypulse/V1-SPEC.md` §6.3 (spec text) and, for option B, a migration widening `ck_local_secrets_name` plus `LocalSettings`/settings routes.
- **Exact change:** choose one:
  - **A (recommended).** Ship a bundled ACS 5-year tract table (poverty B17001_002/001, SNAP B22003_002/001; Florida first, about 5,000 tracts) generated once by the lead with a key, and look tracts up locally after geocoding. Keyless for users, works offline, keeps V1-A03 ("no keys"). Needs: who generates it, with which key, where it lives, and the year.
  - **B.** An optional free Census key in Settings, stored like the Google key. Needs a migration (`local_secrets` name check), schema and route changes, and README copy. Without a key, attributes stay unknown.
  - **C.** No ACS lookup in v1: manual entry or explicit exclusion only. Smallest change, but every EGP network starts fully blocked.
- **Why:** live calls on 2026-11-07 to `api.census.gov/data/{2024,2023}/acs/acs5` (tract and state queries) all returned 302 to `missing_key.html`: "A valid key must be included with each data API request." V1-SPEC §6.3 says "key optional at low volume". Recorded in `apps/api/tests/fixtures/census/acs-missing-key.json`; details in `docs/plans/v1/spikes/S5-census.md`. Getting a key is a secret (lane rule 5) and the spec doesn't settle the alternative (rule 4).
- **Unblocks:** the ACS half of W1-D06 (`test_matched_address_stores_coordinates_tract_and_source` source string, `test_retry_fills_unknown_fields` for attributes) and the planned `acs-tract-fl.json` fixture / `test_acs_fixture_has_poverty_and_snap` (W1-D01). Geocoding, outage handling, manual overrides and EGP blockers can proceed.
- **Status:** decided 2026-11-07 (Gabriel, relayed by the orchestrator): **option A, whole US**. The lead generates and commits `apps/api/app/services/enrichment/data/acs5-2024-tracts.csv.gz` (header `geoid,poverty_universe,poverty_below,snap_households,snap_received`; B17001_001/_002, B22003_001/_002; empty cell = not published → unknown, never 0; 0 universe → unknown rate) and `acs5-2024-tracts.json` (vintage, survey, tables, source_urls, sha256, rows, generated_at) from the keyless bulk ACS summary files on www2.census.gov. The lane builds the lookup test-first with its own tiny fixture in that format, and merges `origin/v1-local` when the real file lands. Source text: "Source: ACS 5-year 2024, tract NNNN".

### CR-w1-data-2 — Where the `import.v1` job may touch the database
- **File(s):** `apps/api/app/services/jobs/registry.py` (`Registration`), `apps/api/app/workers/process_driver.py` (`_ENV_ALLOWLIST`, `_child_env`), and the place that starts a step child with its registration.
- **Exact change (recommended, option 1):** add `child_env: tuple[str, ...] = ()` to `Registration`; when starting a step child, pass `os.environ[k]` for `k in registration.child_env` in addition to `_ENV_ALLOWLIST`. Register `import.v1` with `child_env=("DATABASE_URL", "PP_DATABASE_SCHEMA", "PP_IMPORT_DIR")` (the lane sets that in `workers/imports.py`). The step child then runs `run_import` (W1-D04) in its own transaction and returns `{dataset_version_id, network_id, error_count}`; `publish` only re-reads `import_runs`/`dataset_versions` to confirm them (milliseconds). `run_import` is idempotent for a run already `done`, so a retry after a fenced publication doesn't import twice. `enrichment.v1` and `routes-google.v1` would need the same for W1-D06/D08.
- **Option 2 (no framework change):** the child validates and writes canonical COPY-ready files to the imports volume; `publish` COPYs them and commits. Measured parts from S4: COPY 5.5 s + commit 5.2 s at 4.5 M rows, so roughly 12–15 s **holding the queue's `compute_control` lock**, during which every admission and claim on the install waits (and may hit its lock timeout).
- **Why:** `QueueRepository.publish` holds the `compute_control` row lock for its whole transaction (`apps/api/app/repositories/jobs.py:1189`, via `_lock_claimed` → `_lock_control`), so the import can't run there at full size. Step children get only the env allowlist at `apps/api/app/workers/process_driver.py:25` (no `DATABASE_URL`, `PP_DATABASE_SCHEMA` or `PP_IMPORT_DIR`), so a step can't COPY or commit. Both are lead-owned.
- **Unblocks:** the `import.v1` handler/publisher in `apps/api/app/workers/imports.py` (W1-D05) and its job-level tests; likewise the enrichment workers (W1-D06/D08).
- **Status:** decided 2026-11-07 (Gabriel, relayed by the orchestrator): **neither option.** Import steps keep no DB access (`test_child_environment_carries_no_database_secrets` stays) and `publish` does no bulk load. Steps validate and write load-ready files; a new lead-owned framework hook runs in the supervisor after the steps and before `publish`, outside the queue lock, and bulk-loads into an unattached per-version table with its keys (S4 e4); `publish` inserts the network/version/location/product rows, adds the FKs and ATTACHes (about 1 s under the lock). All-or-nothing holds; the hook drops its staged tables when the attempt doesn't publish. The lane waits for the hook signature before changing the commit path; `run_import` (one transaction) stays as the tested reference until then.

### CR-w1-data-3 — Let enrichment.v1 be advertised for execution
- **File(s):** `apps/api/tests/workers/test_v1_job_kinds.py` (lead-owned), then `apps/api/app/workers/enrichment.py` (lane).
- **Exact change:** in `test_v1_stub_handlers_are_not_advertised_for_execution`, drop `enrichment.v1` from the kinds that must stay unadvertised (or replace the check with "every still-stubbed kind is unadvertised"), and add `assert "enrichment.v1" in advertised`. The lane then registers `EnrichmentHandler()` instead of `HeldEnrichmentHandler()` (one line).
- **Why:** the handler and publisher are built and tested end to end (`tests/enrichment/test_enrichment_job.py`: real supervisor, recorded Census answers), but the lead-owned test pins every v1 kind as unadvertised, so production keeps it held and `POST /networks/{id}/enrichment/retry` answers 503 `COMPUTE_UNAVAILABLE`. Advertising it also means the production supervisor will call `geocoding.geo.census.gov` (V1-SPEC §6.3's endpoint; the lane never calls it outside W1-D01).
- **Unblocks:** enrichment in the running app (V1-A10 live run).
- **Status:** approved 2026-11-07 (Gabriel, relayed by the orchestrator). Authorized lead-file edit, in the W1-D06 commit: only `test_v1_stub_handlers_are_not_advertised_for_execution` in `apps/api/tests/workers/test_v1_job_kinds.py` changed (enrichment.v1 is advertised; the other v1 kinds are not). `enrichment.v1` now registers `EnrichmentHandler()`.

## Escalations

- 2026-11-07 — W1-D01/W1-D06 — the Census Data API requires a key ([ORCHESTRATION.md §5](../ORCHESTRATION.md#5-escalation-stop-and-report) items 4 and 5) — evidence: `apps/api/tests/fixtures/census/acs-missing-key.json`. Filed as CR-w1-data-1.
