# Sample networks

**Sample data — fictional.** Every name, address, quantity, price and rate in these networks is
invented. They describe no real pantry, store, chain, brand or person.

PantryPulse loads two sample networks on first start, one per network mode, so a new install
has something to explore before you import your own data. The local `seed` service imports them
through the same importer as your CSV files, and marks each network as a sample. They never call
the Census geocoder or Google: every location already has coordinates.

| Sample | Mode | Size | Generator |
|---|---|---|---|
| Sample Pantry Network (North Central Florida) | Pantry | 1 hub + 8 pantries, 6 products, 90 days of demand | `apps/api/app/services/samples/pantry.py` |
| Heronfield Market — sample retail network | Retail | 1 distribution center + 20 stores, 50 priced products, 90 days of sales | `apps/api/app/services/samples/retail.py` |

## What is filled in, and how it is labeled

- **Coordinates** are city centers rounded to two decimals (about 1 km). The `street` column
  reads "No street address (sample)": no sample location is a real building.
- **Poverty and SNAP rates** on every pantry are **sample values**: invented numbers, not
  American Community Survey estimates. Replace them, or import your own network, before reading
  anything into a Pantry comparison.
- **Dates** are relative to the day the seed runs: history ends yesterday, the inventory
  describes today (the as-of date), and batches expire in the days and weeks ahead. When the
  newest sample version is more than 7 days old, the seed adds a freshly dated version on the
  next start. Older versions and every result computed on them stay as they were; nothing is
  reset.
- **Unknown days** stay blank in the history files, never zero. Donation reports include days
  with `0` (reported, nothing received).

## Template examples

`data/templates/examples/*.csv` are the Pantry sample and `data/templates/examples/retail/*.csv`
the Retail sample, both generated for a fixed date by `apps/api/scripts/generate_samples.py`. They
are the `kind=example` template downloads (`mode=PANTRY`, the default, or `mode=RETAIL`). A test
fails if they drift from the generator by a single byte.
