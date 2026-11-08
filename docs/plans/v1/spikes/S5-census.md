# Spike S5: Census geocoding and ACS attributes (W1-D01)

Status: measured on 2026-11-07 (UTC) from WSL2 on the lane machine, branch `lane/w1-data`, base `3909010`. Geocoding works with no key. **The ACS Data API refused every keyless request, so no poverty/SNAP data was recorded.** That part is blocked by `CR-w1-data-1` (status file). Spike code was throwaway: curl calls plus a short recorder script, kept outside the repo.

## Fixtures (recorded, not edited)

| File | What | Kind |
|---|---|---|
| `apps/api/tests/fixtures/census/geocode-batch-fl.json` | Batch geocoder request (13 addresses) and its raw response body | live response |
| `apps/api/tests/fixtures/census/acs-missing-key.json` | Keyless ACS 5-year tract query for Leon County and the 302 it returned | live response |
| `apps/api/tests/fixtures/census/acs-tract-fl.json` | Planned poverty/SNAP tract table | **not recorded** (needs a key, CR-w1-data-1) |

Each fixture wraps the raw response in JSON: `recorded` (kind, UTC time, note), `request`, and `response` (`status`, `content_type`, `body` as the exact text). A test transport returns `body` unchanged. The batch geocoder answers with CSV, not JSON, so the `.json` name refers to the wrapper only.

Checked by `apps/api/tests/enrichment/test_fixtures_shape.py` (4 passed, 0 skipped).

## Geocoder (keyless): works

- **Endpoint:** `POST https://geocoding.geo.census.gov/geocoder/geographies/addressbatch`, multipart form with `addressFile` (CSV rows `id,street,city,state,zip`, no header), `benchmark=Public_AR_Current`, `vintage=Current_Current`. The `geographies` variant returns the tract; the `locations` variant does not.
- **Response:** `text/plain` CSV, one row per input, **not in input order** (row 11 came first). Join on the id in column 1.
  - Match row, 12 columns: `id, input address, "Match", "Exact"|"Non_Exact", matched address, "lon,lat", TIGER line id, side (L/R), state FIPS, county FIPS, tract (6 digits), block`. Note the coordinate order: **longitude first**.
  - No match: 3 columns, `id, input address, "No_Match"`. (A `Tie` status also exists per Census docs; not observed.)
- **Match rate:** 12 of 12 real public buildings matched (10 `Exact`, 2 `Non_Exact`), and the planted nonexistent address returned `No_Match`. Addresses: county courthouses and public libraries in Tallahassee, Gainesville, Miami, Tampa, Orlando, Jacksonville, Pensacola, Clearwater and Fort Lauderdale.
- **`Non_Exact` can change the address.** Both non-exact matches flipped the street direction: `100 S Andrews Ave` → `100 N ANDREWS AVE`, `190 W Government St` → `190 E GOVERNMENT ST`. Recommendation for W1-D06: store `Non_Exact` matches but list them for review with the matched address shown, the same way as unmatched ones, so the user can confirm or enter coordinates.
- **Timing:** 0.52 s for 13 rows, twice.
- **Rate limits:** no key and no rate-limit header were seen. A published batch-size cap exists in Census's geocoder documentation; **not verified in this spike**. 100 locations fit in one call either way.
- **Error shape:** a bad parameter (`vintage=Nope`) returned an **HTML page** ("an error occurred validating and processing the parameters…"), not CSV or JSON. A client must check that the body parses as the expected CSV, not only the HTTP status.

## ACS Data API: requires a key now

- **Request tried:** `GET https://api.census.gov/data/{2024,2023}/acs/acs5?get=NAME,B17001_001E,B17001_002E,B22003_001E,B22003_002E&for=tract:*&in=state:12&in=county:073`.
- **Result:** HTTP 302 to `https://api.census.gov/data/missing_key.html`, for both years. Even `get=NAME&for=state:12` redirects. The page says: "A valid key must be included with each data API request. If you don't have one, request an API Key here."
- Variable **metadata** still answers without a key (`/data/2023/acs/acs5/variables/B22003_002E.json` → 200), which confirms the table IDs below exist.
- **Consequence:** V1-SPEC §6.3 ("Census Data API, free, key optional at low volume") no longer holds. A user without a Census key gets no ACS attributes from the API, so EGP stays blocked for every location until values are entered manually or the location is excluded. Options are in CR-w1-data-1.

### Tables chosen (IDs confirmed through the keyless metadata endpoint)

| Attribute | Numerator / denominator | Table |
|---|---|---|
| Poverty rate | `B17001_002E` (income below poverty level) / `B17001_001E` (population for whom poverty status is determined) | B17001 |
| SNAP household rate | `B22003_002E` (household received Food Stamps/SNAP in the past 12 months) / `B22003_001E` (households) | B22003 |

- **Year:** not settled; both 2024 and 2023 refused keyless queries, so availability of the 2024 5-year release was **not verified**. The stored source string stays `ACS 5-year YYYY, tract NNNN` with the year the response came from.
- A zero denominator (a tract with no households) must give an unknown rate, never 0.

## Outage behavior (what the client must treat as "unknown, retry")

Observed: a keyless ACS request (302 to an HTML page) and a bad geocoder parameter (HTML body). Not observed: a real outage, timeout or 5xx. The W1-D06 client treats any of these as unknown with a retry: connection error or timeout, non-200 status, a redirect, or a body that doesn't parse as the expected CSV/JSON. The import still succeeds (V1-SPEC §6.3).

## Outbound calls made

Only `geocoding.geo.census.gov` and `api.census.gov`, during W1-D01, as the lane prompt allows. No key was used.
