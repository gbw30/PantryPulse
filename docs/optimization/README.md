> **Current approved integration:** [Connected application and v2 contracts](CONNECTED-INTEGRATION.md) supersede historical OR-only/no-proxy scope and 15/25/60-second execution limits below. The old decision manifest and qualification artifacts remain historical evidence; their hashes and semantics are not reinterpreted.

# Optimization service

**Start with [current ownership](SCOPE.md) and [execution revision 1.2](03_OR_Codex_Execution_Spec.md).**
The user corrected the scope to the research-centered OR pipeline and necessary
Python schemas. Frontend, FastAPI routes, auth, database and shared-worker integration
are outside this assignment. Next.js is frontend only; no Next API routes/proxies.

[Mathematical specification](01_OR_Mathematical_Specification.md),
[implementation design revision 1.2](02_OR_Implementation_Design.md),
[research mapping](RESEARCH-MAPPING.md), [numerical proof](NUMERICAL-PROOF.md),
[provisional decisions](DECISION-REGISTER.md) and [scope-correction handoff](SCOPE-CORRECTION.md)
record the core and its boundaries. Historical review/UI/API/DB checkpoints remain
history only; they do not authorize reintroducing those layers or prove current
application integration. #54 remains the tracker. Supplier/model/hosting stays paused.

[Callable interface and offline example](INTEGRATION-INTERFACE.md) explain how owning services consume the OR component without HTTP, DB or shared-worker dependencies.

[Final OR milestone](FINALIZATION.md), [qualification and limits](QUALIFICATION.md)
and the [current acceptance ledger](ACCEPTANCE.md) record comparison hardening,
policy sensitivity and actual native performance. Core completion is distinct from
external source/API/storage/runtime integration and domain approval of provisional
policy values.
