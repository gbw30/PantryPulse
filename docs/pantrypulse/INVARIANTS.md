# PantryPulse invariants

> **Current authority:** [Project specification V5](SPEC-V5.md). Compatible invariants remain required. Fixed three-site/six-series examples are historical; V5 defines the expanded scope, both explicit transfer modes and current evidence.

Each invariant needs a meaningful executable assertion. A screenshot of correct-looking numbers is insufficient.

| ID | Invariant | Minimum falsifying case |
|---|---|---|
| INV-01 | Physical stock is a nonnegative integer per site/category/lot | adjustment below zero rejected |
| INV-02 | A transfer preserves total physical stock per category on completion | paired debit/credit; no creation or double completion |
| INV-03 | Transfer quantity <= eligible unreserved donor budget | expiry, reserve and previously reserved stock |
| INV-04 | No self-transfer, wrong-category movement or unavailable route | closed route and mixed units |
| INV-05 | Receiving and total handling capacity hold | exact-bound and bound+1 fixtures |
| INV-06 | Transfers arrive before the need they claim to reduce | late arrival cannot fix yesterday's shortage |
| INV-07 | No relay inventory or double-counted arrivals | inbound transfer not spent again in same batch |
| INV-08 | Before/after use identical snapshot, category and horizon | changed stock cannot silently enter one side |
| INV-09 | Unmet demand is daily lost demand, not summed negative cumulative balances | 40 stock; 50 then 40 demand => 50 unmet |
| INV-10 | Historical gaps remain distinct from zero | one missing date; all-zero complete week |
| INV-11 | Forecast context never includes target horizon observations | perturb held-out future values; fit unchanged |
| INV-12 | Six eligible series get seven dated points or explicit insufficiency | short and complete histories together |
| INV-13 | Metadata identifies actual provider, fallback and source | Chronos exception produces labeled baseline |
| INV-14 | Quantiles are ordered, nullable and honestly interpreted | absent baseline interval never drawn as calibrated |
| INV-15 | Scenarios preserve source history/forecast bytes | baseline hash unchanged after replan |
| INV-16 | Stale inventory versions cannot approve/mutate | two requests with same expected version |
| INV-17 | Native solver status is retained | FEASIBLE/UNKNOWN/MODEL_INVALID test doubles |
| INV-18 | Short supply remains explicit unmet slack | zero-stock case is useful feasible partial plan |
| INV-19 | Saved planning inputs reproduce feasibility/objectives | replay snapshot, not current DB state |
| INV-20 | Demo reset affects only demo data and is authorized | non-demo org reset rejected, data unchanged |
| INV-21 | Projection risk is not a fabricated probability | upper-quantile scenario has no percentage risk label |
| INV-22 | P1 reservation and completion are separate/idempotent | competing approvals; repeated completion |
| INV-23 | Explicit frozen transfer mode is independent of method | missing/invalid mode rejected; new scenario for changed mode; both methods tested in both modes |
| INV-24 | Mode constrains routes and dated surplus | HUB_ONLY rejects pantry origin; HUB_AND_PANTRY rejects donor harm, late/expired lots and same-batch forwarding |
| INV-25 | Demand forecasts represent need separately from stock | changed inventory changes shortage projection, never saved demand forecast |

The following historical pantry-sharing fixture applies only to `HUB_AND_PANTRY`; it is not evidence that either mode is implemented. Golden allocation fixture data/demo/golden-allocation.json is independently auditable. With two days of meals, Central sends 40 to North, total unmet decreases 50 to 10, movement cost is 40, Central ends at 100 and South at 10. Demand surge 1.25, with per-day ceiling, makes North demand [63,50], unmet 73 before and 33 after. These are test expectations for that exact fixture, not real-world results or required numbers for every seeded run.

Test at least zero demand, all-zero stock, no routes, expiry on boundary, insufficient history, missing date, duplicate import, stale version, capacity zero, equal objective ties, a timeout and a malformed scenario. Property-style random feasible inputs should assert conservation and bounds; compare tiny instances against exhaustive enumeration to catch an incorrect objective or feasible-region model. A verifier must not simply re-use the solver's own checker as its only oracle.
