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
- History (W4-02): `pantry`, `retail` and `retail-noprice` hold 42 days of demand (2026-09-23 to
  2026-11-03) in a weekly pattern, and `pantry` 42 days of P1 donations, so the journeys run a real
  forecast.v1 from the app with a backtest (35+ days). Every series keeps its own basis, and the earlier
  blank (missing) days stay blank. P3 BEANS has only a blank day, so it is never forecast. The last date
  is still 2026-11-03, so the default `as_of_date` stays 2026-11-04.
- P1 holds 1 case of Rice (W4-02, lead ruling): a plan acts only on need inside its planning window
  (`candidates.py` caps each lane at the destination's in-window unmet need), so P1 must be short by
  2026-11-06, the first day a hub transfer (shipped 11-05, 1 day) can arrive. P1's weekly Rice pattern
  has no zero day; its seasonal-naive forecast is 3 cases on 11-04 and 3 on 11-06, so the 1 case on hand
  leaves P1 short on 11-04 and on 11-06, and the methods can suggest a transfer to P1.

Known limits:
- With `--workers=2`, two specs can both seed the samples at once and race; the race fails loudly
  (it never passes wrongly). CI runs `--workers=1`.
