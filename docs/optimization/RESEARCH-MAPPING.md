# Draft 1.1 research mapping and pre-solver gate

Checked October 24, 2026 America/New_York, at base `f3946c726e53fa546be1400d80ab717fcb2c3468` plus this task's working tree. Research lane for [#10](https://github.com/gbw30/PantryPulse/issues/10)/[#38](https://github.com/gbw30/PantryPulse/issues/38). OR-DEC-019 remains SELECTED_FOR_DRAFT_1.

The [Wiley full text](https://onlinelibrary.wiley.com/doi/full/10.1111/itor.70252) was actually accessible and inspected, including §2.1.1–3 equations 1–20, §3 equations 21–38, Appendix A tables A.1–6, Appendix C equations C.8–19 and publisher publication metadata (September 11, 2026). No equation fidelity was inferred from an abstract. The mapping below records checked locations and **local** meanings; it is not a reproduction claim. Publisher HTML equations and prose leave aggregation/linkage and boundary details requiring an explicit local contract; no assertion that the paper supplies our physical formulation is made.

| Local family and units | Checked paper location | Deliberate local contract | Independent evidence |
|---|---|---|---|
| Fulfillment, product units | §2.1.3 (9–10), §3 (22–24), C.8–9 | Actual dated consumption, linked to original lots; no attribute allocation variables | Local packing/service proof below |
| Vulnerability, dimensionless | §2.1.2 (7), A.2/A.5 | Fixed prepared proxy `v=1+lambda*sum(c*a)`; not endogenous normalized weights | Exact Fraction profiles |
| Weighted/max blend, dimensionless | §2.1.3 (8,11–12), §3 (21,29–30), C.10–11 | Global Z; beta blend; independent AP/RP coefficients | Full fixture enumeration |
| AP, scaled deficit/share | §2.1.3 (13–14), §3 (31–32), C.12 | Strict two-way integer threshold; exact count excess | AP ablation/equality |
| RP, scaled deficit/share | §2.1.3 (15–17), §3 (33–35), C.13–19 | Current same-product positive-target group including self; strict two-way threshold | RP ablation/equality |
| Source/expiry/storage, product/handling units | §3 (24–28), A.4–6 | Deterministic lot FEFO; lost sales; expiry D unusable; no forced excess delivery | Tiny physical oracle |
| Coefficient quantization | No matching paper equation | S=10000 floor; exact rational reporting; bounded integer objective | Numerical proof/tests |
| ETA/mode/donor/handling/cost | No equivalent asserted | One batch; no relay; seven-day donor safety; explicit capacities | Local proof; production tests required |

Local-only choices include fixed thresholds/caps, per-product mean excess, equal classical weights, normalized cost/waste terms and integer rounding. All fixture attributes and resources are SIMULATED. Different method-native objective values do not establish a universal winner. The DOI supplies research provenance; proofs and independent checks supply correctness evidence for this adaptation.

## Prerequisite evidence

The actual pre-solver gate now has checked source mapping, frozen Draft 1.1 coefficients/scaling/group policy, independent exact enumeration, local FEFO/service uniqueness and same-feasible-region proof obligations. These prerequisites permit implementation against the selected formulation. They do **not** pass OR-A04's eventual emitted-model activity audit or OR-A05 native-model equivalence: those must be checked after model construction. No DB/runtime/UI/live-integration result is established by this document.

| Prerequisite | Status | Reproducible artifact |
|---|---|---|
| Actual equation mapping and deviations | PASS | Checked locations above |
| Versioned coefficient/scaling/group policy | PASS | [Mathematical spec §§9–12](01_OR_Mathematical_Specification.md), policy `or-policy-v1` |
| Independent AP and RP decision-changing ablations | PASS | [AP](evidence/oracle-ap-ablation-v1.json), [RP](evidence/oracle-rp-ablation-v1.json) |
| Six beneficiaries/two products, unique optima | PASS | [Full oracle](evidence/oracle-six-beneficiary-v1.json) |
| Loading/service uniqueness, linkage, conservation | PASS, local proof/test scope | [Proof](NUMERICAL-PROOF.md), tiny exhaustive packing tests |
| Integer bound families and objective clearing | PASS, analytic scope | [Proof](NUMERICAL-PROOF.md) |
| Every actual CP expression audited/equivalent feasible sets | UNVERIFIED at pre-solver handoff | Required in constructed model and solver tests |

Command (from `apps/api`): `/tmp/pantrypulse-forecast-venv/bin/python -m pytest tests/optimization/test_or_oracle.py -q`: 12 passed. Python 3.12.3. Ruff passes for the two oracle files. The stdlib-only enumerator has no application or OR-Tools imports (tested with AST). Mathematical fixtures are evaluated independently of production packing, projection, metrics or verifier code.

## Exact independent results

| Fixture/configuration | Unique optimum per product | Rational native objective |
|---|---|---|
| AP/full | (1,0) | 19/8 |
| AP/disabled diagnostic | (0,1) | 2 |
| RP/full | (0,1) | 11/4 |
| RP/disabled diagnostic | (1,0) | 21/8 |
| Six/classical | (1,1,1,1,1,1), twice | 163/50 |
| Six/research | (2,2,1,1,0,0), twice | 1393/300 |

The full oracle enumerates all 435 per-product vectors and 189225 feasible pairs, including underused supply; it does not assume that all supply must be dispatched. Both methods have optimum_count=1. The 18-unit handling bound matches `2*meals+water`; cost reference is exactly 12 and cost floors are computed before scoring. No hidden preference or shortage-first objective was added.
