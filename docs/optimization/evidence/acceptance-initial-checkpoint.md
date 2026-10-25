# OR acceptance evidence — implementation checkpoint

Date: October 24, 2026, America/New_York. Code: base
`f3946c726e53fa546be1400d80ab717fcb2c3468` plus the uncommitted working tree.
This checkpoint stops for the user to commit. Full OR/V5 release acceptance is
incomplete; no GitHub implementation issue has been closed.

Inputs are `data/demo/or-v1/*.snapshot.json`, with explicit SIMULATED provenance,
policy/settings identities and OR-DEC metadata. The six-beneficiary/two-product
window is H=3 with seven forecast dates. See
[native model-bound evidence](evidence/model-bounds-six-beneficiary-v1.json) for
exact operational/policy hashes and common physical fingerprints, and
[independent enumeration](RESEARCH-MAPPING.md) for unique optimum evidence.

## Executed checks

Environment: Linux; Python 3.12.13; locked dependencies including OR-Tools 9.15.6755;
PostgreSQL 16.15 on dedicated local `pantrypulse_or_test` with isolated schemas;
Node 24.16.0/npm 11.13.0. Native tests use one search worker and seed 0.
Prefix npm commands locally with the tooling directories recorded in the checkpoint.

| Command | Evidence/status |
|---|---|
| `npm run check` with `PP_TEST_DATABASE_URL` naming the dedicated test DB | PASS: types/lint and 870 tests, including real PostgreSQL. Three new bound-audit regression cases were added during review; the updated OR suite separately passes 59 tests. Log: `artifacts/or/milestone-check.log` |
| From `apps/api`: `.venv/bin/python -m pytest tests/optimization -q` | PASS: 59 tests after the bound-audit fix |
| From `apps/api`: `.venv/bin/python -m pytest tests/workers/test_resource_limits.py -q` | PASS: 5 tests, including actual kernel cgroup OOM counter |
| `npm run build` | PASS: root, design lab, allocation UI and API proxy compile |
| `npm run contracts:generate` and `npm run contracts:check` | PASS: actual OpenAPI/TypeScript generation and no drift |
| `npm run test:config` | PASS: 17 tests |
| `npm run or:decisions` | PASS: 20 decisions, real behavior/test symbols and fixture metadata |
| `git diff --check` | PASS |
| Original supplied specs compared byte-for-byte | PASS: all three copies remain verbatim |

The combined run collected its 870 cases before the three numerical regression tests were added. The 59-case updated OR run includes those new tests and reruns the actual solvers with the corrected audit. No skipped test is included in these pass counts.

The earlier full test run exposed a resource-test assumption about systemd's OOM
stop and was corrected; that failed run is not counted as passing. The numerical
review also reproduced three failing upper-bound/overflow tests before fixing the
native-container indexing bug. Fresh focused mathematical checks pass. A Starlette/
httpx deprecation warning remains; it does not represent provider qualification.

## Full acceptance ledger

PASS below is bounded to the stated evidence. UNVERIFIED preserves additional
required evidence; a written test, skipped test or compiled UI is not a browser pass.

| ID | Status | Evidence and remaining boundary |
|---|---|---|
| OR-A01 | PASS | Verbatim adoption, current-ref/worker reconciliation, preserved forecasting/helper regressions; [baseline](BASELINE-RECONCILIATION.md) |
| OR-A02 | PASS | Strict simulated inputs/scenarios, adapter, precision, hashes, tamper/replay and scope tests in `test_or_pure.py` and persistence tests; LIVE remains A12 |
| OR-A03 | PASS | Independent packing/projection/checker, both modes, donor/expiry/handling cases and tiny CP feasible-set equivalence in `test_or_model_equivalence.py` |
| OR-A04 | UNVERIFIED | Checked mapping, exact independent oracles, native optimum agreement and corrected emitted bounds pass; complete native boundary/sensitivity acceptance audit remains |
| OR-A05 | PASS | Both real methods/modes, unique full-fixture optima, identical physical/settings identities and saved common metrics; `test_or_solver.py`, `test_or_http.py` |
| OR-A06 | UNVERIFIED | Status gate/checker, atomic checked publication and partial failures implemented/tested; finish complete independent failure/status matrix |
| OR-A07 | PASS | Actual PostgreSQL migration/integrity/immutability/rollback/race/review/reset checks in `test_or_persistence.py` and inherited queue tests |
| OR-A08 | UNVERIFIED | Queue/lease/termination/fencing and real cgroup tests pass locally; finish full worker-profile resource/benchmark evidence and independent review |
| OR-A09 | UNVERIFIED | Backend security, saved reads and generated contracts pass; rendered same-origin proxy/browser journey remains |
| OR-A10 | UNVERIFIED | Offline bounded pair and marker/contracts checks work; full CLI/benchmark/CI execution evidence remains |
| OR-A11 | UNVERIFIED | Real persisted synthetic HTTP journey passes; browser rehearsal, visual/accessibility and measured timings remain |
| OR-A12 | UNVERIFIED | Missing committed forecast publication plus authoritative stock/operational read adapters; explicit unavailable boundary is not a LIVE integration pass |

The CLI benchmark has not established saved-read/solve latency targets or a measured
hardware/resource report. No actual Chronos inference, supplier work, deployment,
whole-product completion or final independent sign-off is claimed.
