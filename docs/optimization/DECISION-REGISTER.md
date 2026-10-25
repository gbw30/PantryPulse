> **Current approved integration:** [Connected application and v2 contracts](CONNECTED-INTEGRATION.md) supersede historical OR-only/no-proxy scope and 15/25/60-second execution limits below. The old decision manifest and qualification artifacts remain historical evidence; their hashes and semantics are not reinterpreted.

# Provisional OR decision register

Draft 1.1 / policy or-policy-v1 / schema or-input-v1 and or-scenario-v1. Owner: implementation lead; review state: provisional, adopted October 24, 2026. These choices do not resolve accepted backend OPEN records.

The user narrowed ownership through execution revision 1.2. Mathematical choices
remain unchanged. Decision IDs are retained in historical fixture/hash contracts;
they do not imply implementation/acceptance of every external workflow choice.
OR-DEC-012 is deferred to the persistence owner; OR-DEC-014's Next proxy choice is
withdrawn. OR-DEC-011/015/016/020 have explicitly bounded core coverage only.
The v2 manifest checks those ownership/status distinctions without inventing tests
for removed external systems. Historical broad proposals remain visible below.

## OR-DEC-001

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 06/21.

Choice: One operational timezone per network in v1; explicit IANA zone; seven local dates; arrivals then expiry then batch dispatch on day 1 then daily service. Expiry D prohibits use on D; unknown expiry unavailable

Rationale and revisit trigger: Clear executable clock. Revisit for mixed-zone networks or time-of-day receipt/expiry modeling

Alternative: model a timezone and receipt/expiry timestamp per site. Limitation: local date granularity cannot express intraday ordering or mixed-zone networks; such inputs need a new clock contract before acceptance.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-001`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-002

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 19/21/22.

Choice: One dispatch batch before day-1 service; route ETA is an explicit integer day offset 0–2. Allocation window H is explicitly 1–3 days. No silent window or transfer-mode default

Rationale and revisit trigger: Bounded scheduling with actual late-arrival accounting; revisit for multiple dispatches

Alternative: optimize multiple dispatch batches and carry inventory decisions between periods. Limitation: this model chooses one batch; dated service is projected afterward, and proposed inbound never becomes dispatchable stock.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-002`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-003

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 21.

Choice: A sending beneficiary must cover its full seven-day demand and explicit end-of-day reserve without any proposed inbound transfers. No-action already failing protection makes it ineligible to donate that product

Rationale and revisit trigger: Conservative donor protection; revisit for authorized shortage-sharing or shorter reserve policy

Alternative: protect donors for H only, or allow joint inbound to offset their outgoing stock. Limitation: seven-day no-inbound protection can exclude useful network exchanges; an authorized shortage-sharing policy needs a new version and independent safety evidence.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-003`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-004

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 21/22.

Choice: Fixed loading order per source/product: descending ETA, then destination UUID. Each route packs eligible lots by expiry, availability, original lot UUID. Local service uses the same deterministic FEFO key

Rationale and revisit trigger: Exact hard FEFO with a tractable model. Loading order restricts lot assignments and can affect outcomes; revisit with alternative-order sensitivity or joint dispatch scheduling

Alternative: enumerate loading orders or jointly optimize route order and lot assignments. Limitation: fixed descending ETA/UUID order restricts feasible assignments; this is a chosen scheduling convention, not a proof that all physically possible schedules were searched.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-004`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-005

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 04/09/21.

Choice: Optimize free stock only. Freeze disjoint physically on-hand usable, reservation, fixed-commitment and held quantities; protected quantities cannot fund new shipments or local free service. Future confirmed arrivals serve locally but cannot be exported in this batch

Rationale and revisit trigger: Avoid double counting and inventing future dispatchable stock. Revisit with complete commitment event simulation

Alternative: consume an authoritative commitment-event ledger and model each obligation explicitly. Limitation: the current package requires disjoint protected/free quantities and rejects service-overlap commitments; it cannot reconcile ambiguous upstream obligations.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-005`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-006

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 23/25.

Choice: Research defaults: lambda=1, beta=1/2, two attribute coefficients 1/2 each, AP threshold 3/4, RP threshold 1/4, allowed AP and RP shares 1/4 each, both penalties 1

Rationale and revisit trigger: Transparent demonstrable baseline; all are provisional and sensitivity-tested, not values attributed to the paper

Alternative: elicit coefficients from domain owners or calibrate them against approved institutional data; reproduce endogenous weighting only as a separate research model. Limitation: these defaults and fixed proxy scores are provisional; synthetic sensitivity is not social-policy validation.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-006`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-007

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 23/24.

Choice: One RP group per product, all included positive-target beneficiaries including self; each active group has at least two members. AP/RP excess averaged over active products; W remains a sum over goals

Rationale and revisit trigger: Resolves category aggregation without changing BD-20. Revisit before alternative peer groups

Alternative: use approved community peer groups, historical reference means, or normalized cross-product groups. Limitation: the current mean changes with the candidate and includes self; singleton groups are rejected and raw product units are never pooled.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-007`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-008

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 23/24.

Choice: Classical uses equal ordinary weights and the same beta blend; vulnerability/AP/RP absent. Both methods have 0.01 normalized-cost and 0.01 normalized-waste coefficients

Rationale and revisit trigger: Controlled comparator and explicit trade-offs; revisit when domain owners supply conventional weights

Alternative: use domain-specific conventional weights or a lexicographic comparator. Limitation: that would change the comparison question; equal classical weights are a controlled local baseline and different native objective scores do not establish a universal winner.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-008`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-009

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 19/20.

Choice: Canonical JSON with exact decimal strings/rational integers, sorted identity arrays, SHA-256 and immutable full payload; method-independent operational hash and separate policy/settings hashes

Rationale and revisit trigger: Reproducible inputs; revisit only via versioned migration

Alternative: canonical binary encoding or a database revision reference without a full snapshot. Limitation: canonical JSON is inspectable and replayable, but content hashes do not authenticate a source, prove commitment, or establish current authorization.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-009`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-010

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 12/14/16/19.

Choice: Forecast adapter accepts committed per-series results, actual provider, source literal, estimate kind and explicit central/conservative choice. Convert legacy float using shortest round-trip decimal string and disclose conversion

Rationale and revisit trigger: Branch compatibility without claiming recovered precision. Revisit when upstream numeric contract lands

Alternative: require decimal-native upstream forecasts and reject all legacy floats. Limitation: shortest round-trip conversion preserves the supplied float value only; original precision cannot be recovered and conversion remains disclosed.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-010`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-011

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 30/33/35.

Choice: OR computational calls cap native search at 15 seconds. The Linux offline runner uses a terminable child per method, sequential pairs, 25-second method and 60-second pair boundaries. Shared admission, leases and whole-worker quotas are external handoffs

Rationale and revisit trigger: Bound supplied-file computations without importing the shared queue. Revisit the execution adapter with the runtime owner before hosted integration

Alternative: rely solely on the native search timer, or delegate all execution to the shared runtime. Limitation: direct calls do not bound construction/checking; the Linux offline runner adds owned-child deadlines, address-space limits and cleanup, not application admission, leases or aggregate worker quotas.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-011`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-012

Status: `DEFERRED_EXTERNAL_OWNER`. Related OPEN IDs: 04/19/25/29.

Current boundary: Persistence is an external handoff, not an OR deliverable. The choice below is historical proposal context; no ORM or migrations are owned here.

Historical choice: PostgreSQL immutable OR input packages, policies, scenarios, jobs/attempts, per-method results, transfer rows, check reports and reviews; upstream ledger remains authoritative

Rationale and revisit trigger: Full OR persistence without inventing a second stock ledger; reconcile table ownership if upstream lands first

Alternative for the persistence owner: normalized plan/check tables or validated versioned JSON snapshots. Limitation: OR returns typed values and owns no database tables, transactions, review history or stock ledger; historical persistence proposals are not implemented acceptance.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-012`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-013

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 02.

Choice: Return typed plan/site/product/date before-after metrics and per-transfer rationale; omit numeric per-transfer benefit. Presentation is outside OR ownership

Rationale and revisit trigger: Useful explanations without arbitrary additive attribution; revisit only for an explicit counterfactual feature

Alternative: compute marginal benefit with separate counterfactual solver runs for each transfer. Limitation: coupled constraints make benefits nonadditive; the current component returns plan/site/product/date metrics and rationale without inventing transfer-level numeric credit.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-013`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-014

Status: `WITHDRAWN_BY_USER_SCOPE_CORRECTION`. Related OPEN IDs: 31.

Current boundary: The user prohibits Next.js API routes/proxies. The historical choice below is withdrawn. Authentication and frontend-to-FastAPI access contracts belong to their respective owners.

Historical choice: Presenter session with server-side hashed opaque token; same-origin proxy; backend checks session and mutation CSRF/origin; saved synthetic reads public

Rationale and revisit trigger: Concrete local demo security design; reuse equivalent existing auth rather than replace it

Alternative for the access-contract owner: define frontend-to-FastAPI access with deployment-specific session/CORS controls. Limitation: the historical Next proxy is withdrawn and prohibited; no authentication or frontend implementation is authorized by this decision.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-014`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-015

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 20/30.

Choice: Require the supplied expected revision for current scenario construction. Explicit historical replay uses frozen data and carries a historical flag; source-store freshness and saved reads belong to the caller

Rationale and revisit trigger: Separates reproducibility from stale recommendations

Alternative: discard old inputs and recompute every request, or query authoritative revisions in the integration layer. Limitation: OR checks the caller-supplied expected revision and historical intent only; freshness and access must be established by the caller.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-015`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-016

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 29/30.

Choice: Comparison returns SUCCEEDED, PARTIAL or FAILED with independent method outcomes. Retain a verified result if its partner fails; recheck identities and candidate metrics before assembly; never substitute methods. Persistence is external

Rationale and revisit trigger: Honest partial results; revisit for future product requirements

Alternative: fail the entire pair whenever either solve fails, or couple methods into one solve. Limitation: both hide a valid independent result or confound methods; OR retains independent outcomes in the return value, while durable retention belongs to storage owners.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-016`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-017

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 22.

Choice: Integer handling units, explicit product coefficients 1–1000, route load limits, per-day receiving limits, source handling limits, one global batch handling budget, optional simulated transport-cost budget

Rationale and revisit trigger: Joint product feasibility; no guessed meal-to-bottle conversion

Alternative: use volume, mass and vehicle constraints as separate dimensions. Limitation: the current explicit handling coefficients represent declared capacity accounting, not a physical conversion between meal and bottle quantities; new dimensions need new schema/bound proofs.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-017`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-018

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 24/35.

Choice: Initial bounds: 12 beneficiaries, 2 hubs, 2 products, 256 original lots/confirmed arrivals total, H≤3, 7 forecast days, goal target≤100,000; every constructed integer expression must fit below 2^60 in absolute worst-case activity

Rationale and revisit trigger: Fast first draft with numerical headroom; reject unsupported scope explicitly, never silently truncate

Alternative: raise bounds, decompose the problem, or reduce numerical precision. Limitation: shape bounds are ceilings, not a guarantee that every combination is numerically safe or reaches an optimum within the timer; actual emitted intervals and native validation remain mandatory.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-018`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-019

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 23/34.

Choice: Treat local equation proofs/enumeration and paper adaptation mapping as a pre-solver build gate. No claim that a citation, this draft, or prior primitive tests passes it

Rationale and revisit trigger: Preserves V5 research gate; implementer completes evidence before complex solver code

Alternative: accept citations and solver summaries without independent arithmetic. Limitation: exact tiny enumeration is exponential and finite native checks do not prove every future instance; retain analytic obligations, independent replay and explicit qualification limits.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-019`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## OR-DEC-020

Status: `SELECTED_FOR_DRAFT_1`. Related OPEN IDs: 29/32/36.

Choice: Accept explicit immutable SIMULATED packages in the callable service and offline CLI for OR computation tests. LIVE committed-source reads, authorization, publication and revision-store checks remain external dependencies

Rationale and revisit trigger: The OR service can be complete and testable before upstream modules merge, without passing fixture data off as live integration

Alternative: wait for approved live-source adapters before testing, or silently treat demo fixtures as live data. Limitation: offline SIMULATED packages establish computational behavior only; committed-source reads, publication and live qualification belong to upstream/integration owners.

Affected behavior, files and tests: see the machine-checked [marker manifest](decision-manifest.json); runtime metadata retains `OR-DEC-020`. Verification is recorded separately in [acceptance evidence](ACCEPTANCE.md).

## October 25 final audit

All twenty entries now state concrete alternatives and limitations. Mathematical values,
policy/schema versions and retained decision IDs are unchanged. Qualification evidence
is in [QUALIFICATION.md](QUALIFICATION.md); selected defaults remain provisional.
No external or withdrawn decision is promoted to implemented status.
