# PantryPulse acceptance and evidence map

Updated October 25, 2026 against main `647f6a8`. [SPEC-V5 §16](SPEC-V5.md#16-validation-and-release-acceptance) owns acceptance IDs. This page replaces the original three-site/six-series V4 suggestion table. Source implementation is not automatically a new PASS or a release qualification.

| Acceptance area | Implemented source and existing evidence | Remaining boundary |
| --- | --- | --- |
| Foundation/contracts/migrations | Locked tools, generated schemas/types, single `ppvp_0007` head, source-bound Linux/PostgreSQL evidence | Current exact-SHA full gate and intended runtime |
| History/stock/imports | Revision/zero/null/cutoff handling, audited transactions, atomic JSON/CSV import, presenter Data input | No hidden stock creation; broader production management remains separate |
| Forecast/publication | Baseline and opt-in model contracts, actual provider, immutable complete/incomplete publication, reuse/fallback | Complete Chronos planning scope and pantry/donation accuracy/calibration unqualified |
| Frozen scenarios/physical feasibility | Explicit mode, source versions, donor protection, inclusive expiry/FEFO, capacities, seven dates | Numeric/shape limits still enforced, even within the eight-product cap |
| Research/paired results | Native classical and research-inspired methods, same frozen inputs/settings, independent replay and partial outcomes | Simulated provisional policy, no full-paper or real-world outcome claim |
| Durable jobs/security | One-active/two-waiting, actual Linux fences/cancel/retry, presenter tenant/CSRF/proxy, limited visitor saved reads | Broader roles/access and public hosting are separate |
| UI journey | Overview/Data Explorer/Inputs/Recommendations/Scenario Lab/Methodology and current browser specs | Human review and exact target/date/source evidence; a mock-only test is not a persisted journey |
| Supplier proposals | Accepted scope remains paused | Explicit decisions/resumption, implementation and tests |
| Release/operations | Seed/migrations/limits/recovery procedures exist | Five rehearsals, manifest/rollback/backup, actual target smoke and disclosures |

## Current gates

Local quality-runner quick/full/e2e groups are executable; inspect `.claude/quality-gate.json` and [testing](../testing/README.md) for the real prerequisites. Native Windows cannot qualify Linux process containment. CI `verify` is the two-minute static/unit merge check; CI `full` separately runs backend/PostgreSQL/contracts/build/connected Chromium and rejects skipped backend/browser checks. A green verify does not replace full, visual review or release rehearsals.

Evidence needs an acceptance ID, immutable code/config/input identity, environment/dataset, command, timestamp, observed result and artifact. Retain dated reports unchanged in meaning. The [documentation audit](DOCUMENTATION-AUDIT-2026-10-25.md) validates documentation, not the full product. Do not reuse the original V4 FR numbering or unchecked historical task rows as current completion metrics.
