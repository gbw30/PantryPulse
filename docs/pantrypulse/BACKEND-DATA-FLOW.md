# Proposed Backend Data Flow and API Behavior

> **Current authority:** [Project specification V5](SPEC-V5.md). Explanatory reference. V5 supersedes conflicting target, transfer-mode, proxy/job, scenario and supplier policies and distinguishes implemented from planned behavior.

The backend is proposed to take **records of stock, past demand, donations, and operating rules**, turn them into **estimates of future shortages**, and then calculate **feasible recommendations for moving resources between locations**.

There are three distinct kinds of output:

- **Recorded facts:** what stock was reported, what people requested, and what actually moved.
- **Predictions:** what demand, donations, and shortages might look like.
- **Recommendations:** which transfers or supplier orders could help under stated assumptions.

Those distinctions matter because generating a prediction or recommendation must not change recorded physical stock. The following describes the proposed design in the [V4 spec](SPEC-V4.snapshot.txt); most domain behavior is still to be implemented.

## 1. The backend receives several kinds of structured data

Most inputs are rows in PostgreSQL tables, submitted through JSON requests or CSV imports.

| Data | Simple meaning | Technical representation |
|---|---|---|
| Organizations, sites, and products | Who operates the network, where supplies are kept, and what is distributed | Relational records with UUID identifiers and foreign keys connecting them |
| Inventory lots | A particular batch of a product at a location | Integer stock and reservation counts, product/site IDs, expiration date, eligibility status, receipt timestamp |
| Demand observations | How many units people requested and received each day | Daily time-series rows keyed by site, product, and date; requested/fulfilled/unmet counts |
| Donation observations | How much donated supply was historically offered or received | A separate daily time series with donation quantities and source information |
| Expected supplies | Shipments expected to arrive in the future | Dated quantities with source and status enums such as `CONFIRMED` or `CANCELLED` |
| Operational constraints | What movements are possible | Capacities, reserves, route availability, arrival times, and compatible product units |
| Beneficiary attributes and policies | How the allocation should prioritize different needs | Numeric attributes, normalized scores, weights, thresholds, and versioned policy settings |
| Scenarios | A hypothetical change to the situation | Validated JSON overrides linked to baseline data and forecast versions |
| Events | What was changed, approved, or completed | Append-only records with timestamps, actors, reasons, and duplicate-operation protection |

A **UUID** identifies a record. A **foreign key** connects records—for example, an inventory lot references its owning site and product. An **enum** restricts a field to known values, such as `DRAFT`, `APPROVED`, or `STALE`.

Dates also have two meanings: an event timestamp records when something happened, while a site-local calendar date identifies an operational day.

## 2. Inventory data becomes a calculated view of what is actually available

In simple terms, “we have 100 meals” is insufficient for planning. The backend must determine how many are usable, how many are already promised, and how many can leave without harming the donor site.

An illustrative inventory lot might contain:

```json
{
  "site_id": "HUB",
  "product_id": "MEALS",
  "on_hand": 100,
  "reserved": 20,
  "expires_on": "2026-11-01",
  "safety_status": "ELIGIBLE"
}
```

Readable identifiers are used here for explanation; actual identifiers would be UUIDs.

The backend derives several quantities from that record:

| Quantity | Meaning in this example |
|---|---|
| Physical on-hand stock | 100 meals are recorded at the hub |
| Unreserved stock | 80 meals remain after existing reservations |
| Eligible stock | Up to 80, provided the lot meets eligibility and date rules |
| Transferable stock | Potentially less than 80 after protecting local demand and minimum reserves |

For example, if the hub needs 50 meals for local requests and must retain 10, its transfer budget could be:

```text
100 on hand − 20 reserved − 50 local demand − 10 reserve = 20 meals
```

The backend also checks whether those meals can arrive and be used before expiration. Among otherwise interchangeable eligible lots, it must enforce **FEFO: first expiring, first out**.

The output is an inventory response that explains physical stock, reservations, eligible availability, incoming shipments, and exclusions. Expired lots remain in the database for audit and waste reporting.

When someone submits an adjustment, such as “subtract five damaged meals,” the backend performs a database transaction:

1. Check that the caller’s inventory version still matches.
2. Validate that the adjustment would not produce negative stock.
3. Record the signed change and reason in the inventory ledger.
4. Update stock and increment its version.
5. Mark affected plans stale.

The version check prevents two requests from independently changing stock based on the same outdated balance.

## 3. Historical observations become time series, then forecasts

In simple terms, the backend organizes past activity into daily sequences and asks a forecasting model what the next seven days could look like.

A demand observation might be:

```json
{
  "site_id": "PANTRY_A",
  "product_id": "MEALS",
  "day": "2026-10-23",
  "requested_units": 60,
  "fulfilled_units": 45,
  "unmet_units": 15
}
```

This means people requested 60 meals, but the pantry served 45.

The preferred forecasting target is **60 requested meals**. Forecasting only the 45 served could underestimate need because the pantry may have run out.

Technically, the backend:

- Groups records by `(site_id, product_id, target_type)`.
- Sorts each group by date.
- Checks duplicate records and missing dates.
- Preserves observed, proxy, and simulated provenance.
- Builds a daily numerical series for the forecasting adapter.

For example:

```text
Pantry A / Meals / DEMAND:
date → requested units

Hub / Meals / DONATION:
date → observed donated units
```

Demand and donations are separate targets. A donation forecast estimates uncertain supply; it does not create a confirmed shipment.

The proposed forecasting interface supports Chronos-2 where feasible and a simpler seasonal baseline. The baseline can use the previous comparable weekday. Failures or insufficient history must produce explicit fallback or data-availability information.

A forecast point could look like:

```json
{
  "site_id": "PANTRY_A",
  "product_id": "MEALS",
  "target_type": "DEMAND",
  "day": "2026-10-24",
  "p10": 35.2,
  "p50": 42.6,
  "p90": 57.1,
  "interval_method": "model_quantiles"
}
```

In simple terms: the model gives a central estimate of about 43 meals, with lower and upper estimates reflecting its uncertainty.

Technically, these are numerical forecast quantiles. The backend preserves their original precision for evaluation. The proposed integer planner rounds scenario-adjusted daily demand upward when constructing unit counts.

The output includes both the points and run metadata: model/version, historical cutoff, generation time, status, provenance, and fallback information. [Source: forecasting specification, section 9](SPEC-V4.snapshot.txt).

## 4. Forecasts and inventory become daily shortage projections

This stage answers: **“Given the stock and arrivals we are assuming, how much demand could we serve each day?”**

The backend combines:

```text
Eligible starting stock
+ eligible arrivals
− outgoing commitments
− forecast demand
```

It evaluates these quantities on the relevant dates, including expiration and arrival eligibility.

Consider a pantry with 40 meals and forecast demand of 50 today and 40 tomorrow, with no arrivals:

| Day | Stock available | Demand | Served | Unmet | Ending stock |
|---|---:|---:|---:|---:|---:|
| Today | 40 | 50 | 40 | 10 | 0 |
| Tomorrow | 0 | 40 | 0 | 40 | 0 |

The output is **50 total unmet meals**.

The backend must not repeatedly count a cumulative deficit. A cumulative balance of −10 today and −50 tomorrow does not mean 60 unmet meals.

The proposed daily calculation treats unserved demand as lost demand; it does not automatically add yesterday’s unmet requests to tomorrow’s forecast.

Outputs include:

- Daily projected stock, served demand, and unmet demand.
- First projected shortage date.
- Total unmet units over the selected horizon.
- Central or conservative planning mode.
- Included supply assumptions and data availability.

A conservative demand projection may use upper quantiles, but it must not present that calculation as a calibrated probability of stockout.

## 5. A scenario creates an alternative set of planning inputs

In simple terms, a scenario asks a “what if” question.

For example:

```json
{
  "name": "Demand surge",
  "forecast_run_id": "FORECAST_1",
  "overrides": {
    "demand_multiplier": 1.25
  }
}
```

If baseline daily demand is `42.6`, the scenario produces:

```text
42.6 × 1.25 = 53.25 forecast units
ceil(53.25) = 54 units for integer planning
```

The historical observations and saved baseline forecast remain intact. The scenario stores the modification.

For a reproducible plan, the backend also retains the relevant inventory version, lots, supplies, dates, constraints, attributes, and policy version. The design calls for immutable snapshots or immutable version references, plus hashes identifying the input contents.

The output is a scenario ID and a retrievable configuration that can feed shortage projection and optimization.

## 6. The optimizer turns a snapshot and policy into an allocation recommendation

This is the decision-making stage.

The input is a structured planning problem containing:

- Demand targets by beneficiary and product.
- Eligible lots and quantities.
- Local supply and confirmed arrivals.
- Donor reserves.
- Allowed movements and arrival times.
- Receiving and handling capacities.
- Policy weights and thresholds.

Technically, OR-Tools CP-SAT works with **integer decision variables**. For example:

```text
x[hub, pantry_a, lot_1] = number of units to transfer
```

The backend constructs constraints around those variables:

```text
Outgoing quantity cannot exceed transferable stock.
Incoming quantity cannot exceed receiving capacity.
Transfers must use compatible products and units.
Arrival must occur before the need it claims to address.
The same stock cannot be allocated twice.
```

It then chooses values that improve the selected objective.

V4 proposes two methods:

| Method | What it tries to achieve |
|---|---|
| `CLASSICAL_GP` | Reduce normalized shortfalls using conventional policy weights and the declared objective |
| `EGP_PI_INSPIRED` | Also account for vulnerability-weighted shortfalls and absolute/relative deprivation penalties |

For the research-inspired method, the backend calculates:

```text
unmet units = target units − projected fulfilled units
normalized deficit = unmet units / target units
weighted deficit = vulnerability weight × normalized deficit
```

If a pantry needs 100 meals and can serve 60:

```text
Unmet = 40
Normalized deficit = 0.40
```

With a vulnerability weight of `1.5`:

```text
Weighted deficit = 1.5 × 0.40 = 0.60
```

The backend then checks whether this exceeds an absolute threshold, or exceeds its comparison group’s average by a relative threshold. These penalties participate in choosing the allocation.

Both methods receive the same operational inputs and constraints. Their outputs may differ because their objectives differ. The comparison can therefore expose trade-offs: one method may reduce a deprivation measure while increasing cost or another shortfall measure.

After solving, an independent evaluator checks the transfer vector and recomputes projected service. A shipment is not automatically counted as fulfilled demand; its stock must arrive in time and support actual projected service.

The saved output includes transfers, per-site fulfillment and unmet demand, objective components, policy versions, solver status, and runtime. [Source: proposed mathematical contract](../architecture/0001-v4-research-first.md#proposed-v4-mathematical-contract).

## 7. A concrete example shows the final output

Suppose we examine a two-day window with one product, meals:

| Input | Pantry A | Pantry B |
|---|---:|---:|
| Current physical stock | 40 | 100 |
| Forecast demand over two days | 80 | 60 |
| Required donor reserve | 0 | 20 |

Assume Pantry B’s lot is eligible, the transfer can arrive before demand, receiving capacity is sufficient, and there are no other commitments.

Before transfers:

- A can serve 40 of 80 meals, leaving 40 unmet.
- B can serve its 60 meals and retain 40.
- B can transfer 20 while preserving its required reserve of 20.

A feasible recommendation is therefore to send 20 meals from B to A.

| Projected result | Before plan | With proposed plan |
|---|---:|---:|
| A’s fulfilled demand | 40 | 60 |
| A’s unmet demand | 40 | 20 |
| B’s fulfilled demand | 60 | 60 |
| B’s ending stock | 40 | 20 |
| Network unmet meals | 40 | 20 |

An illustrative API result could be:

```json
{
  "plan_id": "PLAN_1",
  "data_snapshot_id": "SNAPSHOT_1",
  "method": "CLASSICAL_GP",
  "solver_status": "FEASIBLE",
  "plan_status": "DRAFT",
  "transfers": [
    {
      "from_site_id": "PANTRY_B",
      "to_site_id": "PANTRY_A",
      "product_id": "MEALS",
      "lot_id": "LOT_B1",
      "quantity": 20
    }
  ],
  "unmet_before": 40,
  "unmet_after": 20
}
```

This is explanatory arithmetic, not an actual solver result. At this point, the database still records physical stock of **40 at A and 100 at B**. Those numbers change only through a recorded movement.

Under the proposed P1 lifecycle, approval would reserve 20 at B. Completion would transactionally debit B by 20, credit A by 20, and release the reservation. An idempotency key identifies that operation so a repeated request cannot move the same stock twice.

## 8. The API exposes these stages as explicit operations

A frontend would typically follow this sequence:

| Action | Request | Output |
|---|---|---|
| Load current conditions | `GET /api/v1/dashboard/summary` | Saved summaries and provenance |
| Start prediction | `POST /api/v1/forecast-runs` | `202 Accepted`, run ID, queued status |
| Check prediction | `GET /api/v1/forecast-runs/{id}` | Running, succeeded, or failed status and metadata |
| Retrieve predictions | `GET /api/v1/forecast-runs/{id}/points` | Dated forecast values |
| Create a what-if case | `POST /api/v1/scenarios` | Scenario ID and validated assumptions |
| Calculate shortages | `GET /api/v1/shortages` | Daily deficits and first shortage date |
| Compare decisions | `POST /api/v1/scenarios/{id}/compare-methods` | Paired plans, changed assignments, and metric differences |
| Inspect a recommendation | `GET /api/v1/plans/{id}` | Saved decisions, assumptions, status, and explanations |

The API returns `422` for invalid inputs and `409` when inventory or policy versions conflict with the request. Forecast jobs expose their progress; plan results expose whether the solver proved optimality, found a feasible solution, or failed to produce one.

Supplier replenishment follows a related path: shortages, offers, lead times, minimum quantities, and spending policies produce a **draft order proposal** with quantity, estimated price, and arrival assumptions. In the proposed MVP, that remains a simulation and does not contact a vendor. [Source: API contracts, section 8](SPEC-V4.snapshot.txt).
