# OR callable interface for the owning services

OR is a Python computational component under `app.services.optimization`, not an
HTTP application, persistence layer or frontend backend. [Execution revision 1.2](03_OR_Codex_Execution_Spec.md)
defines ownership. The caller owns committed-source consistency, access control,
scheduling/global resources, transactions, publication and public error mapping.

From `apps/api`, consume an already frozen scenario:

```python
from app.schemas.or_inputs import ORScenarioPayload
from app.services.optimization.scenario import verify_scenario
from app.services.optimization.service import solve_one
from app.services.optimization.compare import assemble

scenario = ORScenarioPayload.model_validate_json(saved_scenario_json)
verify_scenario(scenario)
classical = solve_one(scenario, "CLASSICAL_GP")
research = solve_one(scenario, "EGP_PI_INSPIRED")
comparison = assemble(scenario, (classical, research))
```

A shared runtime owner can run the methods in its own controlled children and call
`assemble` with their independent results. Direct calls cap native search at 15
seconds; they do not promise whole-application admission, CPU/memory quotas, child
containment or committed publication. The OR-local offline runner is for supplied
files and has a separate method/pair deadline; it is not a persistent queue.

To create a scenario, pass `ORInputPackage`, `ORPolicy`, explicit `transfer_mode`,
`planning_days`, `modifiers`, `intent` and `expected_source_revision` into
`freeze_scenario`. It validates supplied values and canonical derivation; it does
not read current source stores or establish committed readiness. Preserve original
forecast identity separately from the operational hash.

Read a candidate only when `outcome == "VERIFIED"`, native status permits it and
the independent verification passes. Zero transfers can be valid. Keep a failed
partner's own outcome and error code; never substitute the other method. Typed
outputs carry exact common metrics, objective/status, source/policy/settings and
physical identities. Different objective scores do not define a universal winner.
Results have no stock, reservation, dispatch, review or database side effect.

Offline example from the repository root:

```bash
uv run --frozen --directory apps/api python -m scripts.or_compare \
  --snapshot ../../data/demo/or-v1/six-beneficiary-v1.snapshot.json \
  --output ../../artifacts/or-core-comparison.json
```

The separate frontend owner consumes FastAPI under the team's access contract.
Never introduce Next.js API routes/proxies. Historical integration patches are for
owner review, not wholesale application; their withdrawn Next proxy is prohibited.
