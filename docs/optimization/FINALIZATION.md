# Connected OR-v2 finalization — October 25, 2026

The user approved the full [connected integration plan](CONNECTED-INTEGRATION.md),
superseding the earlier OR-only/no-proxy boundary for this change. Current main
`aadd2d2` and latest OR head `465d026` were reconciled on `codex/or-connected-review`.
The retained core, objectives, independent verifier, model reductions, fixtures and
qualification tools are preserved. Withdrawn API/UI/storage implementations were
not restored wholesale. Historical v1 evidence below remains unchanged in meaning.

The connected presenter flow now persists forecasts, freezes coherent tenant-owned
source snapshots, executes a durable sequential comparison, independently verifies
each method, and saves immutable results. Revisions create new scenarios/assumption
versions. A verified method survives its partner's failure. Inclusive DATED expiry,
explicit NON_EXPIRING and excluded UNKNOWN stock use new v2 contracts and hashes.

Search defaults to 120 seconds per method and accepts 1–300 seconds. Frozen method
and pair allowances are search + 30 and 2 * method + 30 seconds: 150/330 by default,
330/690 at maximum. Comparisons reserve 30 seconds for final verification/publication;
queue expiry is 30 minutes with one active/two waiting. Forecast limits remain intact.
Offline parent replay also rejects late output; filesystem serialization is not an
operating-system real-time guarantee. Linux worker ownership/deadline fences govern
application publication.

### Final local evidence

[Source manifest and gate summary](evidence/connected-review-v2.json) binds the
reviewed source files using LF-normalized SHA-256. Exact executable commands are in
the Linux CI workflow; local execution used the locked Python 3.12.13 Linux image,
OR-Tools 9.15.6755, PostgreSQL 16 and Node 24.16.0.

| Gate | Result |
|---|---|
| Complete backend, real Linux processes and isolated PostgreSQL | **1140 passed, zero skipped**, 217.54 seconds; [JUnit](evidence/connected-backend-v2.xml) |
| Full Chromium suite against production build and actual proxy/API/database/worker | **9 passed, zero skipped**; [transcript](evidence/connected-browser-v2.txt) |
| TypeScript / ESLint / Ruff / production build | PASS |
| Configuration / proxy unit tests | **17 / 3 passed** |
| Generated OpenAPI and TypeScript contract drift | PASS |
| Fresh migrations, immutable history, tenant isolation and concurrent idempotency | PASS in complete backend suite |
| Dense native budget sweep, two modes x five budgets x two methods | **20 independently verified outcomes**, all FEASIBLE; [qualification](BUDGET-QUALIFICATION-V2.md) |

The browser suite exercises login, genuine persisted forecast generation, frozen
scenario creation, comparison, refresh/reconnect, revised assumptions/scenario,
cancellation/retry and a real killed partner retaining the verified survivor.
Keyboard interaction, reduced motion, axe checks and overflow assertions pass at
[1440x900](evidence/connected-1440-v2.png),
[1280x720](evidence/connected-1280-v2.png) and
[390x844](evidence/connected-390-v2.png). Human taste approval is not inferred.
The Linux suite includes a real 31-second method, worker loss, cleanup, cancellation
and publication fencing; skipped Linux tests do not satisfy the gate.

Review fixes include equal-timestamp catalog pagination, exact execution identity,
explicit publication reserves, late offline replay handling, source history
freshness, concurrent scenario command replay and independent invalid-partner
isolation. A stale generated Next cache caused a local compiler subprocess failure;
a clean production build passed. Existing Starlette/httpx and Node module-format
warnings are non-blocking and are not concealed as test failures.

At 300 seconds, classical/research gaps were 0.24%/1.18% (hub-only) and 1.23%/3.71%
(hub-and-pantry). Longer search improved these measured cases but did not prove
optimality. Policy remains a simulated editable preset. Operational confirmed
supply without declared expiry is explicitly rejected by the connected adapter.
Hosting, Chronos, supplier planning, visitor access, operational dispatch, broad
scenario support, general import UI and production reset remain outside this PR.

PR creation and merge follow the local gates; remote Linux CI must also pass before
merge. The PR is the authoritative merge/check record. No unresolved local blocking
review finding remains.

---

## Historical OR-v1 core finalization — October 25, 2026

Base `1cd0cf7`; original working tree clean. User requested finishing the remaining
OR-only tasks: pair identity hardening, upper-scope performance/policy sensitivity
qualification, and research/decision evidence reconciliation. Tracker #54; bounded
schema/tooling documentation #55/#57, assigned to GestebanFalcon.

Allowed writes: OR optimization modules/tests, OR input/output schemas if necessary,
OR computational CLI/qualification scripts, fixtures and docs/optimization. No
frontend, API route/auth, database, migration, public contracts, shared worker,
package/CI configuration or original inventory/forecast implementation changes.
Protected file hashes are captured under ignored artifacts/or-finalization.

Use actual native CP-SAT, independent checker/oracles and bounded offline execution.
Keep policy values provisional; diagnostic sensitivity does not silently select a
new policy or imply observed fairness/poverty reduction. Record exact scenarios,
settings, native statuses, bounds/gaps, timings and limitations. Final evidence is
added after execution; no hosted/shared-runtime acceptance is claimed.

Stop after the completed tested OR milestone for the user's commit. No automatic
commit, push, merge, deployment or external ownership expansion.

## Completed milestone

Comparison assembly now validates the frozen scenario and every outcome's policy,
mode, operational/settings hashes, historical intent and decision identities across
success/partial/failure states. Verified results require a matching reconstructed
physical fingerprint and independent candidate/report/objective replay. Callers and
the offline compare CLI bind results to expected settings. Pre-build failures may
omit a fingerprint and remain independent failures.

Native qualification exposed dense-model overhead. The common builder now omits
fixed-zero route trajectories, zero-demand/zero-balance recurrence steps and forced
zero post-H proposed inbound, and reuses identical no-inbound donor projections.
The algebraic proof, native tiny feasible-vector tests and size-bound forced-zero
service/expiry/balance check preserve the physical feasible region.

[Qualification](QUALIFICATION.md) completes five scale and nineteen sensitivity
pairs: 48 independently verified outcomes. It records source/code/settings identities,
native OPTIMAL versus FEASIBLE, bounds/gaps, model size/activity and actual timings.
Dense cases still have large optimality gaps; useful near-optimal results for all
ceiling-sized inputs are not guaranteed. Policy defaults and schema identities are
unchanged. Diagnostic alternatives do not select a new operational policy.

Twenty decision records now have concrete alternatives/limitations; current choices
011/013/015/016/020 explicitly stay inside OR. Historical external choice 012 and
withdrawn Next proxy choice 014 remain clearly marked. Research mapping and emitted
model proof obligations now point to current native evidence rather than the old
pre-solver UNVERIFIED checkpoint. The paper is still an inspiration, not a full
reproduction or evidence of real-world social outcomes.

## Final verification

Base: `1cd0cf7f45cec0df8bdd6ea89fe5568317d6bf3d`; no automatic commit/stage/push.
Environment: Python 3.12.13, OR-Tools 9.15.6755, Linux x86_64/glibc 2.39.

| Command from repository root | Result |
|---|---|
| `PATH=/tmp/pantrypulse-node/node_modules/.bin:/tmp/pantrypulse-uv/bin:$PATH npm run check` | PASS: TypeScript, ESLint, API Ruff, all 641 Python tests (153 OR); 41.80s pytest |
| Same PATH, `npm run test:config` | PASS: 17 tests |
| `apps/api/.venv/bin/python scripts/or/qualify.py --output artifacts/or-finalization/qualification-full.json` | PASS: 24 real bounded pairs, 48 verified outcomes; 42 OPTIMAL, six FEASIBLE |
| `apps/api/.venv/bin/python scripts/or/qualification_summary.py --input artifacts/or-finalization/qualification-full.json --output docs/optimization/evidence/qualification-final.json` | PASS: compact goal vectors/objectives/statuses checked against full report |
| `python scripts/or/check-decision-markers.py` | PASS: 18 core decisions; two external/withdrawn; all fixture IDs retained |
| Ruff check/format on changed OR Python and both root scripts | PASS |
| `git diff --check`, protected hashes and changed-path allowlist | PASS; no deleted paths or adjacent code changes |

The focused comparison regressions were first run against the previous implementation
and exposed missing identity/replay checks. The final complete suite covers them,
independent exact enumeration, native strict AP/RP boundaries and ablations, CLI exit
codes and real process termination; no final test was skipped to obtain green.
The suite emits one existing Starlette/httpx deprecation warning. No PostgreSQL,
browser, build/deployment, new dependency, model download or shared CI change was
needed or claimed. Full logs and detailed native output remain under ignored
`artifacts/or-finalization/`; compact durable evidence lives beside this record.

Ownership evidence is in [evidence/finalization.json](evidence/finalization.json).
All 41 adjacent protected files match their starting SHA-256 values. This milestone
contains no deletion and preserves the two imported worker reference documents.
The previous scope-correction archive remains untouched. API/storage/shared-runtime
integration, live-source validation, domain policy approval and supplier/Chronos/
hosting work remain with their prior owners/statuses.

The OR-only implementation/finalization milestone is ready for the user's commit.
Suggested message: `feat(or): finalize verified comparisons and qualification`.

GitHub #54/#55/#57 now carry this current OR-only status and evidence pointers,
preserving their prior bodies and open state. Assignment remains GestebanFalcon.

Integration PR: [#76](https://github.com/gbw30/PantryPulse/pull/76). Its checks and merge record bind the final reviewed head.
