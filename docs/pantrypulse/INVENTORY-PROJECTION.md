# Dated inventory projection — issue #23

`projection-v1` is an internal, deterministic service for one frozen organization,
site, product and base unit. Input types are in
`apps/api/app/schemas/projection.py`; call `project_inventory` from
`apps/api/app/services/inventory/projection.py`. This is a Python service, not an
HTTP endpoint. It does not connect to Postgres, load a model or mutate stock.

## Accepted policy and scope

On October 24, 2026, the user selected BD-48: process daily confirmed arrivals,
exclude unavailable stock, apply explicit outbound commitments, then serve that
day's demand by hard FEFO. Daily unmet demand is lost sales, not backlog. BD-43/44
still apply: explicit non-expiring stock is permitted; a dated lot is usable
through its expiry day in the site's timezone. Unknown expiry is unavailable.

This resolved the projection-order portion of #11. The subsequent
[scenario-v1 contract](SCENARIO-CONTRACT.md) now defines the operational snapshot,
identity, staleness, donor/route/capacity and no-relay rules. Their allocation
enforcement, independent verification and database integration remain #24/#25/#30.
No transfer is approved by this service.

## Input boundary

- Supply all required identities, a frozen calendar/timezone, inventory version,
  snapshot and forecast IDs, actual provider, demand planning-mode label,
  assumptions and explicit `HUB_ONLY` or `HUB_AND_PANTRY` transfer mode. There is
  no default transfer mode. Both modes use the same local service arithmetic;
  route and donor permissions belong to the allocation layer.
- Supply one to seven contiguous dated `Decimal` demand estimates, starting on
  `opening_on`. Explicit zero is valid; null, missing dates, duplicates, negative,
  non-finite or above-int64 daily demand are rejected. The existing rounding helper
  takes the ceiling of each day before aggregation. No quantile/provider selection
  or demand scaling happens here.
- ON_HAND lot quantities are opening physical stock before the listed horizon
  commitments. Their local availability day cannot be later than opening day.
  Do not subtract a reservation first and submit its debit again as a commitment.
- CONFIRMED lot quantities represent only **outstanding, unreceived confirmed
  supply**, never offered or forecast donations. They enter stock once, on their
  local arrival day. Earlier arrivals must be reconciled into opening stock;
  arrivals after the horizon remain pending. Duplicate lot IDs or duplicate source
  identities within a source kind are rejected, even with different versions.
  Use one projected lot per outstanding supply/product record; split expiry lots
  must have separate operational supply identities. Source/version values must
  identify the frozen records used, not a query for “latest”.
- The caller constructs that opening boundary from consistent operational records.
  The pure function cannot prove that an already-received supply was removed from
  outstanding supply, or that a caller supplied the truthful quantity/version.
  Loading and checking that snapshot belongs to the integration layer.
- Each lot repeats ownership/site/product/unit identity; mismatches are rejected.
  Quantities are strict nonnegative int64 integers. Eligibility distinguishes
  ELIGIBLE, HELD, INELIGIBLE and UNKNOWN; expiry distinguishes DATED,
  NON_EXPIRING and UNKNOWN.
- Commitments are versioned, unique, lot-specific positive counts with a date
  inside the horizon. A commitment on an absent, not-yet-arrived, expired, held,
  unknown or insufficient lot rejects the projection. Multiple commitments cannot
  collectively overdraw a lot. Prior-day service can make a later commitment
  infeasible; the function reports that conflict rather than silently reserving
  arbitrary future stock or reducing service on prior days.

The model is daily: timezone-aware availability timestamps map to site-local
dates. All arrivals assigned to a date precede that date's service. This does not
prove intraday arrival-before-use or dispatch timing. The opening stock must match
the supplied full-day demand boundary; do not combine intraday remaining stock
with an already-partly-served full-day demand estimate.

## Calculation and output

Hard FEFO selects the earliest expiry among eligible lots of the same product.
All dated lots precede explicitly non-expiring lots. Ties use availability instant,
then lot UUID; caller input order cannot change service allocation. Commitments
debit their explicitly supplied lot; transfer FEFO feasibility is checked elsewhere.

Each day returns rounded demand, service/unmet, arrivals, newly unavailable expired
quantity, outbound quantity, eligible ending stock, physical ending stock, per-lot
service/commitment debits, remaining balances, excluded quantities/reasons and
separately pending arrivals. A future arrival is `NOT_ARRIVED`; available physical
stock can be `EXPIRED`, `HELD`, `INELIGIBLE`, `UNKNOWN_ELIGIBILITY` or `UNKNOWN_EXPIRY`.
Expired reason takes precedence, then eligibility, then unknown expiry.

Expired stock remains physically recorded; there is no simulated disposal debit.
`expired` counts the remaining quantity on the first projected day it is expired,
including stock already expired at opening or arriving expired. It is not counted
again on subsequent days. It measures newly recognized date unavailability, not
verified wastage or disposal. Exclusion lists show continuing unavailability.

For every day:

```text
served + unmet = rounded demand
physical_end = previous_physical + confirmed_arrivals - outbound - served
physical_end = eligible_end + sum(physical excluded quantities)
```

Pending arrivals do not enter physical stock. Expiry/eligibility exclusions do not
debit physical stock. All quantities and totals are per the one supplied base unit;
totals use Python integers and are not solver/storage magnitude validation.

The result contains total unmet, first deficit date, the canonical frozen inputs
and a SHA-256 projection-input fingerprint. Collections of lots/commitments are
sorted by identity; times are normalized to UTC and equivalent Decimal scales
normalize exactly, without Decimal-context arithmetic. Ordered assumptions are
preserved. This is a private `projection-v1` replay identity, **not** the final
scenario-v1 hash contract from #11 or its future #30 storage. No current database records are
read during replay; input changes create a different fingerprint. Checking whether
saved inputs are stale against live inventory is a separate caller responsibility.

Example: opening stock 40 with demand `[50, 40]` serves `[40, 0]`, records unmet
`[10, 40]`, total **50**, and identifies the first day as the first deficit.
Moving a 40-unit arrival to day two serves day two only; day one's loss remains.

## Verification

From `apps/api`, using the project Python 3.12 runtime:

```text
python -m pytest tests/test_inventory_projection.py -q -p no:cacheprovider
python -m ruff check --no-cache app/schemas/projection.py app/services/inventory/projection.py tests/test_inventory_projection.py
```

See [task packet/evidence](tasks/PP-39.md). These are pure service tests; they do
not establish an HTTP API, integration with saved forecasts, donor protection,
database snapshot loading, allocation feasibility or independent review.
