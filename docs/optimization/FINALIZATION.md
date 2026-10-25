# OR core finalization — October 25, 2026

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
