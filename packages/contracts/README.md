# API contracts

Pydantic/FastAPI owns the machine contract. `openapi.json` and `src/schema.d.ts` cover presenter/limited visitor reads, baseline/Chronos forecasts and jobs, operational catalog/import/stock/receipt/supply/product commands, dashboard/shortage reads, canonical planning/scenarios/comparisons/plans and simulation reviews. Legacy VP records are explicitly read-only and non-executable.

Current limits include at most eight planning products; fixture-specific two-product examples are not the contract cap. Model selection is a server-bound request/capability contract, not arbitrary checkpoint metadata supplied by a browser.

From the repository root on Windows:

```powershell
apps/api/.venv/Scripts/python.exe apps/api/scripts/export_openapi.py --stdout | Set-Content -Encoding utf8 packages/contracts/openapi.json
node node_modules/openapi-typescript/bin/cli.js packages/contracts/openapi.json -o packages/contracts/src/schema.d.ts
npm run contracts:check --workspace @pantrypulse/web
```

Export never connects to a database, reads credentials, downloads a model or runs inference. Do not edit generated files by hand. Regenerate both after a public schema change and inspect the diff. Windows CRLF differences can affect byte checks; diagnose and normalize line endings without masking semantic drift. A model adapter install is separate from schema export.

See [API runbook](../../docs/pantrypulse/ALL-API-RUNBOOK.md), [forecast flow](../../docs/pantrypulse/FORECAST-API-FLOW.md), [Chronos jobs](../../docs/forecasting/CHRONOS-JOBS.md), [connected planning](../../docs/optimization/CONNECTED-INTEGRATION.md) and [testing](../../docs/testing/README.md).
