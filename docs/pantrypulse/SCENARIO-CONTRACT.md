# Operational scenario contract — scenario-v1 / issue #11

Status: local internal contract with validation/freeze helpers. Allocation builders,
independent feasibility verification, database snapshot loading and public API
integration are separate tasks. [PP-33](tasks/PP-33.md) records verification and
remaining review. V5 and later explicit human decisions control this contract.

## 1. Accepted decisions and representation

| Basis | Rule |
|---|---|
| BD-09/10 | Freeze all inputs, versions and source references; replay never reads mutable latest records. |
| BD-41 | Explicit HUB_ONLY or HUB_AND_PANTRY; no default. Allocation method is separate. |
| BD-43/44 | Distinguish dated, declared non-expiring and unknown expiry. Dated stock remains usable through its local expiry day. |
| BD-48 | Daily confirmed arrivals → expiry/eligibility exclusions → outbound commitments → FEFO local service; daily unmet is lost sales. |
| BD-49, selected in this chat | Protect donating pantries' local service on every day of the frozen seven-day horizon, plus configured reserves. |
| BD-50, selected in this chat | One simulated batch on the first day of an explicit 1–3-day allocation window; one shared frozen planning timezone; whole-day route delays. |
| BD-51, selected in this chat | Every incoming transfer unit must contribute to additional service within the allocation window; no surplus or later-window stocking. |

The field layout, integer cost/handling representation, encoding and identity rules
below are technical elaborations under this task. Concrete reserves, coefficients,
capacities, routes, cost values, dates and mode are explicit frozen inputs. There
are no implicit zero/unlimited/route/default-mode policies. Example numbers are
simulated fixtures and establish no real delivery promise, food-safety assessment
or research result.

## 2. Complete operational input dictionary

`apps/api/app/schemas/scenario.py::OperationalScenario` is the strict internal
schema. All fields are required; unknown fields are rejected. Nested collections
are tuples and typed models are frozen. Each number below is an integer unless
explicitly described as an exact Decimal string.

| Field | Meaning and checks |
|---|---|
| schema_version | Exactly scenario-v1; incompatible changes need a new version/adapter. |
| organization_id | Sole owner of all embedded operational series. The loader must verify referenced source ownership. |
| transfer_mode | Exact required mode; same for every embedded series and both compared methods. |
| planning_timezone | Valid IANA zone, identical to all included sites' frozen calendar zones. Cross-zone planning is rejected in v1. |
| horizon_start | First of exactly seven contiguous protected demand dates. |
| allocation_start, allocation_days | Explicit 1–3-day inclusive subwindow within those seven days. Dispatch is allocation_start. No second dispatch is permitted. |
| network_site_ids, network_product_ids | Complete membership known at capture, including intentionally excluded members. A loader must verify the membership token. |
| sites, excluded_sites | Disjoint exact partition of known sites. Exclusions carry nonempty reasons; missing data cannot silently remove a site. At least one hub and beneficiary must remain. |
| products, excluded_products | Same explicit partition for products; at least one included product. Each product declares a base-unit label and positive integer handling_units per physical unit. No substitution or conversion. |
| sites[].calendar_version_id/timezone/role | Frozen calendar and HUB/BENEFICIARY identity; never read a changed role/zone during replay. |
| sites[].receiving_capacity | Explicit shared handling-unit ceiling for each of the seven days; zero means closed, not unlimited. |
| sites[].reserves | Explicit per-product eligible end-of-day reserve floor for each of the seven days; zero must be supplied when no reserve is required. |
| series | Exactly one projection-v1 input per included site/product. Seven demand days, same organization/unit/calendar/mode/opening date; immutable lots, commitments, outstanding confirmed supply and demand/provider references. Lot/commitment IDs and stock/supply source identities are globally unique within the package. |
| series for hubs | Explicit zero beneficiary demand on all seven days; hubs can retain reserves and existing commitments. Hubs do not become beneficiary fairness goals. |
| forecasts | Exactly one complete canonical document for each referenced forecast ID, plus upstream schema version. actual_provider must match selected series. Freeze original points/quantiles, cutoff, provider/model/checkpoint/fallback metadata, history/input identity and transformations; do not fetch them later. |
| routes | Unique directed origin/destination pair and UUID; distinct included endpoints, beneficiary destination, explicit enabled flag, integer transit_days 0–6, handling_capacity and a nonnegative unit movement cost for every included product. Missing route means unavailable. |
| handling_unit_label, batch_handling_capacity | Common declared handling basis and shared batch ceiling. Product coefficients convert physical counts to this basis exactly. |
| cost_unit_label | Common explicit cost-tick basis, e.g. simulated movement tick. This is not implicitly dollars or real vendor pricing. |
| policy | Immutable policy ID/schema version and complete canonical payload. Its mathematical schema and qualification remain #10/#26; retaining bytes does not qualify a policy. |
| assumptions_json | Canonical object containing explicit applied assumptions/transformations, provenance and classification. No hidden buffer, multiplier or missingness repair. |
| sources | Unique kind/key/version/content_hash manifest for all relevant source records and membership/selection tokens. Hashes are lowercase SHA-256. |

The forecast and policy documents are opaque, exact versioned objects here. Their
upstream semantic validation is mandatory before live scenario creation (#9/#10/
#26/#29/#30). Fixture-only payloads must remain labeled as fixtures. This contract
defines their embedding and reference boundary; it does not invent missing
forecast quantile/buffer rules or approve a research formulation.

`required_source_keys` requires SITE, PRODUCT, CALENDAR, INVENTORY (site/product),
FORECAST, FORECAST_SELECTION (site/product), LOT, SUPPLY, COMMITMENT, ROUTE, POLICY,
SCOPE (organization), CAPACITY (organization) and CONTRACT (scenario-v1) entries
as applicable. Additional upstream history/input dependencies must also be carried
from the forecast handoff. Inventory tokens must cover newly added lots and
eligibility/expiry/receipt-reconciliation changes, not just quantities. SCOPE and
CAPACITY cover complete membership, explicit exclusions, routes, reserves,
coefficients and limits, including additions not visible in a prior member list.
FORECAST_SELECTION identifies the selected eligible result/input basis for each
series, so replacing a forecast cannot evade detection merely because the old
immutable forecast record still exists.

The schema proves structural completeness, not authenticity. The #30 loader must
capture an internally consistent database view, verify source hashes against
actual records, incorporate complete upstream documents, bind selected demand to
the frozen forecast/assumptions and reconcile receipts with outstanding supply.
Source references supplied by an untrusted client are not evidence of any of this.

## 3. Time, baseline and transfer events

All seven-day series use the shared planning timezone. Convert timezone-aware
availability instants to that calendar once; retain the instants and calendar
version. Transit_days is a simulated local calendar-day offset, not a claim of
24-hour driving time across daylight-saving changes. No intraday travel schedule
or actual dispatch is modeled.

Baseline = existing physical stock + outstanding external confirmed arrivals −
existing dated outbound commitments, followed by local service under BD-48/43/44.
Uncertain forecast donations, offers and proposed transfers are absent from the
baseline. Do not represent an already-received amount again as future supply.
Existing reservations are represented by their dated commitments exactly once;
opening stock must not already have their quantities subtracted.

Candidate transfer row, defined for #24/#25 output contracts:

```text
origin_site_id, destination_site_id, product_id, origin_lot_id,
quantity (strict positive integer), route_id,
dispatch_on = allocation_start,
arrival_on = allocation_start + route.transit_days,
use_on (explicit service date inside the allocation window)
```

Several rows may split a lot across recipients/use dates; their total cannot exceed
its dated availability after existing commitments and protected local use. Frozen
external supply arriving by dispatch may provide stock, subject to the same checks.
Decision-generated inbound transfer stock never provides stock for another row.

On dispatch day, process external confirmed arrivals and exclusions; account for
fixed commitments and decision outbound debits jointly before local service.
Same-day planned arrivals may serve their destination that day. They are eligible
for local service only, never outbound dispatch in the same batch. Earlier-day
service and commitments have already reduced the lot balance. Other days follow
BD-48 with their relevant arrivals and existing commitments.

Require dispatch ≤ arrival ≤ use, use within the allocation window, eligibility at
dispatch/use, and use ≤ stated expiry day. Unknown/held/ineligible stock cannot be
made eligible merely by moving it. An arrival after the window cannot be useful;
an arrival on day two cannot repair day one's unmet demand.

Planned inbound events must remain separately labeled SIMULATED_TRANSFER in the
candidate replay adapter; they must not be relabeled actual confirmed supplies.
The present projection-v1 input accepts ON_HAND and external CONFIRMED supply
only. #24/#25 must implement the separately typed conditional event adapter (or a
new projection version) for candidate replay. No adapter exists in this task.

## 4. Local service, donor protection and useful transfers

For each site/product/date, serve dated rounded demand under hard FEFO and record
unmet once. Use existing per-day exact upward rounding; never round a window sum
or invent missing demand. Physical, eligible and transferable quantities differ.
Expiry excludes use without deleting/debiting physical records.

For every sending beneficiary i and product p, let baseline_service[i,p,d] be the
no-decision-transfer baseline, and candidate_service the projected candidate.
Require, for **each of all seven dates**:

```text
candidate_service[i,p,d] >= baseline_service[i,p,d]
candidate_eligible_end[i,p,d] >= configured_reserve_floor[i,p,d]
```

This protects attainable service without inventing fulfillment where the baseline
already has a shortage. Every positive sender must satisfy its reserve floors;
the floors apply after service, not to expired/held physical stock. Hubs must also
retain their configured reserve floors if they send. A node already below its
floor can receive or remain idle; it cannot send an infeasible quantity. A zero
transfer candidate does not become infeasible solely because an idle node cannot
meet demand or its aspirational reserve. Invalid existing commitments remain an
input conflict, even for a zero-transfer candidate.

For each receiving site/product, compare candidate and no-transfer service over
the selected allocation window. Require:

```text
sum(incoming transfer quantities)
    = sum(candidate_service[d] - baseline_service[d] over allocation window)
candidate_service[d] >= baseline_service[d] for each protected service date
```

Use the final joint candidate, not independent per-transfer marginal benefits.
Every incoming unit must produce an additional unit of local service inside the
window; shipment counts alone do not establish fulfillment. Movement may rearrange
which lot serves demand, but cannot create service beyond demand, sacrifice prior
service or merely move future buffer stock. Positive losses remain explicit slack.
This is the operational usefulness test selected in BD-51; it does not decide the
still-deferred numerical per-transfer expected_benefit field (OPEN-02).

## 5. Hard FEFO and exclusions

Local service consumes eligible same-product lots in ascending expiry order;
declared non-expiring lots follow all dated lots. Ties use availability instant,
then lot UUID. Unknown expiry is unavailable.

For transfers, hard FEFO applies to otherwise interchangeable available source
stock for the same origin, destination, product, dispatch/arrival/use dates. A
later-expiring lot cannot be sent while an earlier interchangeable lot remains
available for that same use. Allocation to other recipients, fixed commitments,
dated protected local service and reserves must have explicit quantities/witnesses;
they cannot be asserted as blanket exclusions. Both methods get identical rules
and candidate/exclusion identity; FEFO is never a soft cost preference.

Record excluded candidate quantities with a stable reason and relevant IDs/dates:
NOT_ARRIVED, EXPIRED_AT_DISPATCH, EXPIRED_BEFORE_USE, HELD, INELIGIBLE,
UNKNOWN_ELIGIBILITY, UNKNOWN_EXPIRY, FIXED_COMMITMENT, PROTECTED_LOCAL_SERVICE,
RESERVE_FLOOR, ROUTE_DISABLED, MODE_OR_ROLE_FORBIDDEN, LATE_FOR_USE,
OUTSIDE_WINDOW and SAME_BATCH_INBOUND. Earlier expiry before receiver use is a
valid non-interchangeability reason; an arbitrary preference for a newer lot is
not. Capacity, service and protection witnesses are independently checked in #25.

## 6. Capacity, conservation and movement costs

For product p, h[p] is the explicit positive integer handling coefficient and q is
a physical-unit quantity. All arithmetic is integer; never add bottles to meals
as a physical-stock KPI. Shared handling intentionally has a separately labeled
basis. For every candidate:

```text
route handling  = sum(q * h[p] on route) <= route.handling_capacity
received[d]    = sum(q * h[p] arriving at site on d) <= site.receiving_capacity[d]
batch handling = sum(q * h[p] across all transfer rows) <= batch_handling_capacity
movement cost  = sum(q * route.unit_cost_ticks[p])
```

Each moved unit counts once toward the shared shipment-handling budget; receiving
capacity is a separate constraint on that same movement. This does not claim a
two-ended dock-labor, vehicle-routing or truck-trip model. No fixed trip fees,
currency conversion or external purchase are inferred. Choose smaller integer
units/coefficients explicitly if fractional physical handling would otherwise be
needed. Exact capacity equality is feasible; one unit over is infeasible.

Availability and lot conservation must hold jointly across all rows, local service
and existing commitments. In a candidate movement, source debit equals destination
arrival quantity by original lot lineage. Quantities in transit remain accounted
for; they are not simultaneously at both sites. No self-transfer, hub destination,
disabled/missing route, mixed-unit movement or same-batch relay is allowed. Zero
capacity/resources/routes generally yield a useful zero-transfer shortage result.

Schema fields are individually int64-bounded; Python identity code does not prove
CP-SAT expression/objective safety. #10/#24 must bound every product, sum, cost and
coefficient before solver construction and reject overflow without saturation.

## 7. Canonical identity, replay and current freshness

`freeze_scenario` revalidates the whole model and produces canonical JSON and
SHA-256 over its UTF-8 bytes. It never accesses a database or model. Generated
scenario/execution/attempt IDs, actor, created/generated time and job status belong
outside this package and hash. IDs identifying frozen *source* inventory snapshots,
forecasts, policies and calendar versions stay inside and affect identity.

- Object keys: sorted, compact separators, UTF-8, no NaN/Infinity or float numbers.
- Set-like collections: sort sites/products/routes/forecasts/exclusions by UUID;
  membership IDs by UUID; series by site/product; source manifest by kind/key;
  lots and commitments by UUID; reserves by product/date; capacities by date;
  route costs by product. Reject duplicate semantic identities.
- Dated demand is chronological and complete, not arbitrarily reordered. Ordered
  explanatory assumption lists retain order. Policy/assumption/forecast document
  arrays use the ordering specified by their own upstream schema.
- Dates are ISO calendar dates. Availability instants normalize to UTC ISO times.
  UUIDs are canonical strings. Exact Decimal demand is a normalized signed
  coefficient/exponent string, e.g. 10 → "1e1"; equivalent scales/negative zero
  have one identity. Noninteger values in opaque documents use schema-defined
  exact strings/rationals, never binary JSON floats. Such documents must already
  be canonical; duplicate keys/noncanonical text are rejected.
- JSONB storage may reorder object keys. On load, validate and run this codec again
  before comparing the stored hash. Do not hash raw database-driver serialization.
- Same inputs give the same hash. Changing operational values, scope/exclusions,
  mode, assumptions, policy/forecast bytes, version/content references, calendar,
  reserve/capacity/cost or contract version changes the hash. Changing mode is a
  new scenario, not a different method on the same comparison.

A comparison binds one scenario hash and schema version to both method requests;
method and solver execution settings/results belong to separate versioned result
records. The objective/policy used by a method must match the embedded policy;
solver settings belong in result/reproduction identity and cannot alter the common
operational feasible region silently.

`assess_freshness` validates the historical fingerprint and compares an explicitly
supplied complete current dependency manifest. It reports CHANGED, MISSING and
ADDED tokens, and window_elapsed when the explicit evaluation date is after the
one dispatch date. For simulated fixed-anchor work, pass that simulation date;
for current real-date evaluation use the shared planning calendar. No default
system-clock lookup or implicit latest-record fetch occurs.

Relevant changes include stock/eligibility/expiry, reconciliation/commitments,
confirmed supply, forecast selection and its source history, roles/calendars,
membership/exclusions, reserves/capacity/routes/cost, active selected policy/
assumptions and contract version. A caller must enumerate newly relevant members
and updated scope/selection tokens. An incomplete current read cannot establish
freshness. Comparison helpers do not authenticate references or guard concurrent
database writes; #30/transaction owners must capture/check versions atomically.

Stale or archived results remain inspectable and replayable from their original
bytes. Current-recommendation state cannot silently adopt changed source values.
Replanning creates a new scenario. Busy/unavailable compute does not alter saved
inputs or make a read initiate work. Archival is metadata outside the hash; it
does not delete evidence. No dispatch, approval or reservation is authorized by
being fresh, and a P0 review event changes no stock.

## 8. Worked acceptance cases

All values below are simulated single-product physical units unless handling is
explicitly stated. Other dates have explicit zero demand/reserve. They are small
reduced-scope fixtures, not the full six-beneficiary research demonstration.

| Case | Inputs / proposed movement | Expected |
|---|---|---|
| Hub permitted | HUB_ONLY, hub 10, receiver day-1 shortage 5, route delay 0, send 5 | Feasible if capacities ≥ 5h; service gain 5. |
| Pantry forbidden | Same, origin is pantry in HUB_ONLY | Reject MODE_OR_ROLE_FORBIDDEN even with surplus. |
| Pantry permitted | HUB_AND_PANTRY, donor 20, own day-1 demand 10, all-day reserves 5; send 5 | Donor serves 10 and ends ≥ 5; receiving gain must be 5. |
| Later donor need | Donor 20, own day-1 need 10 and day-5 need 10; send 1 in two-day window | Reject: day-5 service falls 10 → 9 under BD-49. |
| Existing donor shortage | Donor 5, own day-1 need 10; send 1 | Reject: service falls 5 → 4. Zero transfer remains a shortage result. |
| Reserve equality | Donor 20, own need 10, reserve 5; send 5 / send 6 | First passes donor checks; second leaves 4 and fails. |
| Reserve already unattainable | Stock 3, reserve 5, no movement / send 1 | Idle is allowed; positive sending fails reserve. |
| Expiry equality | Arrive/use D, expiry D | Date check passes; D+1 use fails. |
| Late arrival | Receiver needs 5 on day 1 only; delay 1, send 5 | Reject useful-transfer equality: gain 0, incoming 5. |
| Later service in window | Need 5 on day 2, delay 1, two-day window, send 5 | Temporal/usefulness checks pass. |
| Beyond window | Need 5 on day 5, two-day window, send 5 now | Reject BD-51 even though later need exists. |
| FEFO | Same eligible origin/use: early lot 3, late lot 5; send 4 | Consume/send early 3 before late 1, with explicit local-use accounting. |
| Non-interchangeable expiry | Early lot expires day 1; use day 2; later lot expires day 3 | Earlier lot excluded EXPIRED_BEFORE_USE; later lot may be used. |
| No relay | Hub → A supplies 5; A → B tries to reuse those 5 in same batch | Reject SAME_BATCH_INBOUND even with zero-day routes. |
| Capacity equality | Product h=2; receive q=5; receiving/route/batch limits 10 | Exactly 10 handling units passes; q=6 needs 12 and fails. |
| Shared products | q(meal)=3,h=2; q(bottle)=4,h=1; batch limit 10 | 6+4=10 handling units; not 7 physical "items" as stock KPI. |
| Movement cost | q=5, route cost 3 ticks/unit | 15 labeled cost ticks, independent of h. |
| Duplicate stock | A received amount appears on hand and also as outstanding supply | Loader rejects inconsistent source state; pure shape validation alone cannot prove it. |
| Stock correction | Source lot or inventory version changes after capture | Current recommendation stale; historical bytes/replay stay unchanged. |
| New membership | Add a relevant lot/site or change selected forecast; old records remain | Updated membership/inventory/selection token or added reference makes current check stale. |
| Mode/policy/input change | Change HUB_ONLY to HUB_AND_PANTRY or change reserve/policy | New scenario identity; paired methods cannot use different hashes. |
| Empty network resources | Zero usable stock/capacity, positive demand | Zero transfer with explicit unmet, absent contradictory existing commitments. |

## 9. Ownership and remaining integration

- #24 builds the shared feasible region, dated decision-event replay, hard FEFO and
  protection/capacity witnesses against this contract for both methods.
- #25 independently reconstructs/checks candidates; it must not merely call the
  solver builder or the same projection as its sole oracle.
- #9/#10/#26/#29 finalize and qualify forecast/research-policy payloads. Opaque
  embedding does not complete those dependencies.
- #30 implements consistent source capture, immutable JSONB/result storage,
  verified hashes, archive/access/current-staleness behavior and transaction checks.
- #12/#32/#33 own public errors/types, saved HTTP reads and authorization/proxy.
  Internal types here are not public OpenAPI contracts.
- Independent review, integration/merge and full product acceptance remain
  separate gates. No solver, API, database migration, dispatch or supplier work
  is implemented or authorized by this contract.
