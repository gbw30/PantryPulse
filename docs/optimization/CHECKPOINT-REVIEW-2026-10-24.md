> Historical pre-correction scope/evidence. Adjacent implementation is archived, not active on this OR branch. [Current scope and handoff](SCOPE-CORRECTION.md) supersede its implementation instructions/status.

# OR reviewed testing milestone — October 24, 2026

Base: `e49e360d23e46b43542b0a2e9b5f6277d5f840d5`, plus the working tree.
The user requested thorough verification before continuing and a stop at substantial
milestones so they can commit. No commit, push, deployment or issue closure is made.

## Changes in this milestone

Fixed canonical snapshot replay, structured invalid candidate reports, snapshot-local
original-stock availability, UTF-8 presenter login, future-heartbeat readiness,
active retry reuse across new idempotency keys, real Next loopback origin handling,
and saved-list cursor forwarding. Invalid CLI JSON/database URLs now return documented
errors. Synthetic source hashes now represent actual input content; original stock
exists by snapshot time. Existing stored records are not rewritten.

Fixed timing assumptions in resource tests: read environment from the executed child,
and read actual kernel OOM counters from an independent retained observer slice,
including confirmed workload cleanup. Ten consecutive real startup/OOM cycles pass.
No process-control limits were relaxed.

Added independent native threshold/ablation/new-oracle tests, real CLI regression
coverage and direct Next proxy tests. The mobile comparison table supports keyboard
scrolling with a sticky beneficiary column. The browser harness starts the actual API
and shared production supervisor with random in-memory credentials and a random
isolated PostgreSQL schema, then removes only that schema and its owned processes.
It refuses remote/non-test database URLs and never prints credentials. Browser tests
refuse to reuse an existing development server when disposable OR credentials exist.

Actual five-run persisted benchmark and five complete browser rehearsals are recorded
in [acceptance evidence](ACCEPTANCE.md). The activated CI workflow runs the same local
quality gate and isolated browser command; no hosted Actions run is claimed.

## Verification

`node scripts/quality/run.cjs full`: PASS on a source tree unchanged throughout
verification. The [actual gate report](evidence/quality-full-reviewed.json) records
all ten successful steps, base commit, checked tree fingerprint and durations.
The report describes the implementation candidate before this result was appended
to documentation; no implementation changed after the successful gate.

- API/process/PostgreSQL: 926 tests covered (787 non-integration plus 139 real
  PostgreSQL integration tests). Types, web/API lint and production build pass.
- Direct Next proxy: three tests pass. Generated contracts and all 20 decision
  mappings pass. Configuration: 17 tests pass.
- Chromium: all seven tests pass in 39.0 s, including five complete OR cycles.
- Previously timing-sensitive environment/OOM checks: ten consecutive real cycles
  pass. Actual kernel counters, rather than allocation exceptions, establish OOM.
- `git diff --check` and verbatim comparison of all three supplied specs pass.

Logs: `artifacts/or/verification/quality-full-reviewed.log` and
`artifacts/or/verification/browser-reviewed.log`. Intermediate failed runs remain
historical and are not counted as successful verification. This milestone is ready
for the user's commit; full release acceptance remains incomplete.

Useful commands, after installing locked npm/uv dependencies:

```bash
# PP_TEST_DATABASE_URL must identify a dedicated local PostgreSQL *_test database.
node scripts/quality/run.cjs full
npm run test:e2e:install
npm run test:e2e:or
```

The browser command needs no manually configured presenter. It installs no model and
performs no live inventory writes. Ports default to API 8012 / web 3012; override via
`uv run --frozen --directory apps/api python -m scripts.or_browser_tests --api-port 8022 --web-port 3022`.
For standard local commands, expose installed Node/npm/uv on PATH. This session used
`/tmp/pantrypulse-node/node_modules/.bin` and `/tmp/pantrypulse-uv/bin`.
Local ignored logs are under `artifacts/or/verification`; public sanitized result
summaries live under `docs/optimization/evidence`.

## Work remaining after this commit

1. Show the saved scenario's actual frozen multiplier, planning dates and assumptions;
   distinguish them clearly from editable draft controls beside a saved comparison.
2. Bring the saved-result summary ahead of presenter/setup controls on mobile.
3. Explain AP/RP with the saved thresholds and accessible per-beneficiary weights,
   ratios and normalized deficits. Add an immediate per-product gains/losses summary
   using common units. Current raw metrics are persisted; the explanation is missing.
4. Recheck those UI changes in the browser, finish visual/accessibility acceptance
   and complete the remaining OR/V5 documentation/decision-alternative audit. The
   screenshots were reviewed independently; remaining comprehension findings are
   explicit and human taste sign-off has not been obtained.
5. Implement committed authoritative forecast publication and stock/operational
   source adapters, then exercise the actual LIVE source-to-OR journey (OR-A12).
   Pure forecast readiness and a synthetic workflow do not establish this boundary.

Supplier planning and Chronos/model hosting remain paused. OR-A11 and OR-A12 remain
unverified; issue #54 is still open. The user can commit this tested review milestone
before resuming those tasks.
