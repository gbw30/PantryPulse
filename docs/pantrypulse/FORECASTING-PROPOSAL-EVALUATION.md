# Forecasting Proposal: Consolidated Evaluation

Design review, October 24, 2026. This note records proposed forecasting tables and service contracts discussed during planning; it is not an implemented schema or a replacement for V4. The table names below describe candidate structures. Reconcile them with the authoritative specification before implementation.

The proposal’s overall structure is sound. **Keep the core tables and service contracts. Correct the claim about the model’s native input format, and specify the missing data rules before implementation.**

**Correct — keep these parts:**

| Proposal element | Why it is correct |
|---|---|
| Separate `demand_observations` and `donation_observations` | Demand and donated supply are different forecasting targets. |
| Separate requested, fulfilled, and unmet demand | Units distributed do not necessarily represent total need. |
| Nullable requested/unmet quantities | Unknown demand must remain distinguishable from zero demand. |
| Site/product/date identifiers on observations | These identify the daily series being forecast. |
| Provenance and historical version information | The backend needs to distinguish observed, proxy, and simulated inputs and track changes. |
| Separate `forecast_runs` and `forecast_points` | Execution metadata and numerical predictions serve different purposes. |
| Model name/version, cutoff, horizon, and execution status | These are essential for explaining and reproducing forecasts. |
| `target_type = DEMAND \| DONATION` on forecast points | This clearly identifies what a prediction represents. |
| Central predictions with nullable lower/upper quantiles | Some forecasting methods can supply uncertainty estimates; others cannot. |
| `interval_method` | Consumers must know how uncertainty values were produced. |
| Application-level `ForecastInput` and `ForecastOutput` | A common interface allows the backend to support multiple forecasting methods. |
| Fallback metadata and warnings in outputs | The API must reveal which method actually produced a result. |
| The main relational structure | Organizations own sites and runs; observations and predictions reference sites and products. |

**Completely incorrect — reject this interpretation:**

| Statement or interpretation | Correction |
|---|---|
| “`ForecastInput` is the format Chronos-2 itself expects.” | It is a proposed **PantryPulse forecasting-service contract**. A model adapter must convert it into Chronos-2’s supported input format. |

Chronos-2’s documented pandas interface accepts historical tabular data, optional future covariates, and prediction parameters. Fields such as `allow_fallback`, `provenance`, and `preprocessing_config` are responsibilities of the backend service. [Pinned interface](https://github.com/amazon-science/chronos-forecasting/blob/v2.3.2/src/chronos/chronos2/pipeline.py).

Use “forecasting service” for the application contract and “model adapter” for the conversion to the Chronos interface.

**None of the proposed tables is fundamentally incorrect and needs wholesale rejection.** The remaining issues are incomplete definitions or missing guarantees.

**Improve or specify before implementation:**

| Area | What needs clarification or improvement | Recommended decision |
|---|---|---|
| Donation location | `donor_id / site_id` combines the supplier and receiving location. | Use separate `donor_id` and `receiving_site_id` fields. Require a receiving site for site-based forecasting. |
| Donation target | `observed_units` does not identify exactly what was measured. | Define the forecast target explicitly; preferably actual donated units received, with a name such as `received_units`. |
| Donation row meaning | One row could mean one delivery or one daily total. | Choose event-level records or daily aggregates, then define the appropriate uniqueness rule. |
| Concrete SQL types | `Metadata`, “Version identifier,” and several donation fields are placeholders. | Specify actual types, nullability, defaults, foreign keys, and permitted values. |
| Provenance | `provenance` and `source_type` overlap without a shared definition. | Use a consistent source classification plus structured JSONB details where needed. |
| Demand consistency | Invalid combinations of requested, fulfilled, and unmet quantities are currently possible. | Require nonnegative values; enforce `requested = fulfilled + unmet` when all are supplied. |
| Unknown requested demand | No policy explains what happens when requested demand is missing. | Mark it unavailable or apply an explicitly permitted, labeled proxy policy. |
| Observation uniqueness | Duplicate rows could be selected or counted twice. | Define uniqueness within the chosen dataset/version. |
| Historical version selection | `source_version` does not explain which version a run selects. | Define how one authoritative observation per series/day enters a snapshot. |
| Reproducibility | A cutoff alone cannot identify the exact records used. | Store an immutable input snapshot/reference, input hash, and preprocessing configuration. |
| Per-series model metadata | One run may use Chronos for some series and fallback for others. | Persist actual model, fallback, warnings, errors, and availability per series. A separate table is one option. |
| Job lifecycle | Run status exists, but execution timing and failure details are incomplete. | Add start/completion timestamps, structured errors, and rules for partially successful runs. |
| `DailyObservation` | The input contract references an undefined type. | Define its date, numerical target, missing-value representation, and relevant quality information. |
| Missing dates | The treatment of gaps is unspecified. | Preserve a daily calendar and apply a documented missing-data policy; never silently turn missing observations into zero. |
| Future covariates | Their types, dates, and availability rules are unspecified. | Define named, dated features and require that they were known or forecast at prediction time. |
| Preprocessing | `preprocessing_config` could allow inconsistent transformations. | Define supported options and save the exact configuration used. |
| Output availability | `ForecastOutput` cannot explicitly describe an unavailable or failed series. | Add a series status and structured failure/insufficient-data information. |
| Output identity | Outputs do not identify their execution directly. | Include `run_id`; include a series-result identifier if introducing per-series persistence. |
| Forecast point meaning | `p50` needs an exact interpretation. | Define it as the median; introduce a separate field if another point estimate is needed. |
| Forecast validation | Bounds, ordering, uniqueness, and dates are unspecified. | Require finite, nonnegative values; ordered quantiles where present; unique series/day outputs; correct horizon dates. |
| Baseline uncertainty | A baseline may not provide meaningful quantiles. | Permit null bounds with an explicit `NONE` interval method. |
| Organization boundaries | Foreign keys alone may allow a run to reference another organization’s site. | Enforce consistent organization ownership across selected inputs and outputs. |
| Naming | Names such as `horizon` and `data_cutoff` leave units or meaning implicit. | Prefer consistent names such as `horizon_days` and `data_cutoff_date`. |

The highest-priority decisions are **what donation quantity is forecast, what one observation row represents, how exact inputs are frozen, and how each series reports its actual model and outcome**. Resolve those first; the rest can then be expressed as concrete database constraints and typed contracts.
