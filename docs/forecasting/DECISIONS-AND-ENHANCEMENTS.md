# Open decisions and work beyond the current core

**Historical October 24 decision/planning notes.** Current implementation and accepted runtime changes are indexed in [CURRENT-STATUS.md](../pantrypulse/CURRENT-STATUS.md) and SPEC-V5. Old implementation-absence statements do not reopen completed API/job/OR/proxy/CI work; genuinely unresolved policy and optional improvements remain subordinate to the current specification.


> **Current authority:** [Project specification V5](../pantrypulse/SPEC-V5.md). V5 supersedes conflicting V4-era instructions. BD-41 requires explicit `HUB_ONLY` or `HUB_AND_PANTRY` with no default in the full operational scenario; the forecast-only handoff does not select topology. Experimental policies and live integration gates remain open.

Updated: October 24, 2026 (America/New_York).

This document preserves the existing decision tracker. It proposes implementation
work and review questions; it does not select unanswered product policies or change
accepted BD decisions. See the [completion roadmap](MVP-COMPLETION.md) for dependencies
and acceptance checks.

## Decisions required before dependent work

| Existing tracker | What must be settled | What it unlocks |
|---|---|---|
| OPEN-04–08 | Quantity precision/bounds, ownership/FKs, timezone/day rules, authoritative revision/coverage selection, receipt correction semantics | History/receipt migrations and repository adapters |
| OPEN-09–11 | Transaction/ledger authority, locking/version scope, idempotency, expected-supply reconciliation, and first-release physical-count/discrepancy/correction coverage | Exactly-once receipt posting, safe adjustments and inventory reads |
| OPEN-12–14 | Public series outcomes/readiness, sparse eligibility, mixed proxy policy, failure categories, central/quantile fields and permitted postprocessing | Public forecast contracts and durable result publication |
| OPEN-15 | Typed covariates and availability, actual pinned provider API/checkpoint and grouping/settings | Qualified Chronos adapter; future feature support |
| OPEN-16–18 | Explicit buffer policy, exact reuse/dedup/retention, evaluation windows/minimum evidence and selection rules | Conservative planning, concurrent reuse and defensible model choice |
| OPEN-19–22 | Complete JSONB snapshot/hash, staleness, daily event order, missing expiry, donor protection, routes/ETA and shared capacity | Frozen scenarios and one shared feasible region |
| OPEN-23–25 | Complete objective/penalty/group policy, numerical bounds/verification, immutable policy/attribute versions and edit permissions | Both correctly labeled allocation methods and reproducible policy changes |
| OPEN-29–33 | Wire/error catalog, lifecycle/attempt ownership and recovery, presenter sessions/CSRF, reset/retention, probes/log/audit contracts | Authorized APIs, durable execution and diagnosable operations |
| OPEN-34–36 | Final fixture/evidence definitions, effective process limits/termination and benchmark protocol, migrations/generated-contract workflow | Repeatable full gates and a reviewable release |

Work through these by dependency; a database field needs its own decisions resolved,
not every unrelated OPEN topic. Update the existing
[checkpoint](../pantrypulse/BACKEND-DESIGN-CHECKPOINT.md) and
[backend specification](../pantrypulse/BACKEND-SPEC.md) together when a choice is accepted.

The current core's highest-visible-revision rule, 14-day/three-sample demo policy,
mixed-proxy switch, buffer without a selected public upper bound and arrivals/expiry/service
ordering are experimental configurations. Review them before public adoption. Their
presence in code is not evidence that the corresponding OPEN decisions were accepted.

## Paused or deferred decisions that still affect completion

- **OPEN-03/26–28:** supplier planning remains paused. Accepted draft-proposal scope
  includes after-arrival coverage and one coordinated simulated budget. Offer mixing,
  basket terms, coverage/currency/defaults and priority choices remain unselected.
  Supplier proposals cannot be marked complete or quietly relabeled P1.
- **OPEN-02:** numeric benefit attribution per transfer remains deferred. Choose the
  required explanation approach before promising per-transfer causal benefit numbers.
- **Model/hosting setup:** still paused. A later explicit resumption is needed for
  actual Chronos setup or hosted release work. An offline baseline is already useful
  for integration and does not require either setup task to progress.
- **OPEN-01:** resolved by BD-41. Support both explicit modes: `HUB_ONLY` allows hub origins; `HUB_AND_PANTRY` also allows eligible beneficiary origins subject to protection/feasibility. The full scenario requires a mode with no default, independently of allocation method.

## Useful work that can proceed within existing boundaries

These are candidate next tasks, not claims they were implemented during this docs change.

| Work item | Bounded deliverable | Evidence |
|---|---|---|
| Contract review packet | Small valid/invalid input/output examples and a policy decision list using the current core | Shared review; no production schema freeze by implication |
| Evaluation review | Explicit validation/final-holdout protocol; representative seasonal, intermittent, all-zero, proxy and gappy cases | Paired scored-set counts, failure coverage and per-series/target/product metrics |
| Core adversarial review | Independently inspect preparation, output, reuse and handoff invariants | Reproduction cases tied to F-01–17; fix demonstrated defects |
| Operational fixture design | Add planned lot/expiry/route/capacity/attribute cases to the expanded history specification | Hand-derived outcomes and source/provenance manifest; no live DB reset |
| Research validation | Paper mapping, independent tiny enumeration, AP/RP boundary/ablation cases and integer bounds | Reviewable mathematical evidence before complex solver implementation |
| Frontend interaction design | Saved-result layouts, statuses, comparison semantics and accessibility behavior | Reviewed design mapped to future API contracts; illustrative data visibly labeled |
| Gate reconciliation | Identify missing commands/tests and old acceptance/demo assumptions | Concrete checklist using V4/BD requirements; no disabled required check |

Schema-dependent persistence/API changes still wait for their specific decisions.
Preparing mocks, examples or a UI prototype cannot satisfy live acceptance.

## Optional improvements after the mandatory core

These must not displace PostgreSQL integrity, durable jobs, the paired research
comparison, import/correction/replay, or the presenter workflow.

| Improvement | Prerequisite | How to judge value |
|---|---|---|
| Calibrated forecast intervals | Representative held-out data and an approved statistical protocol | Empirical coverage/width with sample counts and comparable baseline evidence |
| Additional covariates | Approved typed/versioned catalog and feature availability rules | Chronological improvement without future leakage |
| Stronger sparse/intermittent baselines | Agreed target basis and evaluation protocol | Better paired accuracy/coverage across representative series; truthful method labels |
| Learned ensembles or finer-grained automatic selection | Agreed core provider-selection rules, sufficient validation evidence and a separate untouched later test period | Stable improvement; selection fitted before final evaluation and versioned for replay |
| Broader stress/performance experiments | Correct bounded live core and reproducible measurement | Recorded scope/hardware/version, throughput/latency/resources and disclosed failures |
| Supplemental no-action/greedy comparisons | Both primary methods and the common checker already work | Same frozen inputs, feasible outputs and clearer explanations; reconcile legacy requirements first |
| Production reservation/completion | Explicit P1 scope and transaction design | Competing approvals, atomic reservations, idempotent paired movements and conservation |
| Real integrations, notifications, maps or richer visualization | Explicit later scope and operational requirements | Measured user value after the core workflow is reliable |

Actual Chronos qualification remains its own planned capability, not something these
optional improvements replace. Advanced ensembles, polished animation or added metrics
cannot establish that a missing provider, job system or research method works.
