# ADR 0003: Offline forecasting core and shared-contract boundary

> **Current authority:** [Project specification V5](../pantrypulse/SPEC-V5.md). V5 supersedes conflicting V4-era instructions. BD-41 requires explicit `HUB_ONLY` or `HUB_AND_PANTRY` with no default in the full operational scenario; the forecast-only handoff does not select topology. Experimental policies and live integration gates remain open.

Date: 2026-10-24. Accepted scope: provider-independent implementation only.

The forecasting implementation plan identifies open SQL, public API/job, provider
and operational policy contracts. The user selected **implement the forecasting
core; retain shared-contract gates**. Implement pure modules under ADR 0001's
existing Python service boundaries; do not introduce a second backend, queue,
frontend calculation or SQLite substitute.

Internal Pydantic contracts use `experimental-v1` versions and immutable nested
tuples. Preparation freezes the exact selected historical fact content and source
references, separate data/knowledge cutoffs, scope, units, calendars and policies.
Canonical SHA-256 identity excludes execution IDs/timestamps. Receipt aggregation
uses complete visible event revisions, keeping receiving sites and donors distinct.
Unknown receipt days require reporting coverage to become observed zeros.

Forecast policies require an explicit sparse window/minimum. The demo selects the
plan's proposed 14-calendar-day/three-observation rule. Mixed requested/proxy history
requires its own explicit opt-in in addition to fulfilled-proxy permission. These
are experimental configurations, not resolutions of OPEN-12–18. Internal forecast
quantities are finite nonnegative numbers; they do not settle SQL count precision
or numeric bounds. Historical demand consistency is checked without deriving
unknown components. Invalid predictions are rejected, never clipped or repaired.

The pure service reports `ready_for_publication` after complete required numerical
coverage. Persisted `planning_ready` remains the responsibility of a future atomic
publisher; pure computation cannot assert committed results. Exact reuse eligibility
is a pure check; PostgreSQL must eventually enforce committed-only lookup and atomic
admission/deduplication. Explicit recomputation makes new result IDs.

The planning handoff freezes exact forecast inputs/results, explicit scope and daily
rounding/buffer choices. It is not the complete operational scenario schema. A pure
projection accepts only supplied versioned lots and explicitly confirmed arrivals;
it uses daily lost sales, eligibility and local FEFO/expiry. The experimental event
order is arrivals, expiry, service; this does not close OPEN-19–22. Unknown expiration
is permitted by the pure experiment and must be resolved by operational policy before
live planning. No receipt forecasts or unapproved supplier proposals enter stock.

Chronos remains a fail-closed adapter boundary: the lockfile's 2.3.2 package alone
does not qualify a checkpoint, native missing handling, resources or inference. No
model download, hosting setup, complex solver implementation, public route, migration
or generated TypeScript contract is introduced. The existing health endpoint remains
process-only. Durable supervision/admission/deadlines remain a mandatory later gate.

See [implementation/evidence](../pantrypulse/forecasting/IMPLEMENTATION.md) for commands,
coverage and the remaining integration work.
