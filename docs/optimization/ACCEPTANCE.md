# OR acceptance evidence — reviewed checkpoint

October 24, 2026. Base commit `e49e360d23e46b43542b0a2e9b5f6277d5f840d5`
plus the reviewed working tree. The initial checkpoint is retained in
[evidence](evidence/acceptance-initial-checkpoint.md). This is a commit milestone;
issue #54 and whole-product V5 acceptance remain incomplete.

All sources are explicitly SIMULATED. The corrected fixture revision is
`sim-v2-stock-asof`; see [fixture provenance](../../data/demo/or-v1/README.md).
The six-beneficiary scenario operational hash is
`60e31e1936082aa707a60d384d201bdc3c79b3f31958e26aa2cfa25204e87428`.
Policy hash is
`e1a5a175fa17d7a7ae81815538e8a6e06048040638458d0a66f00a20d1f414eb`.
Actual model bounds and identical physical fingerprints are in
[reviewed native evidence](evidence/model-bounds-six-beneficiary-stock-asof.json).
Solver settings: one search worker, seed 0, 15,000 ms search limit per method.
Environment: Linux, Python 3.12.13, OR-Tools 9.15.6755, PostgreSQL 16.15,
Node 24.16.0/npm 11.13.0. Tests use dedicated local `pantrypulse_or_test`
and disposable schemas. Local uv is 0.13.5; CI pins 0.11.15.

## Executed review evidence

- Independent API/model review reproduced failures before fixes for Unicode login,
  future heartbeat, canonical snapshot roundtrip, future original stock,
  malformed candidate reports, and repeated retry requests with distinct keys.
- Real browser execution reproduced loopback-origin rejection and missing
  pagination headers in the thin Next proxy. Three direct proxy regression tests
  now cover legitimate login forwarding, hostile origin/Host rejection, cursor
  forwarding and session-cookie filtering.
- Native tests force both AP/RP Boolean branches at equality and one integer quantum
  above; gamma-zero diagnostic ablations change actual native allocations. A new
  independently enumerated small case agrees with the native research optimum.
- CLI tests invoke actual module entry points, exact paired native solving,
  independent verification/tamper rejection, invalid JSON shapes, dedicated-DB
  guardrails, safe seed refusal and verified zero-transfer output.
- All seven Chromium browser tests pass, including five real reset-to-finish OR
  rehearsals, both transfer modes, changed demand, review, saved visitor reads,
  CSRF/origin rejection, pagination, keyboard controls, reduced motion and three
  viewports. The mobile beneficiary column stays visible while keyboard scrolling.
  [Rehearsal evidence](evidence/browser-rehearsals-reviewed.json) records durations
  and identities; local screenshots/logs are under `artifacts/or/browser` and
  `artifacts/or/verification/browser-reviewed.log`.
- Five separate durable paired benchmark jobs succeeded. Median whole-job wall
  time was 3.13 s; maximum saved HTTP read was 0.119 s. The actual shared worker
  cgroup reported six CPUs, 8 GiB memory maximum, zero swap and 182,984,704 bytes
  peak memory. The smaller function timing excludes interpreter startup.
  [Benchmark evidence](evidence/persisted-benchmark-reviewed.json) preserves this
  distinction. These measurements qualify this local OR fixture/environment only.

Final combined gate results are recorded in
[the reviewed checkpoint](CHECKPOINT-REVIEW-2026-10-24.md). A failed intermediate
combined run found one stale test expecting `sim-v1`; the test now uses its actual
snapshot revision when checking source fencing. The first quality-gate run also exposed transient `/proc` inspection and systemd
scope-stop ordering assumptions in two resource tests; those tests now inspect the
executed application and retain an independent observer slice for actual kernel OOM
evidence even when the workload is killed, respectively. Ten consecutive cycles
pass. Failed
runs are not pass evidence.
Starlette/httpx deprecation and the intentionally exercised WebGL fallback emit
warnings; browser tests report no OR page errors.

## Acceptance ledger

| ID | Status | Evidence and boundary |
|---|---|---|
| OR-A01 | PASS | Verbatim specs, reconciled worker/current baseline; original forecasting/helper regressions retained |
| OR-A02 | PASS | Strict scopes, rounding/hash/replay/tamper checks, snapshot-local stock cutoff, canonical serialization; LIVE remains A12 |
| OR-A03 | PASS | Independent packing/projection/checker, conservation/expiry/FEFO/donor/capacities, both modes and tiny native feasible-set equivalence |
| OR-A04 | PASS | Research mapping/proof, independent optima, native strict threshold branches and decision-changing AP/RP ablations; emitted activities below `2**60` |
| OR-A05 | PASS | Exact full-fixture native optima in both modes, common physical/settings identities and saved common metrics |
| OR-A06 | PASS | Status extraction sentinels, malformed candidates, independent verification, atomic publication and method failure/partial retention checks |
| OR-A07 | PASS | Real PostgreSQL migration/integrity/immutability/rollback/race/review/reset tests, corrected linked-retry deduplication |
| OR-A08 | PASS | Local real lease/cancel/timeout/loss/kill/reap/retry/partial checks and actual cgroup OOM/limits. Hosted-worker qualification remains separate |
| OR-A09 | PASS | Real auth/session/CSRF/origin HTTP and browser checks; proxy/pagination regressions, generated contracts, saved reads during outage. UI comprehension remains A11 |
| OR-A10 | PASS | Actual module-mode CLI matrix, contracts, decision markers, local quality gates, five-run persisted benchmark and reproducible browser harness. Hosted GitHub Actions has not been executed |
| OR-A11 | UNVERIFIED | Five full persisted browser rehearsals and measured timings pass; remaining saved-assumption/metric explanations, mobile hierarchy and human visual acceptance are listed in the reviewed checkpoint |
| OR-A12 | UNVERIFIED | Committed authoritative forecast publication, inventory and operational read adapters are still missing. Explicit unavailable behavior is not a LIVE integration pass |

No actual Chronos inference, supplier work, deployment, production source journey,
GitHub issue closure, or whole-product completion is claimed.
