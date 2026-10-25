# PantryPulse OR mathematical specification

**Draft 1.1 • repository refresh October 24, 2026 America/New_York • proposed implementation contract**

Revision scope: repository status and integration provenance only. The equations, provisional mathematical choices, numerical bounds and independently enumerated expected results are unchanged from Draft 1.

This document defines an executable local formulation for the full first draft of PantryPulse's OR service. It resolves missing details with explicit provisional decisions authorized by the user on October 24. These are project choices, not claims that earlier backend OPEN topics were already resolved. Implement the companion engineering design and Codex specification with this mathematics; retain every `OR-DEC` identifier in the code and tests.

Authority: explicit user instructions, V5, compatible backend decisions, then these provisional choices. Existing accepted decisions remain binding. This package does not resume supplier planning or hosting/model setup. It describes a deterministic, simulated, single-dispatch-batch allocation problem, not vehicle routing, stochastic optimization or an exact reproduction of the research paper.

## 1. Inspected project state

| Ref | Reviewed SHA | Finding |
|---|---|---|
| `main` | `f3946c726e53fa546be1400d80ab717fcb2c3468` | PR #51 integrates forecasting, review fixes and design lab; domain OR/persistence still absent |
| `forecasting` | `bed08544e3dc9b00499224806d92dd8f437f0644` | Original PR #49 remains open, but its offline core is integrated into main through #51; use corrected main |
| `VP` | `b82f85f2f7b43f05df5ab0ef033c9bf0e8b28b38` | Documentation-only; now diverged two commits each way from main; no OR code |
| `codex/vercel-prototype-preview` | `81387fe8d7ca97774a61425c97d75a982b1ab1be` | Two commits ahead of reviewed main; isolated frontend-preview setup and narrow V5 exception, no backend/OR change |
| `be/ready-1-6` | `03406d9d2d16168a09dd12fafcdc79e6bf9e9b99` | Already an ancestor of main; helpers merged through PR #7 |
| `be/01` through `be/06` feature branches | Current GitHub branch heads inspected by comparison | Individual helper changes already represented by merged/refactored main; do not replay older versions |

The repository V5 Markdown remains authoritative; the supplied DOCX is the earlier reading copy and was not refreshed or changed. Main has advanced two commits since `ca5909b`: review-fix integration `62ff71c` and merge `f3946c7`. Main now contains experimental forecasting schemas, handoff and one-series inventory projection. These schemas and handoff are byte-identical to the reviewed forecasting branch; they remain internal experimental contracts, not public SQL/HTTP schemas. Public publication, jobs, complete operational scenarios and OR remain unimplemented.

PR #51 fixes the moving-average calculation before the existing daily ceiling, preventing a constant series from becoming an artificial extra unit. It also fixes held-out truth basis accounting without relaxing training proxy authorization. Preserve these fixes; no demand-rounding rule or OR equation changes. V5 adds the isolated optional 3D design-lab exception; its review-candidate wording still predates the merge and is historical status. `VP` retains useful mode/frozen-input clarifications; its older BD-30 topology references map to V5 BD-41, while main BD-30 remains observability. The preview branch's narrow frontend-hosting exception does not resume backend/model hosting. Recheck refs before implementation.

## 2. Process definition

1. Validate source completeness, ownership, units, versions and numeric bounds.
2. Freeze forecasts, daily demand choices, stock, commitments, confirmed arrivals, routes, capacities, vulnerability policy and explicit transfer mode.
3. Run the no-new-transfer dated simulation; store baseline service/unmet/expiry.
4. Build eligible source-product-destination candidates with exclusion reasons.
5. Optimize route quantities using the common physical model and the selected objective.
6. Derive lot packing and daily service exactly, with hard FEFO.
7. Independently replay the returned shipments, verify constraints and recompute metrics/objective.
8. Commit validated outcomes separately for the two methods and construct their comparison.

A shipment is a physical assignment from a particular original lot. A delivered quantity is not automatically fulfilled demand. Fulfillment is the amount consumed by the dated service process. Allocation never calls a forecasting provider and never posts stock movements.

## 3. Provisional decision register

Each row is **SELECTED FOR DRAFT 1**, not a retroactive accepted BD decision. Code marker: `# OR-DEC-001 [PROVISIONAL]: ...; docs/optimization/01_OR_Mathematical_Specification.md#...`. Export `decision_ids` and `policy_version` with scenarios/results. A later change creates a new policy/schema version and scenario; never reinterpret saved results.

| ID and related OPEN topic | Selected concrete choice | Why and reconsideration trigger |
|---|---|---|
| OR-DEC-001 · 06/21 | One operational timezone per network in v1; explicit IANA zone; seven local dates; arrivals then expiry then batch dispatch on day 1 then daily service. Expiry D prohibits use on D; unknown expiry unavailable | Clear executable clock. Revisit for mixed-zone networks or time-of-day receipt/expiry modeling |
| OR-DEC-002 · 19/21/22 | One dispatch batch before day-1 service; route ETA is an explicit integer day offset 0–2. Allocation window H is explicitly 1–3 days. No silent window or transfer-mode default | Bounded scheduling with actual late-arrival accounting; revisit for multiple dispatches |
| OR-DEC-003 · 21 | A sending beneficiary must cover its full seven-day demand and explicit end-of-day reserve without any proposed inbound transfers. No-action already failing protection makes it ineligible to donate that product | Conservative donor protection; revisit for authorized shortage-sharing or shorter reserve policy |
| OR-DEC-004 · 21/22 | Fixed loading order per source/product: descending ETA, then destination UUID. Each route packs eligible lots by expiry, availability, original lot UUID. Local service uses the same deterministic FEFO key | Exact hard FEFO with a tractable model. Loading order restricts lot assignments and can affect outcomes; revisit with alternative-order sensitivity or joint dispatch scheduling |
| OR-DEC-005 · 04/09/21 | Optimize free stock only. Freeze disjoint physically on-hand usable, reservation, fixed-commitment and held quantities; protected quantities cannot fund new shipments or local free service. Future confirmed arrivals serve locally but cannot be exported in this batch | Avoid double counting and inventing future dispatchable stock. Revisit with complete commitment event simulation |
| OR-DEC-006 · 23/25 | Research defaults: lambda=1, beta=1/2, two attribute coefficients 1/2 each, AP threshold 3/4, RP threshold 1/4, allowed AP and RP shares 1/4 each, both penalties 1 | Transparent demonstrable baseline; all are provisional and sensitivity-tested, not values attributed to the paper |
| OR-DEC-007 · 23/24 | One RP group per product, all included positive-target beneficiaries including self; each active group has at least two members. AP/RP excess averaged over active products; W remains a sum over goals | Resolves category aggregation without changing BD-20. Revisit before alternative peer groups |
| OR-DEC-008 · 23/24 | Classical uses equal ordinary weights and the same beta blend; vulnerability/AP/RP absent. Both methods have 0.01 normalized-cost and 0.01 normalized-waste coefficients | Controlled comparator and explicit trade-offs; revisit when domain owners supply conventional weights |
| OR-DEC-009 · 19/20 | Canonical JSON with exact decimal strings/rational integers, sorted identity arrays, SHA-256 and immutable full payload; method-independent operational hash and separate policy/settings hashes | Reproducible inputs; revisit only via versioned migration |
| OR-DEC-010 · 12/14/16/19 | Forecast adapter accepts committed per-series results, actual provider, source literal, estimate kind and explicit central/conservative choice. Convert legacy float using shortest round-trip decimal string and disclose conversion | Branch compatibility without claiming recovered precision. Revisit when upstream numeric contract lands |
| OR-DEC-011 · 30/33/35 | PostgreSQL admission/leases plus a supervisor and terminable child process per method; one shared expensive-work slot; sequential pair; manual retry | Matches accepted runtime architecture without a new queue vendor; reconsider only with actual shared executor requirements |
| OR-DEC-012 · 04/19/25/29 | PostgreSQL immutable OR input packages, policies, scenarios, jobs/attempts, per-method results, transfer rows, check reports and reviews; upstream ledger remains authoritative | Full OR persistence without inventing a second stock ledger; reconcile table ownership if upstream lands first |
| OR-DEC-013 · 02 | Show plan/site/product/date before-after impact and per-transfer rationale; omit numeric per-transfer benefit | Useful explanations without arbitrary additive attribution; revisit only for an explicit counterfactual feature |
| OR-DEC-014 · 31 | Presenter session with server-side hashed opaque token; same-origin proxy; backend checks session and mutation CSRF/origin; saved synthetic reads public | Concrete local demo security design; reuse equivalent existing auth rather than replace it |
| OR-DEC-015 · 20/30 | Old results remain readable; current operational requests require current revision token. Explicit historical replay uses frozen data and is labeled historical | Separates reproducibility from stale recommendations |
| OR-DEC-016 · 29/30 | Comparison ends SUCCEEDED, PARTIAL or FAILED; each method has independent outcome. Persist first validated result even if partner fails; never substitute methods | Honest partial results; revisit for future product requirements |
| OR-DEC-017 · 22 | Integer handling units, explicit product coefficients 1–1000, route load limits, per-day receiving limits, source handling limits, one global batch handling budget, optional simulated transport-cost budget | Joint product feasibility; no guessed meal-to-bottle conversion |
| OR-DEC-018 · 24/35 | Initial bounds: 12 beneficiaries, 2 hubs, 2 products, 256 original lots/confirmed arrivals total, H≤3, 7 forecast days, goal target≤100,000; every constructed integer expression must fit below 2^60 in absolute worst-case activity | Fast first draft with numerical headroom; reject unsupported scope explicitly, never silently truncate |
| OR-DEC-019 · 23/34 | Treat local equation proofs/enumeration and paper adaptation mapping as a pre-solver build gate. No claim that a citation, this draft, or prior primitive tests passes it | Preserves V5 research gate; implementer completes evidence before complex solver code |
| OR-DEC-020 · 29/32/36 | Provide an explicit SIMULATED immutable-input publication path and CLI for full OR integration tests. LIVE input requires real committed upstream read adapters and revision checks | The OR service can be complete and testable before upstream modules merge, without passing fixture data off as live integration |

Explicit inputs, not hidden defaults: timezone, transfer mode, H, per-site/product reserve vector, capacities, handling coefficients, cost units and conservative buffers. Seed files set these values; request models do not guess them. Null cost budget means no hard cost budget; zero means zero spending. Unknown fields are rejected.

## 4. Sets and input quantities

Let S be sites, B⊂S beneficiaries, P products, T={1,…,7}, W={1,…,H}. Each product has one base unit. Each site has a fixed HUB/BENEFICIARY role. Let L be original free on-hand lots and A be confirmed arrival lots. Each lot has product p, source site s, integer free units Q, availability day a, expiry day e, eligibility, unit and immutable source revision. Unknown expiry, held/unknown eligibility and incompatible units cannot enter the usable model.

For every physical on-hand lot freeze `physical = free + reserved + committed + held`, using disjoint nonnegative components. A receipt already represented in on-hand cannot also be a confirmed arrival; enforce source-line identity uniqueness. Protected components remain visible in reconciliation, but are excluded from free-flow conservation. Blocked commitments must be external to the included forecast-service obligations. If a reservation/commitment also fulfills included local demand, reject `COMMITMENT_SERVICE_OVERLAP_UNSUPPORTED` until an explicit fixed-service trajectory is supplied by a later policy version; do not count that demand as unmet merely because its committed stock was quarantined. If commitments cannot be resolved into disjoint blocked quantities, reject input; do not guess or subtract twice. This is a conservative v1 treatment, not full fulfillment of future commitments.

Demand d[s,p,t] is nonnegative integer scenario demand. For each selected forecast value, apply the explicit demand multiplier and central/conservative rule, then ceil **each date once** using BE-03. Preserve source literal and unrounded final value. A conservative point uses actual upper quantile when supplied, otherwise an explicit buffer; missing upper quantile and absent buffer is an error. Donation predictions remain separate contextual outputs and never add inventory. Full required forecast publication rules must be enforced upstream, including any required donation coverage.

Goal r[i,p]=Σ(t∈W)d[i,p,t]. Groups G[p]={i∈included B:r[i,p]>0}, N[p]=|G[p]|. All zero-target goals have f=u=q=0, ratio null, flags false and no denominator membership. N=1 is unsupported for the paired scenario; N=0 contributes no research group. Explicit partial scope lists exclusions; missing data is never an implicit exclusion.

Initial d and future supply dates share the network's chosen timezone. An eligible confirmed arrival on day t enters before that day's expiry/service. Proposed shipments leave source on day 1 and arrive on day 1+ETA; ETA must put arrival within W. They preserve original expiry and origin lineage. Source candidates contain only original on-hand stock available at snapshot; no confirmed future lot or planned incoming shipment can be re-exported.

## 5. Baseline and route decision variables

Run the deterministic daily simulator with all new shipment quantities zero. Store baseline `served0`, `unmet0`, expiry and end stocks. This is the operational reference, not an alternative primary method.

For each allowed source s, beneficiary j, product p, define integer y[s,j,p]≥0, bounded by both source free units and receiver's no-action unmet demand within W. Enforce Σ_s y[s,j,p]≤Σ(t∈W)unmet0[j,p,t]. No self-transfer. Apply BE-02 mode/role/route permission first, then eligibility/ETA/product rules. In HUB_ONLY, beneficiaries still serve their own local demand but no beneficiary-origin variable exists. Explicitly record why excluded candidates were removed.

The y bounds prevent oversupplying baseline need but do not prove dated usability. Additional constraints below require every shipped unit to be consumed within W. A route with no eligible source lots has y=0. Do not create a fake stock variable to make an impossible shipment feasible.

## 6. Exact loading and hard FEFO

For each source/product, order routes by descending arrival offset then destination UUID. This is a frozen loading policy, shared by both methods. For a route k with requested load y_k, set residual request R_0=y_k. Visit all original source lots compatible with this route in ascending `(expiry, availability, lot UUID)` order. Let B_l be its free balance after earlier routes:

\[
x_{l,k}=\min(B_l,R_{l-1}),\quad R_l=R_{l-1}-x_{l,k},\quad B'_l=B_l-x_{l,k}.
\]

Require R_end=0. Noncompatible lots are skipped with a specific reason: not originally dispatchable, wrong product/unit, expires by arrival, held/unknown eligibility, or source/route mismatch. Deterministically create destination sublot (original lot, route) of size x, arrival day and original expiry. At the source retain Q_l−Σ_k x_lk.

This enforces FEFO at each loading event: if a later compatible lot contributes, every earlier compatible lot with positive balance must have been exhausted by that event. Proof: min(B,R) takes all B whenever remaining demand exceeds B; reaching a later lot with residual demand implies exhaustion of every earlier one. There is no objective-dependent loophole. Packing all lots for each route also proves aggregate linkage y_k=Σ_l x_lk and source balance conservation.

**Limitation:** the fixed route order selects a subset of lot-to-route assignments. It can alter the achievable allocation; it is not a claim of optimization over all loading schedules. Include its version/order in hashes, explanations and sensitivity evidence. Test an earlier-expiring lot unusable on a long route but usable on a short route. Changing route order creates a different operational policy/scenario.

## 7. Exact daily service process

At each site/product/day: add confirmed arrivals and planned received sublots due that day; remove free balances expired on or before that day; on day 1 apply new outbound loading before service; then serve demand greedily in FEFO order. For ordered eligible local lots h:

\[
R_0=d_{spt},\qquad c_{h,t}=\min(B^{available}_{h,t},R_{h-1}),\qquad R_h=R_{h-1}-c_{h,t}.
\]

Record `served=d−R_end`, `unmet=R_end`, and remaining free balances. There is no backlog. Lots unavailable before t cannot be consumed or expired early. Expiry loss equals the entire remaining free balance when its expiry day is reached, once. A receipt due on/after its expiry contributes expiry, not usable service; validate source data and report that exclusion.

For every lot/sub-lot and stage, balance_in + due_arrival = consumed + dispatched + expired + balance_out. Proposed transfer debit and credit have equal quantity and shared lineage; receiver credit occurs only on arrival. The total system balance includes in-transit units between departure and arrival. Blocked components reconcile separately to physical source counts and do not disappear from audit.

For every proposed received sublot require Σ(t∈W)c[h,t]=x[h] and expired_within_W=0. Thus new transfers cannot be justified by discarded, post-window or unused units. Main projection still runs all seven days. Source residual and receiver consumption are linked to the same x values, not separately optimized estimates.

Use deterministic `min` equalities, not only `served≤available` inequalities. Otherwise the optimizer could withhold service to manipulate RP or penalties. By induction on routes, days and lot order, fixing y uniquely determines all x, service, expiry and ending balances. This fact makes an independent simulator an exact checker for the physical model.

## 8. Donor protection and capacities

For each possible sending beneficiary/product, compute a second protection simulation with the same outbound vector and confirmed arrivals but **no proposed inbound transfers**. Let h[s,p]↔Σ_j y[s,j,p]>0. If h is true, require served_protected[s,p,t]=d[s,p,t] and end_free_protected[s,p,t]≥reserve[s,p,t] for all seven days. Reserve is an explicit integer floor after service and after expiry. If no-action cannot meet those requirements, forbid sending that product. Hubs have explicit reserve floors and any frozen own operational demand; hub demand is not a beneficiary fairness goal.

This is deliberately conservative: local safety cannot depend on another recommendation or on predicted donations. Original stock exported in this batch is never replaced by an unconfirmed purchase. It does not implement emergency sharing from already-short donors.

With declared integer handling coefficient h_p and per-unit route cost c_sjp:

\[
\sum_p h_p y_{sjp}\le K^{route}_{sj},\quad
\sum_{j,p}h_p y_{sjp}\le K^{source}_{s},\quad
\sum_{s,p:\,arrival(s,j)=t}h_p y_{sjp}\le K^{recv}_{jt},
\]
\[
\sum_{s,j,p}h_p y_{sjp}\le K^{global},\qquad
C=\sum_{s,j,p}c_{sjp}y_{sjp}\le budget\quad\text{when budget is supplied}.
\]

Capacities refer to new batch handling/receiving; frozen commitments/confirmed receipts consume capacity upstream and the package supplies the residual capacity, with original capacity/consumption provenance. Validate `residual = original − fixed_used ≥ 0`. Do not subtract again. Storage capacity is represented by explicit end-of-day free-stock capacity per site in the same handling units, checked after service for all seven days; frozen blocked stock is already deducted. Intraday peak storage is outside v1 and disclosed. Product counts remain separate; handling units are a declared engineering conversion, not nutritional equivalence.

## 9. Goals, vulnerability and integer formulation

For positive goal (i,p): f=Σ(t∈W)served[i,p,t], u=r−f, δ=u/r. `f` derives from simulation and lies in [0,r]. Attribute a_ik is a prepared score on a 0.0001 grid in [0,1], with at least two documented attributes. Coefficients c_k are nonnegative integer percentages summing to 100. Lambda is on a 0.01 grid in [0,1]; beta on a 0.01 grid in [0,1]. Default two c values are 50 each. Preserve raw/source notes, score preparation and SIMULATED labels.

\[
v_i=1+\lambda\sum_k c_k a_{ik}/100\in[1,2],\qquad z_{ip}=v_i\delta_{ip}.
\]

Write reduced v=n_v/d_v. Accepted scale S=10,000; q=floor(S z). Encode using integer inequalities, not floats:

\[
Dq\le S n_v u\le D(q+1)-1,\qquad D=d_v r,\quad 0\le q\le20,000.
\]

Classical q0=floor(Su/r) uses the same construction with v=1. W=Σ_g q_g/S and Z=max_g q_g/S; classical W0/Z0 use q0. If no goals exist, W=Z=0 by explicit construction. Report exact z and δ as rational numerator/denominator alongside computational q; the quantized value is a policy approximation with 0≤z−q/S<1/S.

## 10. AP and RP with strict equality semantics

Thresholds A and T are integer scale units, default A=7500 and T=2500. Threshold ranges: A∈[0,20000], T∈[0,20000]. For every included goal:

\[
b^{AP}_{ip}\leftrightarrow q_{ip}\ge A+1,
\]
\[
b^{RP}_{ip}\leftrightarrow N_p q_{ip}-\sum_{j\in G_p}q_{jp}\ge N_pT+1.
\]

The false branches respectively require q≤A and Nq−Σq≤NT. Equality is unflagged. RP uses the mean of the **current candidate's** group, not the baseline and not a fixed ranking of vulnerability. The strict test is on quantized weighted deficit. Separately show exact-rational flags and disagreement warnings, without silently using them in the computational objective.

Let allowed share be cap_bp/S, default cap_bp=2500, with cap_bp integer 0…10000. Counts C_AP,p=Σ_i b_AP, likewise RP. Define integer excess numerators:

\[
E_{AP,p}=\max(0,S C_{AP,p}-cap_{AP}N_p),\qquad
excess_{AP,p}=E_{AP,p}/(S N_p).
\]

Use the same RP formula. This retains exact flag fractions and cap equality; do not round a group share before applying its cap. Average excess over P+={p:N_p>0}, not over physical units. These are soft objective terms, never hard scarcity constraints. With no active products both aggregate excess terms are zero.

## 11. Complete draft objectives

Freeze cost reference C_ref=Σ over original dispatchable source/product free units × maximum allowed per-unit outgoing route cost for that source/product, using zero when there is no allowed outgoing route. This bounds any feasible C. If C_ref=0, C and qC are zero. Otherwise qC=floor(S C/C_ref). Compute waste W_p as seven-day expired modeled free units of product p, including receiver sublots and confirmed supply exactly once. Reference Q_ref,p is total modeled original free units plus modeled confirmed arrival units within seven days; excluded held/unknown-expiry resources are outside numerator and denominator and remain in exclusion/reconciliation outputs. Set qWaste_p=floor(S W_p/Q_ref,p), or 0 if Q_ref,p=0. Average qWaste over products with positive Q_ref. No physical meal/bottle sum is reported as waste units.

Let β=beta, γA=γR=1 by default, εC=εW=0.01. Gamma values are on a 0.01 grid in (0,10]; ancillary coefficients on a 0.0001 grid in [0,1]. Diagnostic ablations may set one gamma to zero only with an explicit ABLATION label. They are never published as the primary configured research method.

\[
J_R=\beta\sum_g q_g/S+(1-\beta)\max_g q_g/S
+\frac{\gamma_A}{|P^+|}\sum_{p\in P^+}\frac{E_{AP,p}}{S N_p}
+\frac{\gamma_R}{|P^+|}\sum_{p\in P^+}\frac{E_{RP,p}}{S N_p}
+\epsilon_C qC/S+\epsilon_W\,\operatorname{mean}_{Qref>0}(qWaste_p/S).
\]

\[
J_C=\beta\sum_g q0_g/S+(1-\beta)\max_g q0_g/S
+\epsilon_C qC/S+\epsilon_W\,\operatorname{mean}_{Qref>0}(qWaste_p/S).
\]

Missing-group sums above are zero, not division by zero. W is intentionally a per-goal sum; do not replace it with per-product means. Both objectives share physical constraints, ancillary coefficients, references and solver settings. Evaluate both returned plans under the same research policy for comparison. Their native objective values are method-specific and are not a universal quality ranking.

Multiply S·J by the least common multiple of its exact rational coefficient denominators, then divide all resulting integer coefficients by their greatest common divisor. Minimize that integer objective; record conversion factor. No floating objective coefficients and no shortage-first lexicographic pre-pass. Do not add a tie-break that changes the declared objective. Return feasible/objective-equivalent ties honestly.

## 12. Numerical bounds and proof obligations

Under OR-DEC-018 there are at most 24 goals, W_scaled≤480000, N≤12, |Nq−Σq|≤240000, and E≤120000. With the stated attribute grids d_v≤10^8, n_v≤2·10^8 and r≤100000, each deficit-encoding product is ≤2·10^17. Across ≤256 original lots/arrivals of at most 100000 units and route prices≤10^6 minor units, C_ref≤2.56·10^13 and S·C_ref≤2.56·10^17. All are below 2^60; expression sums still require explicit interval checking.

The coefficient grids make denominator clearing bounded: lcm(N_p) divides lcm(1,…,12)=27720, product-average divisors≤2, and weight denominators divide 10000. Thus a sufficient clearing factor divides 554400000 for S·J; the simple objective domain is far below int64 under these bounds. Generate actual interval bounds for every constraint/objective activity, not only these summaries. Reject `NUMERIC_RANGE_UNSUPPORTED` before solver construction if any signed activity reaches 2^60. Never clamp quantities or drop constraints.

Local min/max equations can be encoded by native CP-SAT equalities. Binary flags require both enforcement branches. Validate the built model before solve, then independently check every accepted candidate. Timeout/UNKNOWN is not a mathematical infeasibility proof.

## 13. Independently enumerated examples

The following were checked during this planning task with a standalone Python integer/Fraction enumerator, without OR-Tools or production checker code. They validate objective expectations, not the future CP-SAT model, full network constraints or runtime behavior.

### 13.1 AP decision-changing ablation

Two beneficiaries, one product, r=(2,3), v=(1.5,1.5), one unit supply, default thresholds/caps/beta/gammas, ancillary terms zero in this isolated test. Enumerate all integer f with f≤r and Σf≤1.

| Configuration | Unique best f | Objective |
|---|---|---|
| Full research | (1,0) | 19/8 |
| AP penalty removed | (0,1) | 2 |

### 13.2 RP decision-changing ablation

r=(2,2), v=(1.5,2), one unit supply; other isolated-test settings as above.

| Configuration | Unique best f | Objective |
|---|---|---|
| Full research | (0,1) | 11/4 |
| RP penalty removed | (1,0) | 21/8 |

These deliberately reduced scopes have explicit two-member groups; they do not satisfy the full-population demonstration by themselves. Recreate them as physical one-hub/one-day fixtures and prove identical outcomes after source, packing, capacities and checker are added.

### 13.3 Full six-beneficiary fixture

One hub, six beneficiaries in stable UUID order, two products. Each beneficiary has target 2 of each product on day 1 and zero on days 2–7; no initial beneficiary stock or confirmed arrivals. Hub has 6 units of each product; lots expire on day 8. All routes arrive day 1 and cost one SIM_CREDIT minor unit per item. Handling coefficients are meal=2 and water=1; global budget 18; individual limits nonbinding; reserves explicit zero. Prepared two attributes are equal per institution and yield v=(2,1.8,1.6,1.4,1.2,1). H=3, full scope, default objectives, C_ref=12, no expiry waste.

| Method | Meals served, institution order | Water served, institution order | Native objective |
|---|---|---|---|
| Classical | (1,1,1,1,1,1) | (1,1,1,1,1,1) | 163/50 = 3.26 |
| Research | (2,2,1,1,0,0) | (2,2,1,1,0,0) | 1393/300 = 4.643333… |

Independent enumeration found a unique optimum for each objective over 435 per-product feasible vectors and all feasible pairs. The numeric objectives cannot be compared across methods as a winner score. Both serve 12 units overall; research shifts service toward the more vulnerable institutions and leaves explicit unmet need at others. Compare common evaluation metrics and disclose trade-offs. This fixture alone does not exercise pantry donation or binding competition between products; add a pantry-surplus fixture and reduce shared capacity to exercise those paths.

## 14. Research adaptation and validation gate

Research source: Rampazo et al., DOI [10.1111/itor.70252](https://onlinelibrary.wiley.com/doi/full/10.1111/itor.70252), first publication September 11, 2026. Section 2.1.3 gives the general extension; section 3 gives its food-bank application; Appendix A defines notation and Appendix C provides worked application material. The published application solves connected periods sequentially. Our fixed proxy weights, forecast targets, explicit transfers and deterministic loading policy are local adaptations, not a reproduction. The paper's grouped allocation variables must not be confused with physical lot variables here.

Before complex implementation, write `RESEARCH-MAPPING.md`: one row per local objective/constraint family, paper section/equation reference where actually checked, deliberate deviation, units, independent oracle, and verification status. Review source equations rather than inferring them from an abstract. In particular inspect allocation linkage, inventory/expiry interpretation, weights, poverty lines and group aggregation. The exact CP-SAT formulation above is a proposal derived for this project; its correctness is established by local proofs/oracles and checker agreement, not attributed to the paper.

Gate completion requires actual checked mapping, interval proof output, AP/RP ablations, full-fixture oracle, and FEFO/packing/projection equivalence tests. This planning document does not assert the gate has passed. Codex should complete these artifacts/tests autonomously before its complex solver implementation and record any inaccessible research source as unverified instead of fabricating equation fidelity.

## 15. Required outputs and interpretations

Publish per-method native status, separate job outcome, timings/settings, objective and exact decomposition, bound/gap where available, all frozen hashes, decision IDs, lot-level shipments, daily free-stock/service/unmet/expiry/in-transit records, donor protection results and independent check report. OPTIMAL/FEASIBLE allow candidate extraction only; BE-05 grants no automatic publication permission. Forbidden native statuses produce no vector. A validated zero-transfer solution is distinct from no solution.

Compare target/service/unmet by product, worst unweighted and weighted deficits, exact and computational AP/RP incidence/excess, W/Z, cost, waste, donor impact and changed assignments. Show before/after at plan/site level plus rationale; numerical per-transfer benefit is omitted under OR-DEC-013. Quantiles/buffers are planning assumptions, not calibrated stockout probabilities. No nutrient or observed poverty metric is claimed without its own data/model contract.

Sources of technical implementation semantics: [official CP-SAT guide](https://developers.google.com/optimization/cp/cp_solver) and [official Python model API](https://or-tools.github.io/docs/pdoc/ortools/sat/python/cp_model.html). Use the repository's actual locked version and verify the selected methods on it. The custom packing, protection, numeric policy and objective are the original project design specified above.
