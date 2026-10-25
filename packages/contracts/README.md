# API contracts

Pydantic/FastAPI owns the machine contract. `openapi.json` and `src/schema.d.ts`
cover the PP-45 baseline forecast/presenter routes reviewed in PR #75.
They do not finalize every V5 domain or imply OR-branch integration. See
[forecast flow and boundaries](../../docs/pantrypulse/FORECAST-API-FLOW.md).

From the repository root (PowerShell):

```powershell
apps/api/.venv/Scripts/python.exe apps/api/scripts/export_openapi.py --stdout | Set-Content -Encoding utf8 packages/contracts/openapi.json
node node_modules/openapi-typescript/bin/cli.js packages/contracts/openapi.json -o packages/contracts/src/schema.d.ts
apps/api/.venv/Scripts/python.exe apps/api/scripts/export_openapi.py --check packages/contracts/openapi.json
node node_modules/openapi-typescript/bin/cli.js packages/contracts/openapi.json -o packages/contracts/src/schema.d.ts --check
```

Exporting never connects to a database, loads credentials or runs inference. Never
edit generated output manually. Regenerate and diff it after public schema changes.

