---
name: verify-forecast
description: "Verify PantryPulse baseline/Chronos integration, fallback, leakage and shortage projection."
---

Read PROJECT-CONTRACT.md and INVARIANTS.md. Inspect the actual provider interface and tests. Check six series, seven dated outputs, cutoff separation, gaps, duplicate policy, quantile order and actual fallback metadata. Run focused forecasting and projection tests in the assigned worktree. Force a provider failure. Use the two-day lost-sales counterexample: stock 40, demands 50 then 40 means unmet 50, not 60. Report exact commands and PASS/FAIL/UNVERIFIED. Accuracy claims require a chronological holdout and honest baseline comparison, separate from these integration checks.
