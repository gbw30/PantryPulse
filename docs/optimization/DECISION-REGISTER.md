# Provisional OR decision register

Draft 1.1 / policy or-policy-v1 / schema or-input-v1 and or-scenario-v1. Owner: implementation lead; review state: provisional, adopted October 24, 2026. These choices do not resolve accepted backend OPEN records.

## OR-DEC-001

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 06/21.

Choice: One operational timezone per network in v1; explicit IANA zone; seven local dates; arrivals then expiry then batch dispatch on day 1 then daily service. Expiry D prohibits use on D; unknown expiry unavailable

Rationale and revisit trigger: Clear executable clock. Revisit for mixed-zone networks or time-of-day receipt/expiry modeling

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-001`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-002

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 19/21/22.

Choice: One dispatch batch before day-1 service; route ETA is an explicit integer day offset 0–2. Allocation window H is explicitly 1–3 days. No silent window or transfer-mode default

Rationale and revisit trigger: Bounded scheduling with actual late-arrival accounting; revisit for multiple dispatches

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-002`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-003

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 21.

Choice: A sending beneficiary must cover its full seven-day demand and explicit end-of-day reserve without any proposed inbound transfers. No-action already failing protection makes it ineligible to donate that product

Rationale and revisit trigger: Conservative donor protection; revisit for authorized shortage-sharing or shorter reserve policy

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-003`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-004

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 21/22.

Choice: Fixed loading order per source/product: descending ETA, then destination UUID. Each route packs eligible lots by expiry, availability, original lot UUID. Local service uses the same deterministic FEFO key

Rationale and revisit trigger: Exact hard FEFO with a tractable model. Loading order restricts lot assignments and can affect outcomes; revisit with alternative-order sensitivity or joint dispatch scheduling

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-004`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-005

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 04/09/21.

Choice: Optimize free stock only. Freeze disjoint physically on-hand usable, reservation, fixed-commitment and held quantities; protected quantities cannot fund new shipments or local free service. Future confirmed arrivals serve locally but cannot be exported in this batch

Rationale and revisit trigger: Avoid double counting and inventing future dispatchable stock. Revisit with complete commitment event simulation

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-005`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-006

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 23/25.

Choice: Research defaults: lambda=1, beta=1/2, two attribute coefficients 1/2 each, AP threshold 3/4, RP threshold 1/4, allowed AP and RP shares 1/4 each, both penalties 1

Rationale and revisit trigger: Transparent demonstrable baseline; all are provisional and sensitivity-tested, not values attributed to the paper

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-006`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-007

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 23/24.

Choice: One RP group per product, all included positive-target beneficiaries including self; each active group has at least two members. AP/RP excess averaged over active products; W remains a sum over goals

Rationale and revisit trigger: Resolves category aggregation without changing BD-20. Revisit before alternative peer groups

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-007`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-008

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 23/24.

Choice: Classical uses equal ordinary weights and the same beta blend; vulnerability/AP/RP absent. Both methods have 0.01 normalized-cost and 0.01 normalized-waste coefficients

Rationale and revisit trigger: Controlled comparator and explicit trade-offs; revisit when domain owners supply conventional weights

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-008`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-009

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 19/20.

Choice: Canonical JSON with exact decimal strings/rational integers, sorted identity arrays, SHA-256 and immutable full payload; method-independent operational hash and separate policy/settings hashes

Rationale and revisit trigger: Reproducible inputs; revisit only via versioned migration

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-009`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-010

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 12/14/16/19.

Choice: Forecast adapter accepts committed per-series results, actual provider, source literal, estimate kind and explicit central/conservative choice. Convert legacy float using shortest round-trip decimal string and disclose conversion

Rationale and revisit trigger: Branch compatibility without claiming recovered precision. Revisit when upstream numeric contract lands

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-010`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-011

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 30/33/35.

Choice: PostgreSQL admission/leases plus a supervisor and terminable child process per method; one shared expensive-work slot; sequential pair; manual retry

Rationale and revisit trigger: Matches accepted runtime architecture without a new queue vendor; reconsider only with actual shared executor requirements

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-011`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-012

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 04/19/25/29.

Choice: PostgreSQL immutable OR input packages, policies, scenarios, jobs/attempts, per-method results, transfer rows, check reports and reviews; upstream ledger remains authoritative

Rationale and revisit trigger: Full OR persistence without inventing a second stock ledger; reconcile table ownership if upstream lands first

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-012`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-013

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 02.

Choice: Show plan/site/product/date before-after impact and per-transfer rationale; omit numeric per-transfer benefit

Rationale and revisit trigger: Useful explanations without arbitrary additive attribution; revisit only for an explicit counterfactual feature

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-013`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-014

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 31.

Choice: Presenter session with server-side hashed opaque token; same-origin proxy; backend checks session and mutation CSRF/origin; saved synthetic reads public

Rationale and revisit trigger: Concrete local demo security design; reuse equivalent existing auth rather than replace it

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-014`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-015

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 20/30.

Choice: Old results remain readable; current operational requests require current revision token. Explicit historical replay uses frozen data and is labeled historical

Rationale and revisit trigger: Separates reproducibility from stale recommendations

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-015`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-016

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 29/30.

Choice: Comparison ends SUCCEEDED, PARTIAL or FAILED; each method has independent outcome. Persist first validated result even if partner fails; never substitute methods

Rationale and revisit trigger: Honest partial results; revisit for future product requirements

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-016`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-017

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 22.

Choice: Integer handling units, explicit product coefficients 1–1000, route load limits, per-day receiving limits, source handling limits, one global batch handling budget, optional simulated transport-cost budget

Rationale and revisit trigger: Joint product feasibility; no guessed meal-to-bottle conversion

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-017`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-018

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 24/35.

Choice: Initial bounds: 12 beneficiaries, 2 hubs, 2 products, 256 original lots/confirmed arrivals total, H≤3, 7 forecast days, goal target≤100,000; every constructed integer expression must fit below 2^60 in absolute worst-case activity

Rationale and revisit trigger: Fast first draft with numerical headroom; reject unsupported scope explicitly, never silently truncate

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-018`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-019

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 23/34.

Choice: Treat local equation proofs/enumeration and paper adaptation mapping as a pre-solver build gate. No claim that a citation, this draft, or prior primitive tests passes it

Rationale and revisit trigger: Preserves V5 research gate; implementer completes evidence before complex solver code

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-019`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-020

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 29/32/36.

Choice: Provide an explicit SIMULATED immutable-input publication path and CLI for full OR integration tests. LIVE input requires real committed upstream read adapters and revision checks

Rationale and revisit trigger: The OR service can be complete and testable before upstream modules merge, without passing fixture data off as live integration

Alternative: retain the related OPEN topic for a later version with a different validated policy. Limitation: the selected behavior is bounded to this draft and requires explicit new policy/scenario identity when changed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-020`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

