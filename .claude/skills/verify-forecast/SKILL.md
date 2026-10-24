---
name: verify-forecast
description: "Verify PantryPulse V4 forecasting and projection: DEMAND and DONATION series, seasonal-naive baseline and labeled fallback, lazy bounded Chronos-2, leakage, missingness and once-only supply counting."
---

V4 authority: the section 9 and 10 V4 extensions (docs/pantrypulse/SPEC-V4.snapshot.txt) and docs/architecture/0001-v4-research-first.md. PROJECT-CONTRACT.md is superseded where it conflicts, including its three-site, six-series wording. Inspect the actual provider interface and tests, and run focused tests in the assigned worktree.

Check, reporting PASS/FAIL/UNVERIFIED with exact commands:

1. **Series shape (FR03, FR-04):** one daily series per site/product/target_type, for both DEMAND and DONATION. Derive the expected count from the seed (beneficiaries and hubs times categories times targets); don't assume six. Each eligible series gets seven dated, site-local points, or an explicit per-series status such as LOW_CONFIDENCE or insufficient_data.
2. **Targets:** DEMAND means requested units, including unmet requests. Fulfilled-only history is flagged as a censored proxy. DONATION forecasts stay separate from confirmed expected supplies and are never counted as guaranteed stock.
3. **Data handling:** reject duplicate keys and nonfinite or negative input; flag missing dates rather than zero-filling; enforce the cutoff, so perturbing held-out future values leaves the fit unchanged.
4. **Fallback and provenance (FR-05, INV-13):** force a Chronos import, load, predict and timeout failure. Each yields a persisted, labeled seasonal-naive run with its fallback reason, and the actual provider, checkpoint and cutoff are recorded. Chronos loads lazily in a terminable subprocess, never on startup or on a GET. A cached run keeps its real provider and timestamp.
5. **Uncertainty (FR-08, INV-14):** quantiles are ordered when present and null when absent, with the interval method labeled. Summed daily p90 is a conservative scenario, not a calibrated joint probability. No stockout percentages.
6. **Projection (FR-06, FR-07):** projected usable stock = eligible stock + confirmed arrivals + scenario donations + transfers-in - forecast requests - transfers-out, each supply counted once, with no double counting of reserved, ordered-but-unreceived or already-on-hand units. Report confirmed and uncertain supply separately. Use FEFO/expiry eligibility by site-local date. The lost-sales counterexample still holds: stock 40 with demands 50 then 40 gives unmet 50, not 60. First shortage day is the earliest projected deficit, and overlapping cumulative deficits are never summed.
7. **Accuracy claims:** only from chronological rolling-origin backtests against the seasonal-naive baseline on the same windows (MAE, bias, and WAPE where the denominator is valid). Integration checks above never count as accuracy evidence.
