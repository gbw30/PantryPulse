# OR checkpoint review fixes

Base: e49e360d23e46b43542b0a2e9b5f6277d5f840d5. User resumed work and
required thorough testing first. All original 873 API/PostgreSQL tests pass;
independent review and actual browser execution identified additional regressions.

Lead owns shared configuration, generated contracts, CLI/runtime, Next proxy/UI
and integration. No source reset, merge, deployment or physical stock write.

API review lane: only services/or_access.py, routers/or_api.py (readiness function),
tests/integration/test_or_http.py. Fix UTF-8 username comparison, coherent cheap
heartbeat observations with explicit future-age rejection. Derive failing tests
before fixes; run on dedicated local test DB in random isolated schemas.

Model review lane: schemas/or_inputs.py, schemas/or_outputs.py (verification
candidate identity only), optimization/{scenario,verify}.py, and new
tests/optimization/test_or_review_regressions.py. Reject original on-hand stock
whose availability is future at snapshot under the network timezone; preserve
existing projection compatibility. Canonical snapshot roundtrip must reconstruct
correctly. Invalid candidates must produce structured failed verification without
inventing an identity for unvalidated content. Tests first; root regenerates TS.

Lead independently checks diffs/tests and integrates all lanes. Workers may report
additional proven findings but must not edit outside boundaries. Keep draft choices
and source contracts unchanged in meaning. Handoff gives exact commands/results,
remaining limitations and counterexamples. No subagents or Git mutations.

Review milestone complete. See [verified results and remaining work](../../optimization/CHECKPOINT-REVIEW-2026-10-24.md). The historical review assignments above do not authorize additional work beyond the user’s requested scope.
