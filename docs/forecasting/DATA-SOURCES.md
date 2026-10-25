# Forecast evaluation data sources

Research date: October 25, 2026. Owner: @GestebanFalcon.

This document records the FC-02/03 source checkpoint. Subsequent validation and
one serialized FC-07 final opening are in [the qualification dossier](QUALIFICATION.md).
Statements below that final values were unread describe source preparation;
the final week has now been evaluated and is no longer an untouched tuning holdout.

Execution: [FC-02 / #81](https://github.com/gbw30/PantryPulse/issues/81), then
[FC-03 / #82](https://github.com/gbw30/PantryPulse/issues/82), under existing
[#38](https://github.com/gbw30/PantryPulse/issues/38).
See the [execution plan](EXECUTION-PLAN.md) for milestones and evaluation rules.

## Current conclusion

No public source with verified daily site/product requested-demand **and** actual
donation histories was qualified in this search. Partner exports remain the best
target fit, with access unconfirmed. **FreshRetailNet-50K is now sample/file/schema
qualified for a separate normalized observed-retail-sales benchmark.** The official
pinned files were downloaded and checksum-verified; the 100-series pilot and four
validation folds are prepared. This does not qualify latent demand, pantry need,
donation forecasts or model accuracy. Final holdout values remain sealed.

## Sources inspected or identified

| Source | What was verified | Fit and next action |
|---|---|---|
| Authorized direct pantry/food-bank export | Required fields specified below; no export/access established | Preferred for demand/donation qualification. Record missing demand, unserved requests, coverage and unit definitions; fulfilled quantity alone is censored need |
| [FreshRetailNet-50K, official dataset](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K) | Official raw-file hashes and schema verified; 50,000 matching store/product series with 90 train days and seven later eval days; sampled normalized sales and stockout masks inspected; CC BY 4.0 attribution recorded | Accepted for the retail observed-sales proxy only; the final eval file was read only for IDs/dates/schema, not values |
| [FreshRetailNet paper](https://arxiv.org/abs/2505.16319) and [official code](https://github.com/Dingdong-Inc/frn-50k-baseline) | Primary methodology describes stockout-censored sales and latent demand recovery | Use to interpret fields and evaluation; recovered quantities are estimates. Do not assume its covariate protocol is valid for our as-of use |
| [Give Food API](https://www.givefood.org.uk/api/) | Official API publishes food-bank locations and requested donation-item lists | Context/taxonomy lead; not a verified daily quantitative target. Do not turn a needs-list entry into a requested unit count |
| [NYC Community Food Connection quarterly report](https://catalog.data.gov/dataset/community-food-connection-quarterly-report) | Public catalog describes individuals served at pantries and meals served at kitchens, reported quarterly | Useful aggregate context; unsuitable as daily product-level forecast truth. Do not disaggregate quarters into fabricated daily observations |
| [FoodGo / 412 Food Rescue supporting dataset](https://rosap.ntl.bts.gov/view/dot/56260) | Official DOT catalog describes 500 pickup/delivery orders and 50 volunteers, with quantities, coordinates and availability windows | Routing/operational fixture lead. A repeated daily demand/donation time series was not established; do not treat order time windows as longitudinal history |
| [openICPSR Food Banks deposit](https://doi.org/10.3886/E203361V1) | Search index identifies a donation-data codebook; direct deposit/raw access returned 403 during research | Unverified lead only. Need raw files, dictionary, chronology, unit/target semantics and terms before recommending it |
| Existing [PantryPulse fixture](../../data/demo/forecasting-v1.json) | Deterministic simulated 90-day history, 26 demand/donation series and four origins | Keep as correctness/adversarial evidence. Expand synthetic regimes where useful; do not use it alone to claim domain accuracy |

FreshRetailNet's complete pinned raw files were downloaded and hashed; train values
were decoded only for the selected cohort, while eval values remain unread. Other
sources were checked at metadata/preview level and remain unqualified without
suitable samples, units and chronology.
The older issue text references `DATASET-RESEARCH.md`; no file with that name was
found in the current checkout. This document supplies current, linked research
without treating that missing reference as an accepted source decision.

## FreshRetailNet adaptation proposal

The official card defines `sale_amount` and `hours_sale` as globally normalized
sales quantities, and supplies date, store/product identifiers and stockout
fields. Therefore retain a named normalized retail-sales unit. An inverse
conversion to PantryPulse meals/bottles has not been established. Its commercial,
perishable-product context also differs from pantry need and donated arrivals.
[Field definitions and terms](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K).

This is our proposed adaptation, not an upstream claim of pantry suitability:

- Preserve store/product keys, daily dates, native values, masks and source
  classification in an offline benchmark envelope. Do not create fictional
  beneficiary identities or fill unsupported donation scope to satisfy production
  job validation. Reuse provider/preparation/metric primitives where semantically
  valid and keep any source-specific envelope narrowly defined.
- Start with no covariates and no learned demand recovery. Score observed-sales
  forecasts with explicit censoring labels; report an additional uncensored
  diagnostic and its coverage. That diagnostic is conditional on realized stock
  availability and must not become a claim of accuracy on all future demand.
- Stockout-day observed sales are not latent-demand truth. Excluding such days
  does not make the remaining sample representative. Any later recovery experiment
  uses training-only fitting, separate estimated labels and explicit sensitivity
  analysis, without silently changing production history preparation.
- Preserve training/validation/final-holdout separation. Select sparse/high-volume
  cohorts using training history, not final-period values or availability. Pin
  upstream file revisions/checksums and verify real split lengths before use.
- Exclude realized future weather and stockout status from model inputs. Future
  promotion plans require evidence they were known at the origin; calendar flags
  require reviewed interpretation. Cross-series grouping must not leak future
  target values or mix independent access domains.
- Verify whether the exact Chronos checkpoint training corpus includes the chosen
  dataset, subsets or near duplicates. The [model card](https://huggingface.co/amazon/chronos-2)
  and [training-data report](https://arxiv.org/abs/2510.15821) are the starting
  evidence; an absent name alone does not prove non-contamination. Record unknowns.
- Short histories can test weekly patterns and censoring but do not establish
  annual seasonality. Keep retail findings, synthetic pantry findings and any
  eventual direct-pantry results in separate reports.

## Direct-source export specification

Request/accept institution-level anonymized records, not client personal data:

| Field group | Required meaning |
|---|---|
| Identity | Stable source/site/product IDs, category, explicit quantity unit and conversions |
| Time | Local service/receipt date, timezone, opening/closure calendar; observation span |
| Demand | Requested, fulfilled and unmet quantities as separate nullable fields; known stockouts/capacity limits and denominator definitions |
| Donations | Actual receipt event/line quantities and dates, not offered/predicted/confirmed future supply |
| Coverage | Complete reporting versus missing records; genuine zero activity must be distinguishable from no report |
| Provenance | Source revision/recorded-at/correction timestamps when available; otherwise explicitly retrospective data |
| Terms | Access permission, redistribution/attribution requirements and an approved anonymized unit of publication |

Prefer six months or more and ideally a year or more, while accepting a documented
shorter-history pilot for limited claims. Specify the intended seven-day horizon
and which sites/products have enough history before using outcomes to select
cohorts. Do not relabel visits/families served as product quantities without a
separate documented conversion and target definition.

## Source qualification deliverable

FC-02 records an accept/reject/unknown decision for each candidate, an accessible
raw-sample/schema report, provenance/terms, target/censoring/unit mappings and a
reasoned source choice. FC-03 provides reproducible acquisition/conversion,
deterministic cohorts and immutable split manifests. Raw bulk data stay outside
Git; only permitted tiny examples, checksums, transformations and attribution are
versioned. Explicit FreshRetailNet acquisition/conversion has now been performed;
no live database import, model scoring or partner outreach was performed by the
data implementation.

## Executed FC-02 / FC-03 checkpoint

Source revision: `c374e85975c82816c495acfa904cc55ab14a47d3`.
The [source pin](../../data/benchmarks/forecasting/freshretailnet50k-source-v1.json)
records complete SHA-256/size identities. Actual training dates are March 28–June
25, 2024, with final dates June 26–July 2. Every source series has 90 unique daily
train records and seven unique later eval records; the two splits have matching
50,000 store/product identities.

The stable seed-20261025 ID sample contains 100 series / 9,000 training records:
504 observed zero values, no missing training rows/values, and 3,943 days with
positive upstream daytime stockout counts. Sixty-eight sampled series contain
zeros; all 100 contain a censored day. These are pilot-specific descriptive
counts, not population estimates. Missingness remains covered by synthetic
adversarial tests; no source gaps were fabricated to create that cohort.

Reproducible commands and loader interfaces are in
[the tooling guide](../../scripts/forecasting/README.md). The ordinary prepared
dataset at `/tmp/pantrypulse-forecast-pilot-v1/manifest.json` contains training
values only. The [versioned pilot manifest](../../data/benchmarks/forecasting/freshretailnet50k-pilot-v1.manifest.json)
is a small audit record; its large sibling training artifact remains in the
external output directory. [Three attributed training examples](../../data/benchmarks/forecasting/freshretailnet50k-tiny-training-sample.json)
are checked in for schema inspection, not accuracy evaluation.

Manifest SHA-256: `012d609c4760d62063f7d3a8018e95f758c380cf8e5c0613405e67cba595ba19`.
Training artifact SHA-256:
`71b9aa7b90832b58128fa0f391d9854e31ffd1debc862abe377207502a6bcf41`.
The [machine-readable qualification record](evidence/data-qualification-v1.json)
contains source layout, provenance, cohort counts, hashes and remaining gaps.

Checks: 25 focused envelope/temporal/hash tests passed; Ruff check/format and
whitespace checks passed. Actual conversion used isolated tooling Python 3.13.5
with Arrow 22.0.0; the dependency-free API envelope/tests ran on Python 3.12.13.
No model forecasts or accuracy metrics were computed, and no eval target/mask/
covariate values were decoded. FC-07 must explicitly open final truth after
freezing validation/model choices.
