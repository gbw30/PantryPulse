# PantryPulse OR service execution specification

**Revision 1.2 — OR-only ownership correction, October 24, 2026**

This revision implements the user's explicit scope correction. Draft 1.1 incorrectly
assigned frontend, API, database and shared-worker implementation to the OR task.
Those clauses are withdrawn. Their integration requirements describe other owners'
work, not permission for this agent to implement it. The original text is retained
in Git at `46ff0cd:docs/optimization/03_OR_Codex_Execution_Spec.md`.
The mathematical formulation and OR-DEC policy values have not changed.

## 1. Scope and authority

Implement only the diagram's **Research-Centered Allocation Intelligence** pipeline:
normalized immutable input → candidate transfers → shared physical constraints →
CLASSICAL_GP / EGP_PI_INSPIRED → OR-Tools CP-SAT → independent verification,
objective/deprivation evaluation → typed plans and metrics returned to the caller.

The user owns scope. Explicit user instructions override attached documents, issue
bodies, acceptance checklists and previous agent plans. A request to use a spec does
not transfer ownership of every adjacent system mentioned in it. Missing adjacent
components are integration dependencies; they are not invitations to build them.

**Next.js is frontend only in this architecture. Never add Next.js API routes or
route-handler proxies. FastAPI routing/orchestration belongs to the API owner.**
No frontend, API route, authentication, database migration/repository, persistent
queue, supervisor or shared worker changes are part of this assignment.

## 2. Allowed implementation paths

- `apps/api/app/services/optimization/**`: OR models, packing/projection, objectives,
  exact arithmetic, verification, comparison and narrowly scoped offline execution.
- `apps/api/app/schemas/or_inputs.py` and `or_outputs.py`: OR-owned typed contracts.
- `apps/api/tests/optimization/**`: independent arithmetic, native solver, contract,
  CLI and OR-only execution checks.
- Offline `apps/api/scripts/or_{common,validate_input,enumerate,verify,solve,compare}.py`.
- `data/demo/or-v1/**`, `scripts/or/**`, `docs/optimization/**` and narrowly scoped
  task/ownership documentation. Fixtures are explicitly simulated.

Existing forecast, inventory, method/mode and numeric helpers may be imported
read-only. Do not refactor another service to accommodate OR. Put the OR-specific
network projection in the OR package; preserve the existing inventory projection.
No dependency/lockfile or shared configuration change is implied by this allowlist.

## 3. Explicitly excluded work and handoff

Do not edit `apps/web/**`, `app/main.py`, `app/routers/**`, `app/models/**`,
`app/repositories/**`, `app/services/jobs/**`, `app/workers/**`, database migrations,
generated public OpenAPI/TypeScript, shared CI/package configuration or authoritative
inventory/forecast storage. In repository-relative form the Python paths above are
under `apps/api/`. Do not copy another branch's queue into this deliverable.

External owners obtain authoritative data, enforce access/revisions/transactions,
call OR, persist verified results and expose them through FastAPI. Frontend owners
consume that API directly under the team's deployment/CORS contract. The OR owner
supplies Python input/result schemas and callable examples, not HTTP routes.

Prior integration/UI work must be preserved as a separate, checksummed handoff
before removal from the OR working tree. Do not rewrite commits or reset the branch.
Remove only attributable additions or restore exact attributable edits; preserve
collaborator/pre-existing work and flag uncertain ownership explicitly. Do not apply
handoff patches to another owner's branch or send them messages without authorization.

## 4. Mathematical and source requirements

Use `01_OR_Mathematical_Specification.md` for equations, fixed-point scale, provisional
policy and independent expected results. Keep both transfer modes explicit and
independent from method. Preserve deterministic loading, dated lost-sales/FEFO,
original-stock conservation, no relay, receiving/handling limits, ETA/expiry and
seven-day donor protection without proposed inbound stock. Demand ceilings apply
per date after original-source assumptions, never to previously rounded targets.

Both methods use one physical feasible region. Classical has equal ordinary weights;
research has actual vulnerability weights and active, strictly reified AP/RP excess
terms. Equality is unflagged. Zero targets are excluded from groups; singleton
positive groups remain unsupported. Keep exact fractions and quantized diagnostics.
Every emitted integer activity must be strictly below `2**60` before native search.
Never add a shortage-first objective or relabel one method after the other fails.

Validate frozen input/scenario hashes and derivation; retain original forecast
identity/provider/basis/date/unit provenance. OR consumes supplied complete data and
performs no source queries, implicit forecasting or stock writes. The caller owns
committed-source authorization and consistency; structural validation is not proof
that an input was committed. SIMULATED native tests do not establish LIVE readiness.

## 5. Execution order and service boundary

1. Reconcile current files/ownership and record the allowed paths before coding.
2. Preserve the research mapping, independent enumeration and numerical proof gate.
3. Implement/verify OR input contracts, source adapter, canonical freeze/replay,
   independent projection/checker and shared constraints.
4. Attach and independently validate classical and research objectives; compare the
   same scenario/settings, retaining independent outcomes without substitution.
5. Verify module-mode offline commands and a small OR-owned child boundary where
   needed. It must not import the application's shared queue/worker implementation.
6. Deliver typed outputs and an integration handoff to API/storage/worker owners.

`solve_one` is the computational entry point and limits native search to 15 seconds.
The offline runner additionally enforces whole-method 25-second and pair 60-second
boundaries, terminates/reaps its owned child tree and exposes no DB credentials.
It is not a second job queue. Application-wide admission, leases, auth, persistence,
whole-worker resource ceilings and publication remain the shared runtime owner's job.
Do not claim those external guarantees from an OR-only test.

## 6. Acceptance and evidence

Required local evidence: original helper/forecast regressions; strict OR contracts,
canonical/tamper/rounding cases; independent conservation/FEFO/donor/capacity checks;
actual native feasible-set/optimum comparisons; strict AP/RP boundary and ablation
cases; safe integer bounds; native status extraction gate; independent verification;
paired failure/partial/zero-transfer behavior; offline exit codes and real OR child
termination. No browser, HTTP or PostgreSQL test is a completion prerequisite for
this ownership slice. Do not implement their systems to satisfy an old checklist.

Expected full fixture per product: classical `(1,1,1,1,1,1)`, J=`163/50`;
research `(2,2,1,1,0,0)`, J=`1393/300`. AP fixture: full `(1,0)`, `19/8`,
no-AP `(0,1)`, `2`. RP fixture: full `(0,1)`, `11/4`, no-RP `(1,0)`, `21/8`.
Use independent exact enumeration; arbitrary tied vectors need not match exactly.

Run meaningful failing/passing regressions, Ruff, the complete retained API Python
suite and OR offline/native checks. Verify the baseline process-health/route surface
and frontend files were not expanded by this deliverable. Report exact base/tree,
commands, hashes, outcomes and limitations. Historical broad integration evidence
must be labelled archived, not reported as current application acceptance.

## 7. Backlog and stopping rule

Keep #54 as the OR tracker and existing issues/history intact. Frontend/API/storage/
worker PBIs are handoffs owned outside this OR assignment. Reclassify #59–#66 and
related technical issues accordingly; do not silently close or delete them. Existing
OR mathematics/contracts/verification issues remain active. Supplier, Chronos and
hosting work remain paused.

Stop at a substantial tested milestone for the user's commit. No automatic commit,
push, merge, deployment, physical stock action or broader product-completion claim.

## October 25 finalization clarification

Pair identity checks apply to every outcome, including FAILED and TIMED_OUT.
Assembly replays verified plans and reconstructs any supplied physical fingerprint;
callers pass expected solver settings to bind the pair to their request. Retain
independent partial results without accepting mixed policies or stale metadata.

Qualification must include the declared size ceilings together, both modes, numeric
quantity/goal limits and diagnostic policy extremes. Report FEASIBLE/UNKNOWN and
actual gaps honestly: shape bounds do not guarantee optimality within 15 seconds.
Performance reductions must preserve the shared feasible region and pass independent
native/replay tests. Current evidence belongs in FINALIZATION.md and QUALIFICATION.md;
these requirements add no frontend, routing, storage, shared-runtime or CI ownership.
