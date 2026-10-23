---
paths:
  - "apps/api/app/services/forecasting/**/*.py"
  - "apps/api/tests/forecasting/**/*.py"
---

Forecast requested units; warn when fulfilled units are only a proxy. Reject duplicate dates and invalid numbers, preserve gaps. Seasonal naive uses the prior comparable weekday; short history uses a labeled simple fallback with documented threshold. No held-out future data in fit/scaling/imputation. Persist actual provider/checkpoint/revision/cutoff/horizon/fallback. Missing quantiles are null. Never describe raw quantiles or summed daily upper bounds as calibrated intervals.
