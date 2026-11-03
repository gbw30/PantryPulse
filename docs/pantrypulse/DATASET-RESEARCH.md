# Dataset research for PantryPulse V5

Researched: October 24, 2026, America/New_York. Basis: [SPEC-V5.md](SPEC-V5.md), especially sections 2, 5–10 and 16. This is a sourcing recommendation, not an amendment to V5 or a claim that an importer or dataset has been validated.

## Recommendation

Use three complementary tracks:

1. **Demo and regression tests:** a small, frozen, explicitly simulated PantryPulse network. Preserve the V5 shape: six beneficiaries, one hub, two products, 90 historical local dates and a seven-day forecast horizon. Start from the existing project fixtures rather than depending on a new external import for the presentation.
2. **External food-bank scenarios:** inspect the Synthetic Food Bank Network Dataset first; use the Tehran case-study parameters as a secondary allocation benchmark.
3. **Forecast evaluation:** use a small FreshRetailNet-50K subset, with M5 as a longer-history alternative. Report these as external retail proxy benchmarks, separately from simulated pantry results.

No source inspected establishes a ready-to-import dataset containing all of V5's requested demand, actual received donations, reporting coverage, expiring eligible lots, institutional vulnerability, and frozen operational constraints. Missing pieces need explicit simulation or must remain unavailable.

## What V5 requires from the data

| Requirement | Implication for dataset selection |
|---|---|
| Daily demand by beneficiary/product | Requested quantities are the target. Sales, pickups and distributions may be censored fulfillment; use only through explicit proxy opt-in. |
| Daily donated supply by receiving site/product | Aggregate actual receipts, not offers, pickup jobs or pledges. Preserve individual events and revisions. |
| Missingness and zero distinction | An absent record is not a zero. Receipt-free days require documented reporting completeness to become observed zeros. |
| Lots and dated feasibility | Need receipt/availability date, expiry, quantity, unit and eligibility; a perishable flag alone is insufficient. |
| Research comparison | Need at least two documented simulated institution-level vulnerability attributes in [0,1], plus identical operational inputs for both methods. |
| Reproducibility | Freeze source version/checksum, subset selection, transformations, units, calendar, cutoffs and simulation seed. |

The older DEMO.md describes three sites; V5's six-beneficiary requirement takes precedence. V5 documents a larger fixture on the unmerged forecasting branch; that does not imply it is integrated into main. The local `data/demo/golden-allocation.json` is a small arithmetic fixture, not the complete V5 seed.

## Ranked candidates

### 1. Synthetic Food Bank Network Dataset — strongest external demo candidate

**Verified metadata:** version 1.0.1, October 2, 2026; fully synthetic; modeled on a West Alabama food-bank service area. Contains pantry, donation, inventory-catalog, pickup-history and travel-time tables. Data/documentation: CC BY 4.0; bundled code: MIT. The record describes an unpublished Data Descriptor draft, so do not present it as a peer-reviewed benchmark. [Publisher record and downloads](https://zenodo.org/records/23105385).

**Proposed use:** first inspect `DATA_DICTIONARY.md`, then selectively retrieve `pantries.parquet`, `inventory_catalog.parquet`, `donations.parquet`, `client_pickup_history.parquet`, and pantry-to-pantry travel tables. Avoid the full 4.2 GB file collection. These selected files total roughly 9–10 MB, excluding the location-key table if needed. [File inventory](https://zenodo.org/records/23105385).

**Adaptation:** select a reproducible six-site subset; introduce a clearly simulated hub if needed. Confirm receipt status, destination, timestamps, units and product-level pickup quantities before mapping anything to V5. Treat pickup history as a potential fulfillment proxy, not requested demand. Add missing operational fields explicitly as simulated. Do not carry client-level demographics into the demo or silently convert them into institutional vulnerability scores.

**Evidence limit:** landing page and file list verified; dictionary/raw Parquet retrieval was unsuccessful in this session. Field-level suitability, coverage and joins remain unverified. This is a promising candidate, not a qualified import.

### 2. FreshRetailNet-50K — strongest stockout-aware forecast test

**Verified metadata:** 50,000 store/product series spanning 90 days, with daily normalized sales, hourly sales/stockout annotations and contextual variables. Parquet on Hugging Face; CC BY 4.0. Relevant fields include `store_id`, `product_id`, `dt`, `sale_amount`, `stock_hour6_22_cnt` and `hours_stock_status`. [Official dataset card](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K).

**Proposed use:** select 12 series for a bounded retail forecast benchmark. Evaluate seasonal naive, moving average and actual Chronos inference when qualified. Preserve stockout flags and report errors by stockout cohort.

**Limits:** sales are globally normalized, not physical pantry units or uncensored demand. Use the original numeric scale in external evaluation. Any conversion into meals/bottles creates simulated quantities with a documented scale. Missing demand must not be repaired by an unapproved latent-demand model. Promotions and realized weather are usable future covariates only if their availability at each forecast origin is established. [Field definitions](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K/blob/main/README.md).

### 3. Food bank network design Tehran city — allocation parameter tests

**Verified metadata:** published May 14, 2025, version 1; CC BY 4.0. The repository describes charity demand, food supply and shelf life, distances, transport and handling costs, capacities and budget parameters. [Mendeley dataset](https://data.mendeley.com/datasets/mr9kbjkjk8/1).

**Proposed use:** adapt a small instance to test capacity, scarcity and expiry sensitivity under both allocation methods and both transfer modes.

**Limits:** this is a network-design case study, not a verified daily demand/receipt history. Raw files and parameter units were not inspected. Do not assume shelf-life parameters establish actual lot expiry dates, or that all parameters are observed operational records. Add institutional vulnerability independently as simulated policy inputs. Supplier-related parameters do not resume V5's paused supplier work.

### 4. M5 / Walmart — longer-history forecast alternative

**Verified metadata:** the competition organizers provide sales train/test data, calendar and price information, benchmark material and a competitor guide. The organizer repository links its data folder; Kaggle is another official entry point. [Organizer repository](https://github.com/Mcompetitions/M5-methods), [competition data](https://www.kaggle.com/competitions/m5-forecasting-accuracy/data).

**Proposed use:** select food-product series and evaluate seven-day horizons over more historical origins than the 90-day fixture allows. It can test weekday patterns, intermittent sales and model behavior across varied histories.

**Limits:** retail sales remain a fulfillment proxy. No pantry donations, lots or vulnerability are established. Dataset redistribution terms were not verified; do not assume the organizer code's availability licenses redistribution of sales records. Prefer source-download instructions until the applicable terms are checked. Keep this benchmark separate from the fictional pantry network.

### 5. FoodGo / 412 Food Rescue — small logistics stress fixture

**Verified metadata:** Carnegie Mellon/Mobility21 test data documented by USDOT: 500 donation transport orders and 50 volunteers, including quantities, perishability, coordinates, time windows and vehicle capacities. [USDOT dataset description](https://rosap.ntl.bts.gov/view/dot/56260), [dataset DOI](https://doi.org/10.5281/zenodo.3801643).

**Proposed use:** derive bounded feasibility cases for limited capacity and arrival deadlines. It is a test dataset; do not characterize the orders as verified completed receipts.

**Limits:** no established multi-month daily demand history, exact expiry dates or vulnerability attributes. Full volunteer scheduling is beyond V5's allocation scope. The Zenodo download could not be accessed in this session; raw contents and the original license still need checking before redistribution.

### 6. USDA Food Access Research Atlas — context for vulnerability assumptions

**Verified metadata:** tract-level downloadable CSV/XLSX. The current download page distinguishes **2025 SNAP-authorized Retailer Access Map (SRAM)** from **2019 Large Retailer Access Map (LRAM)**. It also offers older archives. [Official downloads](https://www.ers.usda.gov/data-products/food-access-research-atlas/download-the-data).

**Proposed use:** inspect Alachua County/Florida access indicators to inform plausible ranges and explanatory context for simulated institutional attributes, such as access barriers and economic hardship. Record the exact release and definition. These are proposed proxy concepts, not adopted policy coefficients.

**Limits:** geographic estimates are not measured vulnerability of a particular institution and cannot provide daily meals/bottles demand. SRAM and LRAM use different geographies and input vintages; do not join them on tract IDs without a reviewed crosswalk. Keep demo institution scores simulated as V5 requires. [Definitions and limitations](https://www.ers.usda.gov/data-products/food-access-research-atlas/documentation).

## Sources to defer

| Source | Possible value | Why it is lower priority |
|---|---|---|
| [Feeding America Map the Meal Gap](https://www.feedingamerica.org/research/map-the-meal-gap/by-county) | Local food-insecurity context | Annual estimates; dataset request form rather than a verified immediate bulk download. Not daily institutional demand. |
| [Give Food API](https://www.givefood.org.uk/api/) | Real food-bank item vocabulary and needs lists | Requested item lists are qualitative hints, not quantity histories or received donations. Display rules require attribution, current information and preservation of list order. Poor match for a frozen fictional demo. |
| [UCI Daily Demand Forecasting Orders](https://archive.ics.uci.edu/dataset/409/daily%2Bdemand%2Bforecasting%2Borders) | Tiny CC BY 4.0 logistics smoke dataset | Only 60 observations; weekday/week-of-month fields do not establish a complete dated seven-day calendar. Not food-bank data or a six-site network. |

## Proposed test and demo package

Keep these as distinct named datasets with distinct reports:

| Package | Contents and intended claim |
|---|---|
| `pantrypulse-demo-v1` | Six fictional beneficiaries, one hub, meals and bottles; 90 history dates, seven future dates; 12 demand and 14 donation series. Deterministic system/demo evidence only. |
| `external-foodbank-v1` | A qualified subset of the synthetic food-bank source, preserving source units and provenance. External synthetic scenario evidence. |
| `external-retail-v1` | FreshRetailNet subset; original dates/scale and stockout flags. Retail proxy forecast evidence, not measured pantry demand accuracy. |
| `allocation-edge-cases-v1` | Small authored instances with exact expected feasibility/arithmetic. Correctness evidence, not empirical performance. |

For the demo, author separate cases for scarcity with different vulnerability, adequate supply, a protected pantry surplus, expiring stock, late arrivals, zero capacity and disabled routes. Include one disruption that creates a new frozen scenario. Compare CLASSICAL_GP and EGP_PI_INSPIRED on the same snapshot/mode; compare modes in separate scenarios. Report actual tradeoffs even when a research allocation leaves more total units unmet or costs more. Do not guarantee a preferred method wins.

For imports/history, include true zeros, unknown days, same-day distinct receipts, duplicate IDs and late corrections. Use explicit simulated requested demand and receipts in the main seed. If adapting external sales or pickups, retain proxy labels and require the relevant opt-ins. Receipt-free synthetic days may be zero only under a declared complete synthetic reporting process. Historical imports must not post current inventory.

For forecasting, predeclare series and chronological origins; keep a final untouched seven-day holdout where history permits. Fit any scaling/selection only on the training period. Report MAE, bias and WAPE separately by target, product/unit, basis and actual provider, including failures and coverage. Report WAPE as unavailable for zero-total actuals. Retail and pantry metrics must remain separate. The external sources do not automatically resolve V5's OPEN-18 evaluation policy.

Every package should have a manifest containing source URL/DOI, version/revision, retrieval time, checksum, source license/attribution, selected IDs/date range, exact transformations, unit mapping, timezone/date shifts, source-versus-simulated fields, seed, data/knowledge cutoffs and output hash. An illustrative re-date or rescale creates a derived simulated dataset; preserve the source unchanged for evaluation.

## Next implementation order

1. Inspect the food-bank dictionary and a small raw sample; confirm units, event status and time coverage before selecting it.
2. Complete the local deterministic V5 fixture and exact arithmetic cases, using final reviewed contracts. Do not merge the experimental forecasting branch as part of data sourcing.
3. Prepare a bounded FreshRetailNet benchmark with explicit proxy handling and chronological evaluation.
4. Add the external food-bank subset if its schema passes inspection; retain the local fixture as the rehearsal fallback.

This research inspected primary-source documentation and metadata. It did not download full datasets, execute forecasts, qualify licenses beyond the stated source labels, or verify import compatibility.
