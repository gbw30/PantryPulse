# Connected e2e fixtures (w3-web)

Fictional CSV sets for the connected specs (`PP_RUN_CONNECTED=1`); they are imported through the
real API, never written to the tables. Names, IDs and quantities are invented; the coordinates are
city-level points in Florida. `pantry` follows the backend `mini-network` fixture
(`apps/api/tests/networks/fixtures/mini-network`) and adds the optional files.

- `pantry`: every location has coordinates and every pantry both rates, so enrichment never calls
  the Census geocoder. `routes.csv` overrides H1→P1 and disables H1→P3. Inbound: one delivery in the
  7-day horizon after `as_of_date` 2026-11-04, one outside it. Donations: a quantity, a reported 0
  and a blank (unknown) day.
- `bad`: one row per rejected class (duplicate key, negative, fractional, unknown ID, missing
  expiry, non-ISO date).
- `unlocated`: `pantry`'s required files plus P4 with no coordinates and no rates, so enrichment
  must look it up (V1-A10).
- `retail`: the backend `retail-twin` fixture (a distribution center and three stores, all located,
  every product priced), so a Retail comparison runs in units and in USD (V1-A15).
- `retail-noprice`: `retail` with `unit_value_usd` blank for every product, so USD is unavailable
  with its reason.
- `forecast.json` (in `pantry`, `retail`, `retail-noprice`): a FIXTURE forecast run keyed by external
  IDs, copied from the backend fixtures. `connected/seed_forecast.py` inserts it for an imported
  network because the v1 forecast routes are 501 until W4 (Escalation E-1). It is never forecast
  evidence; import, scenario, comparison, decisions and export stay real.
