# Operational data and inventory contract — issue #8

Version: `operational-v1` · October 24, 2026, America/New_York.

**Status: technical operational baseline ready for issue #19 implementation; persistence and independent verification pending.**
[V5](SPEC-V5.md) remains authoritative. BD-42–47 record the user's six explicit policy selections; the remaining storage and transaction specifications are technical elaborations prepared under the user's instruction to finish #8 before #19, not additional claimed interview selections. Internal record names may be mapped to SQLAlchemy names in #19 with a documented correspondence; do not change their meaning silently. This contract does not finalize public HTTP payloads, forecasting providers, job schemas, solver objectives or paused supplier policy. No database migration has been performed.

## 1. Agreed behavior and source reconciliation

| Binding requirement | Source | Consequence |
|---|---|---|
| Standard products with explicit base units | BD-02; V5 §5 | A meal and a bottle cannot be added into one physical quantity. |
| Daily demand plus individual donation receipts | BD-03 | Retain receipt identity; donor and receiving site are distinct. |
| Historical import has no stock effect | BD-04 | Importing an old receipt never creates inventory automatically. |
| Explicit exactly-once receipt posting | BD-04 | Receipt linkage, lots, ledger, inventory version and audit commit together. |
| Append corrections; retain original revisions | BD-05 | Replay references exact revisions; no overwrite of historical facts. |
| Unknown demand is not zero; proxies require opt-in | BD-06/27 | Null, missing and observed zero remain distinguishable. |
| Confirmed supply differs from predicted supply | BD-07 | Forecast donations and draft supplier proposals never become stock. |
| Explicit operator lot eligibility | BD-25 | Unknown eligibility stays unavailable; changes retain actor/time/reason. |
| Partial import, complete receipt atomicity | BD-26 | Valid demand rows can succeed individually; a receipt and its lines succeed together. |
| Nonnegative stock, expected versions, durable audit | V5 §5.3; INV-01/16 | Reject stale/invalid mutations without partial stock changes. |
| Plan review has no stock effects | BD-01 | No reservation, physical transfer or dispatch is introduced here. |
| First-release stock correction uses audited adjustments only | BD-42, selected in this chat October 24 | Do not add a separate physical-count/discrepancy investigation workflow. |
| Explicitly declared non-expiring stock is supported | BD-43, selected in this chat October 24 | Distinguish non-expiring from unknown expiry; retain eligibility and operational checks. |
| Dated stock is usable through its expiry day | BD-44, selected in this chat October 24 | Exclude from the following local midnight, subject to other eligibility checks. |
| History correction survives a rejected negative stock adjustment | BD-45, selected in this chat October 24 | Keep stock unchanged and flag unresolved receipt reconciliation. |
| Posted cancellation follows the same nonnegative-stock rule | BD-46, selected in this chat October 24 | Retain void history; reverse stock only when possible; otherwise flag mismatch. |
| Downward receipt correction does not create an incoming promise | BD-47, selected in this chat October 24 | Require explicit reconfirmation before restoring future confirmed supply. |

Reviewed sources: V5 §§5/16/18/19, BACKEND-SPEC §3, checkpoint BD-01–07/25–27 and OPEN-04–11, compatible PROJECT-CONTRACT identity rules, INVARIANTS, ACCEPTANCE-MATRIX, detailed/simple backend data-flow documents, migration/contracts READMEs and repository data/API rules. Older three-site examples, forecast `p50` examples, approval states and source-history uniqueness examples do not supersede V5.

This review covers repository requirements; it does not claim a fresh full-text verification of every Google Docs tab or unpublished user decision. The earlier live issue review supplied issue #8's current scope.

## 2. Storage conventions — OPEN-04/05

Concrete names/types in §§2–7 define the internal storage handoff. They are not generated public DTOs or a claim that SQL tables already exist.

Bounded executable contracts now exist in [operational.py](../../apps/api/app/schemas/operational.py), with pure [calendar/ownership checks](../../apps/api/app/services/inventory/contracts.py). They validate counts, observed demand components, complete receipt revisions and expiry declarations. They do not establish database ownership, duplicate protection, ledger atomicity or a completed posting service; those require #19/#21. Their names are internal and do not finalize #12's HTTP payloads.

- UUID primary identities; organization-owned records carry `organization_id`.
- Organization-owned references use composite foreign keys `(organization_id, referenced_id)` against matching unique keys. Knowing another organization's UUID does not authorize linking it.
- UTC `TIMESTAMPTZ` for actual/recorded instants; `DATE` for operational calendar days. Preserve event time separately from knowledge/recording time.
- Physical and observed counts use nonnegative PostgreSQL `BIGINT` integers, range `0..9223372036854775807`. Receipt quantities are positive. Signed ledger deltas permit negative movements, but each resulting balance must remain in the count range. Reject fractional counts, booleans, nonfinite values and overflow; never silently truncate. Bound aggregate calculations separately before BIGINT persistence or solver conversion.
- Forecast estimates remain outside this count contract; #9 owns the exact forecast-to-count bridge. Scale 10,000 is for research deficits, not a physical-stock unit.
- Product units are explicit immutable identifiers for referenced historical quantities. Changing a unit requires a new product identity or a separately reviewed conversion, never relabeling old counts.
- Store revisions append-only. Corrections and deactivation do not cascade-delete historical records.

### Record dictionary

`id`, `organization_id` and appropriate recorded timestamps are implicit below except for Organization itself. Required/nullable business fields are stated explicitly.

| Logical record | Required fields / nullable fields | Integrity and use |
|---|---|---|
| Organization | `name`, `is_demo`, `created_at` | Ownership boundary; no automatic demo reset here. |
| Site | `name`, `role`, `active`, `timezone_version_id`; nullable latitude/longitude | Reuse HUB/BENEFICIARY domain roles; inactive sites retain history and cannot enter new active scope. |
| SiteCalendarVersion | `site_id`, IANA `timezone`, `recorded_at`, positive `revision`; superseded version reference nullable | Append timezone changes; new facts bind an explicit version, never recompute historical days using a later version. |
| Product | `name`, `category_id`, `base_unit`, `active` | Category and product references share organization; handling coefficient belongs to #11, not physical stock arithmetic. |
| Category | `name`, `active` | Groups compatible reporting; different product IDs are not implicitly substitutable. |
| Donor | `name`, `active` | Separate identity from Site; optional linkage must not collapse donor and receiver. |
| DataSource | `name`, `classification`, immutable source identity/version | Classification is OBSERVED or SIMULATED, separate from demand basis; never choose source authority by arrival order. |
| DemandRecord | `site_id`, `product_id`, `local_day`, `source_id`, `source_record_key` | Stable logical fact identity for append-only revisions; do not retarget an existing source key to a different site/product/day. |
| DemandRevision | `site_id`, `product_id`, `local_day`, `calendar_version_id`, `source_id`, `source_record_key`, `revision`, `source_classification`, `recorded_at`; nullable `requested`, `fulfilled`, `unmet` | At least one observed component; check nonnegative counts and `requested=fulfilled+unmet` when all three are known. |
| Receipt / ReceiptRevision | Stable receipt ID; revision has `receiving_site_id`, `donor_id`, `received_at`, derived `local_day`, calendar version, source/key, revision, classification, `recorded_at`; previous revision nullable | Entire receipt event is revised together; source identity unique per organization/source/key. |
| ReceiptLine | `receipt_revision_id`, stable `line_key`, `product_id`, `received_quantity`; nullable declared expiry/lot reference | Unique line key within revision; at least one line, positive quantities; preserve product identity across correction lineage. |
| DonationCoverageRevision | `site_id`, `product_id`, `local_day`, calendar/source identity, revision, coverage declaration, `recorded_at` | Explicit per-product complete/incomplete reporting; no receipts alone does not establish zero. |
| Lot | `site_id`, `product_id`, receipt-line/posting linkage, `received_at`, `on_hand`, `eligibility`, `metadata_version`, `expiry_kind`; nullable `expires_on` | Kinds DATED/NON_EXPIRING/UNKNOWN: DATED requires a date; other kinds require null. Explicit non-expiring declaration retains actor/time/reason. |
| ReceiptPosting | `receipt_id`, `posted_revision_id`, `command_id`, `posted_at`, actor | Unique original posting per receipt; corrected revisions use linked adjustment batches, never a second full posting. |
| StockLedgerEntry | `site_id`, `product_id`, `lot_id`, signed `delta`, `reason`, `command_id`, effective/recorded times, actor, before/after inventory versions; source and reversal references when relevant | Nonzero delta; references consistent; append-only. See ledger authority proposal below. |
| InventoryVersion | `site_id`, `product_id`, `version` | Unique organization/site/product row; version increments once per successful stock-changing command per affected pair. |
| StockCommand / Audit | command identity, actor, organization, operation, idempotency key, canonical payload digest, exact outcome/source links, timestamp/reason | Unique organization/key; successful replay retains original outcome; credentials and raw imports excluded. |
| ExpectedSupply / ReceiptAllocation | destination/product, source identity, version, state, original quantity, net received quantity, explicit `outstanding_confirmed_quantity`, confirmation revision/arrival where applicable; immutable allocation/reversal entries link actual receipt line/posting and quantity | Nonnegative counters with `received + outstanding_confirmed <= quantity`; outstanding quantity never inferred solely by subtracting received. Uniqueness and sum limits prevent reusing a received unit. |

### Uniqueness and indexes

- Unique demand `(organization, source, source_record_key, revision)` plus source-key identity tied to one site/product/day. Index `(organization, site, product, local_day, recorded_at)`.
- Unique receipt source/key; revision `(receipt_id, revision)`; lines `(receipt_revision_id, line_key)`; explicit coverage logical key plus revision.
- Do not retain historical single-row `unique(site, product, day)` as a revision constraint: it would prevent corrections.
- Lot lookup `(organization, site, product, expires_on, id)`; ledger lookup `(organization, lot_id, recorded_at, id)`; expected supply `(organization, site, product, state, expected_arrival_at)`.
- Positive revision/version numbers; exact foreign-key ownership; nonnegative count checks; geographic validity if supplied. Multirow receipt consistency requires transaction/service validation in addition to SQL constraints.

## 3. Calendar and expiry — OPEN-06

Existing agreement: store UTC instants and derive operational days using versioned site timezones. The demo uses America/New_York; do not use host timezone as a default for arbitrary sites.

Operational representation:

1. An operational day starts at local midnight and ends at the next local midnight; daylight-saving days may have 23 or 25 hours.
2. Require timezone-aware receipt instants. Reject ambiguous naive local timestamps rather than guessing a DST offset. Verify any supplied local day against the selected calendar version.
3. Record the calendar version/local day on each revision. A later timezone change does not rewrite old observations; a historical calendar correction creates explicit new revisions.
4. **Accepted BD-44:** treat `expires_on` as the last usable local calendar date; unavailable from next local midnight. Preserve expired stock physically until an explicit disposal adjustment removes it. Exact allocation arrival/use order stays in #11.
5. **Accepted BD-43:** allow explicitly declared non-expiring stock. Representation: DATED with required `expires_on`, NON_EXPIRING with null date and explicit declaration, UNKNOWN with null date and unavailable for allocation. Never infer NON_EXPIRING from a missing/null field. Correcting the declaration is an audited availability/version change. Non-expiring does not bypass held/ineligible status, donor protection or capacity checks. Expiry labels do not establish food safety.

## 4. Source identity, revisions and missingness — OPEN-07

Storage selection procedure: require an explicitly chosen authoritative source per logical series/scope; do not install an automatic source-priority default. Multiple sources may be retained but cannot be silently added or overwritten. For a named logical record at a knowledge cutoff, select the highest revision recorded by that cutoff, subject to its event-date cutoff. Never use later corrections retroactively. A same-number revision with different content conflicts; an exact duplicate is reported as duplicate, not accepted as new history. #9 owns its forecast preparation selection interface; this is not adoption of a forecasting branch default.

Source classification (for example SIMULATED/OBSERVED) is separate from target basis. Do not label fulfilled counts as requested counts, or deduce absent observations from incomplete reporting. Coverage corrections are versioned and participate in the knowledge cutoff.

Daily received quantity sums lines from each selected receipt revision exactly once by receiving site/product/day. Complete reporting and no receipt establish observed zero. Incomplete/absent coverage leaves the daily total unknown, with recorded receipts still inspectable; no automatic zero fill. #9 must review compatibility with its forecast preparation contract.

Receipt input includes all lines of a revision. Reject a duplicate line key, inconsistent receiver, unknown product or cross-organization reference for the whole receipt. Valid demand rows and other complete valid receipts can still succeed in a partial import. Header/structural errors cannot fabricate accepted rows. Exact wire errors and import-size limits stay with #12/#22.

## 5. Receipt posting, corrections and ledger — OPEN-08/09

### Transaction and concurrency design

- Append-only ledger entries are the stock-change authority; `Lot.on_hand` is a transactionally maintained materialized balance. Opening balances also require explicit audited commands, not a side effect of importing history.
- Lock each affected `(organization, site, product)` inventory-version row in sorted UUID order, then affected lots in sorted ID order. Create missing version rows with uniqueness-safe initialization before locking; no stock mutation can bypass the same version protocol.
- One inventory version per site/product serializes stock and eligibility/expiry changes that affect availability. Metadata changes have separate audited events, not fake zero-quantity ledger entries.
- Require expected versions for affected pairs; stale writes fail without partial changes. A multi-product receipt commits all of its lots/entries/audit/version changes or none.
- Successful commands store a canonical validated payload digest and saved outcome under a unique organization-scoped idempotency key. Authenticate before replay; same key/same operation/payload returns the original outcome even when its original expected version is now old. Changed operation/payload conflicts. Concurrent duplicates serialize on the command identity; no duplicate ledger entries.
- Failed transactions leave no successful command or partial ledger/balance/audit change. Retries still validate versions. Do not use a database transaction across model execution.
- Canonical payload identity must include organization, operation, target IDs, exact revision, quantities, expected versions and reason. #12 owns public authentication/status/error envelopes; this defines domain outcomes only.

Initialize a new site/product inventory-version row at 1 using uniqueness-safe insertion; all writes, including first posting, require the explicitly supplied current version. Creation of that control row is not a stock credit. Canonical command identity uses validated values serialized as UTF-8 JSON with sorted object keys, compact separators, exact integers, UUID strings, ISO dates and UTC timestamps. Reject duplicate JSON keys and nonfinite values at ingestion; exclude generated command IDs/completion timestamps from identity. Sort unordered per-lot operations by UUID and reject repeated lot targets; preserve meaningful receipt line keys. Hash canonical bytes with SHA-256. Never log the payload or credential-bearing metadata. #12 may wrap this internal command in its final public envelope.

### Receipt lifecycle

1. Import/record a complete revision as historical facts: **no lot/balance changes**.
2. Explicit POST_RECEIPT identifies the exact revision, eligibility, required batch/expiry details, actor/reason, key and expected inventory versions.
3. Lock/check original posting uniqueness and versions. Atomically create the posting, lots, ledger/audit entries, saved outcome and version increments. Replay returns original outcome.
4. A newer receipt revision does not auto-post. Preserve the original posting; expose any mismatch as requiring explicit reconciliation.
5. CORRECT_POSTED_RECEIPT links original/reconciled revision to target revision and a reviewed per-lot delta. Record the reconciled revision so replay/next correction cannot apply an old delta twice. Never derive each delta from the original quantity after prior corrections.
6. **Accepted BD-45/46:** save the factual corrected/void receipt revision even if the related stock adjustment would make a physical balance negative. Reject that stock adjustment and keep its ledger/balance unchanged; mark receipt reconciliation unresolved. Do not clamp stock to zero, undo past use or report stock reconciliation as successful. An operator must document and reconcile the mismatch explicitly. This is a receipt flag, not a physical-count investigation workflow. Posted cancellations follow the same rule by explicit user selection.

The history correction and attempted physical adjustment are distinct commands/transaction boundaries. The correction must not be rolled back merely because a later stock command fails. Record the new historical revision and outstanding reconciliation marker atomically, and clear that marker only after successful explicit reconciliation. Public command/wire details remain #12; database proof remains #19/#21.
Unposted cancellation appends an explicit void revision; preserve prior versions and exclude void events under cutoff-aware selection. A void revision explicitly has no receipt lines; a received revision has one or more positive lines. Posted reversal is a linked negative ledger batch only when remaining stock permits it; it never deletes the original posting or supply linkage. BD-46 explicitly selects the consumed-stock rule for posted cancellations.

Line removal/quantity reduction uses linked negative entries where possible; added lines require explicit lot/eligibility declarations. Product/receiver changes cannot silently rewrite an existing lot: require an explicit valid reversal/replacement sequence, or reject if consumed stock prevents it. Real transfer completion and reservations remain P1.

## 6. Confirmed supply and receipt reconciliation — OPEN-10

Internal states: UNCONFIRMED, CONFIRMED, CANCELLED, RECEIVED; partial receipt is represented by reconciled amounts, not disappearance of the outstanding balance. These are storage terms, not public job or API enums.

- Only confirmed outstanding quantity with usable arrival metadata may enter baseline future supply; operational eligibility/ETA tests remain #11.
- An explicit receipt-posting transaction links any matched actual quantities to expected-supply lines and removes those units from future-inbound accounting at the same commit that adds physical lots.
- Example: confirmed 100, receive/post 60 → on-hand +60 and outstanding confirmed 40. Never count on-hand 60 plus inbound 100.
- Overdelivery requires explicit actual receipt records; reconciliation cannot exceed the confirmed outstanding amount. Extra received units may post as separately identified actual supply, not negative outstanding supply.
- Cancellation removes only unreceived outstanding supply. Received goods require physical reversal/adjustment; cancellation never silently removes stock.
- Metadata-only receipt revisions and historical imports cannot make expected supply RECEIVED or add on-hand stock. Match-source provenance remains auditable.
- A posted-receipt correction must reconcile stock and supply links atomically. **Accepted BD-47:** do not restore corrected received quantity to future confirmed supply automatically. Require a new explicit confirmation; a reduced historical receipt does not prove a new delivery is promised. If stock reconciliation fails, preserve the prior physical/allocation state and flag the mismatch; do not increase future supply to conceal it.
- Persist the outstanding confirmed amount explicitly, with versioned confirmation evidence. Example: original 100 fully received, then corrected/reconciled to 80 -> net received 80, outstanding confirmed 0, not 20. Only an explicit reconfirmation may set outstanding to 20. For original 100 with only 60 received, ordinary partial delivery leaves outstanding 40 until cancellation/reconfirmation changes it. Do not implement `outstanding = original_quantity - received_quantity` as an unconditional generated column: it would violate BD-47 after a correction.
- Predictions, offers and supplier proposals stay outside this lifecycle until a separately authorized real confirmation fact exists; supplier design remains paused.

## 7. First-release counts and discrepancies — OPEN-11

**Accepted BD-42:** first-release scope is controlled audited stock adjustments only. Each adjustment names lot/product/site, signed delta, actor, reason and expected inventory version; it cannot create negative physical stock. Positive adjustments also require source and eligibility/expiry declarations as applicable. Exact transaction fields remain proposed under OPEN-08/09.

A physical-count session, discrepancy investigation/approval lifecycle and automatic recount correction are excluded from the first release by this selection. Their appearance in historical explanatory documents does not add them back. An operator can record a documented correction through the audited adjustment command; no separate discrepancy-management feature is implied. A presenter marking an allocation plan reviewed never adjusts stock.

## 8. Worked acceptance examples

These are independent arithmetic/transaction expectations for future implementation, not executed database tests. Short names are aliases, not wire IDs.

| ID | Input/action | Expected result |
|---|---|---|
| OP-01 | Requested 60, fulfilled 45, unmet 15 | Valid; 60 = 45 + 15. |
| OP-02 | Requested 60, fulfilled 45, unmet 16 | Reject inconsistency; no accepted replacement revision. |
| OP-03 | Requested null, fulfilled 45, unmet null | Preserve unknown requested/unmet; no automatic requested=45. |
| OP-04 | Explicit requested 0 versus no day row | Observed zero and missing day remain different. |
| OP-05 | Import receipt of 30 meals while lot balance is 10 | History gains receipt; physical balance stays 10. |
| OP-06 | Post that receipt with expected version 4 | Balance 40; version 5; posting/ledger/audit/outcome commit together. |
| OP-07 | Replay exact OP-06 command | Balance remains 40; version remains 5; return same saved outcome. |
| OP-08 | Same key, quantity changed to 31 | Conflict; no additional stock. |
| OP-09 | Different commands both expect version 4 | At most one commits; other is stale. |
| OP-10 | Two lines: valid 30 meals, invalid negative bottles | Whole receipt rejected; no line/lot/ledger partial posting. |
| OP-11 | Distinct receipts 20 and 30 meals on same day | Received history totals 50 once under chosen revisions/complete coverage. |
| OP-12 | First receipt corrected from 20 to 15 | Current history totals 45; earlier cutoff remains 50; stock unchanged until correction command. |
| OP-13 | Posted 100, used 70, physical 30; correct receipt to 80 | Delta -20 → physical 10, if explicit linked correction commits. |
| OP-14 | Same facts; correct receipt to 50 | Save receipt revision 50. Delta -50 would give -20: reject stock adjustment; physical remains 30 and ledger unchanged; flag unresolved mismatch (BD-45). |
| OP-15 | Posted 100 → corrected 80 → corrected 90 | Apply -20 then +10; never +90 or another full posting. |
| OP-16 | Confirmed 100; post matched receipt 60 | Physical +60; future confirmed 40; combined quantity remains 100 before use/expiry. |
| OP-17 | Forecast says 30 donated meals; no receipt/confirmation | Physical and confirmed balances unchanged. |
| OP-18 | Organization A receipt references B's site/product | Reject ownership mismatch in service and database constraints. |
| OP-19 | Complete day reporting, no receipts versus incomplete reporting | First is observed zero; second unknown. |
| OP-20 | Receipt at 2026-10-25 02:00 UTC in America/New_York | Local receipt day is October 24; retain exact calendar version. |
| OP-21 | Lot expires October 24 under accepted BD-44 | Usable through October 24 subject to other rules; physical lot remains; unavailable October 25 local midnight onward. |
| OP-22 | Failure after inserting lot but before ledger/audit commit | Roll back all posting effects and successful idempotency outcome. |
| OP-23 | 10 meals plus 20 bottles | Return separate quantities; never report 30 meals/bottles. |
| OP-24 | Supply cancelled after 60 of 100 received | Physical 60 remains; future outstanding 40 excluded. |
| OP-25 | Correct source revision recorded after saved knowledge cutoff | Original source revision remains selected for historical replay. |
| OP-26 | Unknown eligibility or UNKNOWN expiry | Unavailable for allocation; no inference from null to non-expiring. |
| OP-27 | Explicit NON_EXPIRING, null date, eligible stock | No date-expiry exclusion; still check every other operational rule. |
| OP-28 | DATED without date, or NON_EXPIRING with a date | Reject contradictory proposed expiry representation. |
| OP-29 | Posted receipt cancelled after stock was consumed | Save void history; reverse only if nonnegative; otherwise preserve stock and flag mismatch (BD-46). |
| OP-30 | Delivery 100 fully received, then corrected/reconciled to 80 | Net received 80, future confirmed 0; only explicit reconfirmation may add 20 future units (BD-47). |

## 9. Contract readiness and implementation gates

| Topic | Contract v1 contribution | Remaining implementation/integration proof |
|---|---|---|
| OPEN-04 | Records, exact types, bounds and ownership/index requirements defined | #19 supplies SQL models, migration/integrity/rollback evidence. |
| OPEN-05 | Organization-scoped identities, products/base units, donor/site separation defined | #19 tests cross-organization and unit/reference enforcement. |
| OPEN-06 | Inclusive expiry/non-expiring decisions and local calendar representation defined | #19 persists versions; #11 owns dispatch/use/event order, outside #8. |
| OPEN-07 | Explicit source selection, cutoff/revision/coverage and void semantics defined | #9/#22 bind forecasting/import interfaces; no branch defaults adopted silently. |
| OPEN-08 | Posting/correction/cancellation/reversal defined, including BD-45/46 | #19 persists evidence; #21 verifies commands and separate correction/stock transactions. |
| OPEN-09 | Ledger authority, locks/versions, command replay and rollback defined | #19/#21 supply real SQL, concurrency and atomicity proof. |
| OPEN-10 | Partial receipts and explicit reconfirmation defined, including BD-47 | #19/#21 test receipt allocations and outstanding supply without double counting. |
| OPEN-11 | Scope resolved by BD-42: audited adjustments only | Implement/test transaction controls under OPEN-08/09; no physical-count feature in first release. |

Next: implement #19 against this `operational-v1` baseline, with a task packet and isolated PostgreSQL tests. Preserve six explicit user decisions BD-42–47 and distinguish them from implementation elaborations. Public wire binding remains #12; worker schemas remain gbw30's scope. Independent review and merged-tree acceptance are not claimed, and GitHub issue state remains unchanged.

## 10. Issue #19 storage handoff and verification boundaries

The following makes the storage implementation reviewable without starting a migration:

1. Use organization-scoped composite foreign keys for every site/product/source/donor and receipt link, plus contextual keys where needed. A receipt line's product and revision must match its lot; a posting must reference a revision of the same receipt. Correction-created lots may reference later receipt revisions while retaining the same original receipt posting identity; do not constrain every lot to the originally posted revision.
2. Separate a site's append-only calendar versions from its current calendar reference. Enforce that a referenced calendar belongs to the same site; the pointer cannot silently rewrite history. Resolve the initial site/calendar insertion cycle explicitly with a deferred FK or a transactionally initialized pointer.
3. Store immutable receipt revision contents and line sets together. Enforce append-only history and unique revision identities. #22 validates complete imports; #19 must identify which consistency rules are SQL-enforced versus repository-enforced.
4. Receipt reconciliation needs distinct latest factual revision, last physically reconciled revision and outstanding-mismatch state. A saved factual correction cannot accidentally advance the physically reconciled revision. Preserve historical command/reconciliation evidence; a mutable marker is not the audit record.
5. Require per-line supply allocation identity, total reconciled amounts within actual received and confirmed quantities, explicit outstanding-confirmed storage, and atomic outstanding/on-hand updates. Two different expected supplies cannot reuse the same received quantity. Corrections must preserve the original allocation evidence and link reversals; do not overwrite an audit trail to fix a sum. Preserve confirmation versions/audit so explicit reconfirmation can be distinguished from automatic arithmetic.
6. Use exact integer arithmetic for arithmetic checks. Cast before addition in SQL checks where two valid BIGINT operands could overflow. Null demand components remain unknown; also reject known fulfilled or unmet values that individually exceed a known requested value.
7. Non-expiring declaration and date eligibility are separate from operator eligibility. Expiry or eligibility metadata changes invalidate the relevant inventory version even though physical count does not change.
8. Generate and review Alembic migrations as source; importing models must not connect to a database or call `create_all`. #19 does not include forecast/job/scenario tables or #21's stock command orchestration.

| Evidence | Current scope |
|---|---|
| Pure contract tests | `tests/test_operational_schema.py`: strict integer bounds, missingness/arithmetic, receipt completeness/duplicate line keys, immutability, expiry-day/non-expiring distinction, cross-organization check and DST/local dates. |
| Health regressions | Existing health tests exercised with the focused contract checks; health remains process-only. |
| Database access | New supplied Neon connection verified read-only against PostgreSQL 16.15; no application tables present at that check. This is not migration or isolation evidence. |
| Policy selections recorded | BD-42–47, including posted cancellation and explicit reconfirmation. |
| Remaining implementation evidence | Real PostgreSQL migration/integrity/rollback under #19; concurrent receipt/ledger/command tests under #21; HTTP/import integration under owning issues. |

Verification on the current working tree: 30 focused contract cases plus 2 health regressions passed; full API suite **467 passed**; focused Ruff **passed**. The first focused run failed because the schema module did not exist. Lint formatting issues were corrected and rechecked with `--no-cache` because the local cache directory could not be created. One existing Starlette/httpx deprecation warning remains. These checks do not prove inventory API or transactional behavior.
