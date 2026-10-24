---
name: research-claims-check
description: "Check that every PantryPulse statement about the EGP-PI research, fairness, forecasts and impact is accurate and labeled (FR-29, FR-30, section 19.1). Use before writing or changing README, the methodology screen, demo script, UI copy, API methodology responses, release notes or submission text."
---

## Required facts

- Citation: Rampazo, R. C., Jones, D. F., Godoi, L. F., Iamamoto, M. O., & Cantane, D. R. (2026). An extended goal programming framework incorporating poverty measures: application to food bank logistics. International Transactions in Operational Research.
- DOI 10.1111/itor.70252, first published online 11 September 2026, within the hackathon window of 23 October 2025 to 23 October 2026. ADR 0001 records the publisher and institutional evidence. Recheck the publisher page before final submission.
- The method is named `EGP_PI_INSPIRED`, a bounded research-inspired subset.
- Adapted: absolute-poverty (AP) and relative-poverty (RP) goals with reified thresholds, normalized institutional vulnerability attributes, weighted plus Chebyshev deviation, and FEFO lot constraints.
- Not reproduced: endogenous vulnerability weights, the multi-period model, the paper's full equations (8)–(20) and (21)–(38), and the paper's reported results.
- Vulnerability attributes and all demo data are SIMULATED. They describe fictional institutions, never individuals or protected traits.
- Chronos-2 and OR-Tools are supporting technology, not the eligibility basis. FoodRL is optional inspiration and P0 does not implement reinforcement learning.

## Never write

- "exact reproduction", "implements EGP-PI" without "inspired", or "the paper's model".
- Real-world outcome claims: "reduces poverty", "saves N meals", "fairer distribution" stated as fact. Use "in this simulated scenario" with the same-snapshot comparison.
- Stockout percentages or probabilities without a validated method, or quantiles described as calibrated.
- "AI approves", "auto-orders" or "dispatches". P0 is simulation and decision support only.
- A classical result labeled as EGP after a research-solve failure (FR-30).

## Procedure

1. Search the user-facing surfaces:
   `rg -n -i "egp|rampazo|itor\.|poverty|fair|equit|reproduc|saved|saves|guarantee|probabilit|calibrat|auto-?order|dispatch" README.md docs apps/web/src apps/api/app`
2. Open each hit and check it against the two lists above.
3. Confirm the runtime surfaces, or mark them UNVERIFIED where they aren't built yet:
   - `GET /api/v1/allocation-methodology` returns DOI, date, adapted constructs and limitations;
   - the methodology screen shows the date within the first 30 seconds of the judge path;
   - a forced EGP failure shows method-unavailable;
   - TEST-ELIG-01 exists and passes.
4. Report a table of check, PASS/FAIL/UNVERIFIED, file:line and the exact replacement text for each FAIL. Don't edit files outside your task's write boundary; hand fixes to the owning agent.
