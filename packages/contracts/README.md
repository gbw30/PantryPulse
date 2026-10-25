# API contracts

Pydantic/FastAPI owns the machine contract. `openapi.json` and `src/schema.d.ts`
cover presenter/forecast routes and PP-46 planning catalog, assumptions, scenario, comparison and generalized job routes. They do not finalize broader V5 domains. See
[forecast flow](../../docs/pantrypulse/FORECAST-API-FLOW.md) and [connected planning](../../docs/optimization/CONNECTED-INTEGRATION.md).

From the repository root (PowerShell):

```powershell
apps/api/.venv/Scripts/python.exe apps/api/scripts/export_openapi.py --stdout | Set-Content -Encoding utf8 packages/contracts/openapi.json
node node_modules/openapi-typescript/bin/cli.js packages/contracts/openapi.json -o packages/contracts/src/schema.d.ts
apps/api/.venv/Scripts/python.exe apps/api/scripts/export_openapi.py --check packages/contracts/openapi.json
node node_modules/openapi-typescript/bin/cli.js packages/contracts/openapi.json -o packages/contracts/src/schema.d.ts --check
```

Exporting never connects to a database, loads credentials or runs inference. Never
edit generated output manually. Regenerate and diff it after public schema changes.

