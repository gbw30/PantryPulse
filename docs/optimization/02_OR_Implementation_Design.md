# PantryPulse OR implementation design

**Revision 1.2 — OR-only service boundary, October 24, 2026**

The user explicitly limited this assignment to the research-centered allocation
pipeline. This design replaces the overbroad Draft 1.1 implementation ownership;
its original is retained at `46ff0cd:docs/optimization/02_OR_Implementation_Design.md`.
Equations/policy remain in companion 01. [Execution revision 1.2](03_OR_Codex_Execution_Spec.md)
controls allowed paths and acceptance. Historical API/UI/job/SQL designs are handoff
material, not implementation instructions for the OR owner.

## Owned pipeline and modules

| OR-owned module | Responsibility |
|---|---|
| `schemas/or_inputs.py` | Immutable normalized package, policy and frozen scenario contracts |
| `schemas/or_outputs.py` | Candidate/plan, projection, verification, metrics and independent method/comparison outputs |
| `optimization/forecast_adapter.py` | Pure conversion from existing supplied forecast/handoff values, preserving identity and avoiding double rounding |
| `optimization/canonical.py`, `scenario.py` | Exact identity, explicit mode/policy/assumptions, freeze and derivation replay |
| `optimization/kernel.py`, `projection.py` | OR-local FEFO/lost-sales simulation with lot lineage and no stock writes |
| `optimization/candidates.py`, `packing.py` | Dated baseline, original-stock candidates, donor protection and deterministic packing |
| `optimization/constraints.py` | One bounded physical feasible region for both methods |
| `optimization/classical_gp.py`, `egp_pi_inspired.py` | Independent objective attachments with exact coefficients and strict AP/RP reification |
| `optimization/numerics.py`, `extract.py` | Actual emitted-activity audit and native-status extraction guard |
| `optimization/verify.py`, `metrics.py` | Independent replay/checking and exact/common evaluation; no builder dependency |
| `optimization/service.py`, `compare.py` | Typed computational entry points and paired outcomes; no HTTP/ORM/job dependency |
| `optimization/offline.py` and OR-local execution helper | Bounded offline child execution only; no persistent queue or application supervisor |
| Five computational commands plus common file I/O | Validate, enumerate, verify, solve and compare supplied files; no DB seed/benchmark/browser/supervisor commands |

All `optimization` modules are under `apps/api/app/services/`. Import existing
forecast/numeric/mode helpers read-only. The existing `services/inventory/projection.py`
remains its owner's implementation and retains its experimental null-expiry policy.
OR's stricter resource eligibility and network recurrence live in the OR package.

## Input and result interface

The caller supplies a complete validated `ORInputPackage` and explicit `ORPolicy`,
mode, planning window, modifiers and revision expectation to `freeze_scenario`.
`verify_scenario` independently checks canonical identity and derived demand/order.
The adapter does not query source stores, run a provider or promote an in-memory
forecast readiness flag to committed readiness.

`prepare_problem` builds one scenario's baseline/candidates. `solve_one(scenario,
method, settings)` returns a `MethodOutcome` with native status, verified candidate
only when readable, exact objective/common metrics, identities and diagnostics.
`compare` runs both computational methods sequentially; `assemble` can combine
independent outcomes from an external worker owner. Inputs, policy, physical model
and settings must agree. Failures remain method-specific; zero transfers is a valid
verified vector and differs from an absent/invalid vector.

The computational result is returned to the caller. It is not a committed plan,
stock movement, reservation, review event or public response. Exceptions and typed
failure outcomes are internal contracts; the API owner defines HTTP mappings.

## External ownership contracts

| External owner | Their work; OR contribution |
|---|---|
| FastAPI | Routes, validation/orchestration, sessions, CSRF/CORS, errors and public contracts; OR supplies Python schemas/callables |
| Data/inventory | Authoritative ledger, reservations/receipts, transactions, source revisions and consistent snapshot reads; OR consumes frozen values |
| Forecast | Required-series policy, actual providers, committed publication and read adapter; OR preserves supplied provenance/targets |
| Shared runtime | Durable jobs/admission, supervisor/leases, global resource ceilings, retry/cancel and fenced publication; OR supplies method callables and verified outcomes |
| Frontend | Scenario/result views and direct FastAPI consumption under the deployment contract; OR supplies metric definitions/examples |

**Never implement Next.js API routes or a Next.js proxy.** Next.js is frontend only
for this project. Do not generate or alter the public API/TypeScript client from this
OR assignment. Missing external contracts stay explicit handoff dependencies.

## Tests and reproducibility

Keep exact independent oracle/proof/native tests, all four mode/method combinations,
FEFO/conservation/expiry/ETA/donor/capacity cases, actual strict threshold branches,
decision-changing AP/RP ablations, emitted bounds and safe native status handling.
Test canonical roundtrip, local snapshot stock timing, malformed candidates and
truthful source numeric conversion. Preserve all pre-OR forecasting/helper tests.

Offline commands consume JSON and emit explicit OFFLINE results with exact source,
policy and settings identities. Validation errors never return successful vectors.
A narrowly scoped child runner enforces real deadlines and cleanup without importing
shared application jobs/workers; direct computational calls promise only their
native search bound. No actual Chronos/model downloads are part of verification.

Database/browser/hosted CI/full-product acceptance belongs to external owners. Keep
previous broad implementation and its tests/evidence in a reversible handoff before
removing them from this branch; never treat archived evidence as a current pass.
