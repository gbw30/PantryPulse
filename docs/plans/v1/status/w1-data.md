# Status — `w1-data`

**Lane:** `w1-data` · **Branch:** `lane/w1-data` · **Base SHA:** `39090104222e6a67b60f8d9fa0c9e798c68a38d7` · **Last update:** 2026-11-07 · **Head:** see `git log -1 origin/lane/w1-data`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W1-D01 | done, except the ACS poverty/SNAP fixture (blocked, CR-w1-data-1) | `5b5e45e` | `uv run --frozen pytest -q tests/enrichment/test_fixtures_shape.py` → 4 passed, 0 skipped |
| W1-D02 | done | see `git log --grep W1-D02` | `uv run --frozen pytest -q tests/imports/test_validation.py` → 39 passed, 0 skipped; `ruff check .` → clean |
| W1-D03 | todo | — | — |
| W1-D04 | todo | — | — |
| W1-D05 | todo | — | — |
| W1-D06 | todo (ACS part depends on CR-w1-data-1) | — | — |
| W1-D07 | todo | — | — |
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
- **Status:** open

## Escalations

- 2026-11-07 — W1-D01/W1-D06 — the Census Data API requires a key ([ORCHESTRATION.md §5](../ORCHESTRATION.md#5-escalation-stop-and-report) items 4 and 5) — evidence: `apps/api/tests/fixtures/census/acs-missing-key.json`. Filed as CR-w1-data-1.
