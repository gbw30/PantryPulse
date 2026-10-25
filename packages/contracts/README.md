# API contracts

Pydantic/FastAPI owns the machine contract. `openapi.json` and `src/schema.d.ts`
cover the PP-45 forecast/presenter routes, PP-46/47 inventory and adjustment routes,
and PP-49 receipts, declarations, supplies, imports, dashboard, shortages and saved
allocation workflows currently implemented on VP. OR integration uses explicit
v2 input/scenario contracts and the shared presenter and job infrastructure.
See the [API runbook](../../docs/pantrypulse/ALL-API-RUNBOOK.md) for execution
requirements and remaining worker/UI/release checks.

From the repository root (PowerShell):

```powershell
apps/api/.venv/Scripts/python.exe apps/api/scripts/export_openapi.py --stdout | Set-Content -Encoding utf8 packages/contracts/openapi.json
node node_modules/openapi-typescript/bin/cli.js packages/contracts/openapi.json -o packages/contracts/src/schema.d.ts
apps/api/.venv/Scripts/python.exe apps/api/scripts/export_openapi.py --check packages/contracts/openapi.json
node node_modules/openapi-typescript/bin/cli.js packages/contracts/openapi.json -o packages/contracts/src/schema.d.ts --check
```

Exporting never connects to a database, loads credentials or runs inference. Never
edit generated output manually. Regenerate and diff it after public schema changes.

