# W2-06 decisions: open change requests from wave 1, and the adversarial pass

**Status:** decided by Gabriel, 2026-11-08 ("approve all as recommended"; the `net_batches` partition was approved the same day). **Applies to:** W2-06 Step 2, the W3 lanes (`wave-3.md` carry-ins), W4 and W5.

## 1. Adversarial pass (W2-06 Step 1)

The `adversarial-reviewer` ran on `v1-local` `9f8c7a3` with the V1-SPEC §6 seed cases.

- **Holds:**
  - duplicate keys after trimming;
  - a UTF-8 BOM;
  - a second import during an import (409);
  - a Census outage, then a retry;
  - the Google key never appears in an error;
  - every product at zero stock;
  - every route disabled;
  - USD with one price missing.
- **Broken, reproduced by the lead:** a NUL byte in a CSV header (for example UTF-16 without a BOM) reached PostgreSQL as text. The resulting `DataError` escaped `Supervisor._publish`, which catches only its own exception types, and stopped the worker. Fix packet `w2/fix-nul-header`:
  - a NUL in a header is a row error;
  - an unexpected exception during publish fails that attempt with `PUBLICATION_STORAGE_FAILED` (an existing reason code), and the supervisor keeps serving.

## 2. A: land in W2-06, before W3

| # | Change | Where |
|---|---|---|
| 1 | `forecast.v1` joins `V1_NETWORK_JOBS`, so `GET /jobs/{id}` answers for a network forecast under its network's organization. `forecast.chronos.v1` is not included; if W3-F03 runs Chronos for networks, that is a CR. | lead, `0730730` |
| 2 | The importer sets `networks.is_sample` | data fixer |
| 3 | CR-w1-web-4, defined below | lead, `be50335` |
| 4 | Solver S2: `MethodResult.solver` records engine, OR-Tools version, seed and worker count for the three optimizers. It is null for the deterministic baselines, and its null default keeps saved comparisons valid. | lead, `5adbe31` |
| 5 | A fractional `handling_units_per_unit` is a row error at import, not a freeze blocker | data fixer |
| 6 | Solver S3: lots already expired at `as_of_date` are left out of the frozen scenario and listed as an assumption | data fixer |
| 7 | A Census `Non_Exact` match stays non-blocking (W1-D06), but its source reads "unconfirmed address match" | data fixer |
| — | `net_batches` partitioned by dataset version (`ppv1_0013`), because publish held the lock 6.25 s and 4.91 s on Docker Desktop (above 3.5 s; W2-05) | partition builder |

### CR-w1-web-4: the network forecast series read and per-location accuracy

- **(a) `GET /networks/{id}/forecasts/{forecast_run_id}` → `NetworkForecastRun`.** It returns every series of a published run, keyed by the CSV `location_id`/`product_id`. The run itself stores `net_locations.id`/`net_products.id` (W1-D09), and the read maps them back. Each `NetworkSeries` has:
  - `kind`: `demand` or `donation`;
  - `basis` (demand series only), `unit` (the product's own);
  - `status` with a `reason` whenever there is no forecast;
  - `actual_provider`, `fallback_used`, `fallback_reason`;
  - `observed_count` and `missing_count`;
  - seven `ForecastPoint`s.

  The validators refuse:
  - an `AVAILABLE` series without a provider and seven points;
  - points on a series that has no forecast;
  - a fallback without a reason;
  - a basis on a donation series.

  Quantiles appear only when the provider produced them (`ForecastPoint`).

  The run also carries `dataset_version_id` and `data_cutoff_date`, which equal the version's `as_of_date`. Those are the conditions `create_scenario` checks. Until W3-F03 builds it, the route is a 501 stub.
- **(b) `BacktestResult.locations`.** Each row is `{location_id, unit, series_count, score}`, a location's roll-up on the pooled scored set of its demand series in **one unit**. The web lane asked for one pooled figure per location. Pooling series measured in different units (cases with pounds) would add quantities that can't be added (product truth), so a location has one row per unit. A one-unit network still gets one row per location.

## 3. B: handed to the W3 lanes

These are recorded as carry-ins in `wave-3.md`.

- **web:**
  - The import page states that addresses without coordinates are sent to the Census geocoder. V1-SPEC line 48 requires an explicit, labeled lookup.
  - Remove the "simulated network" wording on real imports (the Live chip, the Atlas subtitle, the session footer).
  - The header date is the snapshot's `as_of_date`, not today.
  - Fix the product picker that stays on "Loading products…".
  - Don't show the legacy fixture atlas above an imported network's ranking.
  - Wire names in the trust panel and Decisions.
  - The column guide says that a pantry given coordinates also needs both rates, or an exclusion.
- **samples:** sample rates are labeled "sample values", not "manual" (V1-SPEC §8).
- **forecast:** W3-F04/F05 reuse `services/optimization/projection.py::project_v3`, which already counts frozen inbound once. The danger ranking and the solver then share one projection kernel.

## 4. C: deferred to W4 (hardening)

- Solver S1: an independent FEFO check in the verifier.
- The F2 residual.
- One tenancy helper.
- Cancel and retry for v1 jobs.
- Enrichment says why it didn't start.
- Reverse geocoding when a location's coordinates are given (today it gets no tract and no ACS rates).

## 5. D: deferred to W5, disclosed as known limits

- An external batch id field. Only ids over 64 characters or containing `/` are hashed.
- An abort route and the cleanup of abandoned import runs and files (W0-08 §4).
- The staged-table sweep assumes one supervisor; compose runs one.
- Import progress has no live row count. V1-A09 needs only a durable job with progress, which exists.
- Publish retry backoff.

## 6. E: recorded as designed

Enrichment writes geocodes and ACS rates onto the published dataset version's locations. A scenario freezes the values it reads, so a scenario created before enrichment finished keeps its own copy, and its hash doesn't change.
