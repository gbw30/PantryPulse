> **Current approved integration:** [Connected application and v2 contracts](CONNECTED-INTEGRATION.md) supersede historical OR-only/no-proxy scope and 15/25/60-second execution limits below. The old decision manifest and qualification artifacts remain historical evidence; their hashes and semantics are not reinterpreted.

# OR callable interface for the owning services

OR is a Python computational component under `app.services.optimization`, not an
HTTP application, persistence layer or frontend backend. [Execution revision 1.2](03_OR_Codex_Execution_Spec.md)
defines ownership. The caller owns committed-source consistency, access control,
scheduling/global resources, transactions, publication and public error mapping.

From `apps/api`, consume an already frozen scenario:

```python
from app.schemas.or_inputs import ORScenarioPayload
from app.services.optimization.scenario import verify_scenario
from app.services.optimization.service import DEFAULT_SETTINGS, solve_one
from app.services.optimization.compare import assemble

scenario = ORScenarioPayload.model_validate_json(saved_scenario_json)
verify_scenario(scenario)
classical = solve_one(scenario, "CLASSICAL_GP")
research = solve_one(scenario, "EGP_PI_INSPIRED")
comparison = assemble(scenario, (classical, research), expected_settings=DEFAULT_SETTINGS)
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

Pair assembly validates policy, operational, mode, historical and decision identities
for failed as well as successful outcomes. Settings hashes must agree; pass
`expected_settings` to bind them to the caller's requested configuration. Without
that argument, equal hashes establish agreement only, not the intended settings.
Any supplied physical fingerprint must match a fresh physical build; verified
results require it. Successful candidates, verification reports and objectives are
replayed independently. Invalid identities/results raise `ValueError` with a
`PAIRED_` code rather than becoming a partial comparison. A failure before model
construction may have no fingerprint. Hashes establish content consistency, not
trusted origin or authorization.

Physical fingerprints identify the current emitted model. After a compiler change,
assemble newly solved outcomes or replay with the matching compiler version;
historical fingerprints are not portable across implementations. Frozen input
identity and independent plan feasibility remain separate checks. Native status,
bound and gap describe that search; replay validates a candidate, not its optimality.
