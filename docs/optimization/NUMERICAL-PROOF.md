> Ownership correction: this proof applies to OR-local simulation/model code. The inventory service is restored unchanged; persistence/publication/shared-runtime obligations are external handoffs. [Current execution scope](03_OR_Codex_Execution_Spec.md) controls implementation ownership; equations are unchanged.

# Draft 1.1 local physical and numerical proofs

OR-DEC-001–008/017–019 [PROVISIONAL], policy `or-policy-v1`, S=10000. Base `f3946c726e53fa546be1400d80ab717fcb2c3468`. These are proofs of the selected **local** formulation, independent of the paper. [Research mapping and checked gate evidence](RESEARCH-MAPPING.md).

## Loading, service, conservation and common feasibility

Fix all route quantities y. Each source/product's routes have frozen descending ETA/destination identity order. For one route, let R be remaining request and B be the compatible lot's residual. `x=min(B,R)` uniquely fixes x, then uniquely fixes `R'=R-x` and `B'=B-x`. Initially B is original free stock; each later route receives the previous residual, so stock cannot be reused. Induction on lots/routes gives unique assignments or a nonzero final request, which is infeasible. Reaching a later compatible lot with positive R means each preceding compatible lot was exhausted. An earlier-expiry lot incompatible with the route is excluded rather than violating FEFO. The oracle exhaustively tests tiny stocks and requests, including an early-expiry/long-ETA exception.

Sum each packing equality: outgoing source debit equals the sum of destination sublot quantities and no lot debit exceeds its original free stock. Each sublot retains original lot/route identity and expiry; original free balances are the only dispatchable quantities. Neither confirmed arrivals nor received sublots enter packing, which proves no same-batch relay. Reserved/committed/held parts reconcile outside the modeled free balance and are never subtracted twice. Service-overlap commitments must be rejected at input validation.

For a date, add only supply due by that date, remove expired remaining balance once, dispatch only on date 1, and process eligible balances in frozen FEFO order with `c=min(B,R)`. Each step uniquely fixes remaining stock and remaining demand. Induction on dates/lots fixes all service, lost demand, expiry and end balances for given y. Therefore neither objective can withhold eligible service to game relative flags. Incoming quantity is not fulfillment: a day-2 arrival cannot undo day-1 lost demand. The hand fixture stock40/demand50,40 has unmet10,40 (total50). Each received sublot must be fully consumed by H with zero within-window expiry; residual/new inbound cannot justify future service beyond W.

At every stage, initial modeled stock plus due arrivals equals service plus expiry plus end stock plus in-transit stock. A transfer changes location/transit composition, not system quantity. Future arrivals remain outside on-hand until due. Outbound original stock and incoming sublot identity must match; independent publication verification rejects mismatched lot quantities or service claims.

For every sending product, repeat the seven-day recurrence with identical outbound and no proposed inbound. Full local service and daily reserve floors in that run prove donor protection independent of other recommendations. Already failing no-action donors cannot become eligible by relying on proposed inbound. Hubs retain explicit own operational demand/reserves. Scarcity at receivers uses unmet slack, not artificial hard fulfillment requirements.

The physical feasible set is the set of y satisfying these deterministic equations, route/mode, baseline unmet inbound cap, donor and declared capacity constraints. It contains no vulnerability weights, flags or objective coefficient. Attaching either objective to the identical frozen physical build therefore leaves the same feasible region. Actual builder identity and native model/oracle feasible-set equivalence remain implementation tests, not consequences of a document hash alone.

## Exact floors, boundaries and group membership

For positive integer D, integer a and q, `D*q <= a <= D*(q+1)-1` is equivalent to `q=floor(a/D)`. Substitute `a=S*n_v*u`, `D=d_v*r`. Since 0<=u<=r and 1<=v<=2, 0<=q<=20000. The error is `0<=v*u/r-q/S<1/S`. Original exact ratios remain reportable; computational flags use q. Source literals and daily target ceilings are separate; summing after daily ceiling is mandatory.

The Boolean conditions `b=>q>=A+1` and `not b=>q<=A` partition integer q; equality is unflagged and neither branch can evade truth. For RP replace q with `N*q_i-sum(q_j)` and A with N*T. The current candidate determines every member's q and mean. For count C, `E=max(0,S*C-cap*N)` gives exactly `max(0,C/N-cap/S)=E/(S*N)`. No rounded-share shortcut is valid. Zero targets are absent from denominators; zero groups contribute zero; singleton positive-target groups are explicitly unsupported. Tests cover equality, +1, no groups, singleton rejection and candidate-dependent RP.

## Bound families and emitted-expression obligation

All signed activities must remain **strictly** below 2^60, not merely their final feasible values. For an emitted affine expression `c0+sum(c_i*x_i)` with domains `[L_i,U_i]`, compute interval endpoints by sign: `lo=c0+sum(min(c_i*L_i,c_i*U_i))`, `hi=c0+sum(max(...))`. Include enforcement expressions, min/max operands, both floor inequalities and objective. Reject at/beyond the limit before invoking CP-SAT. A generous domain cannot be justified by small feasible values. Recompute actual intervals after all constraints/objective attachments; also invoke the native model validator.

| Family | Maximum under Draft 1.1 declared domain |
|---|---|
| Positive goals | 24 |
| Per-goal q / W sum | 20000 / 480000 |
| RP N*q and sum(q), N<=12 | 240000 each; conservative difference activity 480000 |
| AP/RP count excess magnitude | 120000 |
| Reduced weight denominator/numerator | <=10^8 / <=2*10^8 |
| Deficit numerator S*n_v*u, u<=100000 | <=2*10^17 |
| D*q, D=d_v*r | <=2*10^17 |
| Conservative two-sided floor inequality activity | <4.01*10^17 (<2^60) |
| Original/supply units, 256 resources*100000 | <=25600000 |
| Cost reference, prices<=10^6 | <=25600000000000 |
| S*cost reference | <=256000000000000000 |
| Cost floor conservative difference activity | <=512000000000000000 (<2^60) |

Resource count applies jointly to original lots/confirmed arrivals. More array/route terms can widen naive domain intervals even when conservation constrains their feasible total. Therefore bounds must follow real emitted domains and shared residual chains; if conservative activities reach the limit, reject the instance rather than assuming conservation rescues numerical safety. Storage/capacity and source quantity fields also require explicit finite validated upper bounds; the table does not license unbounded BIGINTs.

For `S*J`, coefficient denominators divide the product of the 1/10000 weight grid, a product-average divisor at most 2 and lcm(1,...,12)=27720. Thus 554400000 is a sufficient clearing factor. Find the actual coefficient-denominator LCM, multiply, then divide all integer coefficients by their GCD. Positive scaling preserves order and ties; record the exact rational conversion. The independent compiler test checks equivalence and a >=2^60 rejection. No floating objective or extra lexicographic shortage pass is permitted.

The six-fixture oracle uses exact integer scoring with denominator 6000000, including the floor of `S*C/12`; all coefficients/values are integers. Its exhaustive optimum-count evidence is in [the saved report](evidence/oracle-six-beneficiary-v1.json). It is not an OR-Tools result, a physical-model validation or a runtime measurement.

## Evidence and remaining limits

`apps/api/tests/optimization/test_or_oracle.py` independently tests 12 cases, including all mathematically feasible six-beneficiary pairs, physical tiny cases, threshold/group boundaries, coefficient equivalence and dependency independence. The production checker and CP builder must be compared with these oracles. Every actual emitted activity, real paired native solve, parent-owned publication and whole-process termination require their own evidence. This proof never promotes a citation or a fixture-only result into application acceptance.
