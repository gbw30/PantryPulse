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


VP API convergence retains the connected planning contracts and adds exact-string
operational quantities, audited writes/imports, dashboard/shortage reads, canonical
single-method plans and simulation reviews. Original VP raw-package/policy and
competing scenario/comparison shapes are superseded. Legacy reads explicitly use
the VP_LEGACY family and cannot submit work. See docs/pantrypulse/VP-API-INTEGRATION.md.

## v1 examples (W0-08)

`examples/v1/<SchemaName>.json` holds one example per v1 response model (the routes in
`apps/api/app/routers/v1_*.py`). They describe one fictional Pantry network. `w1-web` builds its
Playwright mocks only from these files. `contracts:check` runs
`apps/api/scripts/validate_contract_examples.py`, which fails on a missing, extra or invalid
example. v1 routes and their decisions: `docs/plans/v1/README.md` ("Interfaces frozen in W0-08")
and `docs/plans/v1/decisions/W0-08-scenario-and-import.md`.
