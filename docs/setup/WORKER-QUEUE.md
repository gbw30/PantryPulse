# Internal worker queue foundation

The production registry contains `forecast.v1` and `or-comparison.v2`. Presenter API
admission, immutable domain publication and `/optimization` use this shared lane.
See [approved connected integration](../optimization/CONNECTED-INTEGRATION.md).
Native Windows cannot provide the Linux boundary and never reports compute READY.

Solver defaults are 120s native / 150s method / 330s comparison; maximum settings
are 300s / 330s / 690s. Queue expiry is 1,800s, with one active and two waiting jobs.
Capability advertisement version 2 is required; restart old supervisors after migration.
Forecast limits remain 270/300s. Drain grace is 720s; container stop grace is 725s.

## Schema and startup

Use a dedicated PostgreSQL 16 database. From `apps/api`, with `DATABASE_URL` supplied privately in the process environment:

```sh
uv run --frozen alembic upgrade head
uv run --frozen python -m app.workers.admin status
uv run --frozen python -m app.workers.supervisor --registry production
```

The current Alembic head is `ppor_0005`, following the preserved worker/operational
merge and forecast migration. It adds immutable planning assumptions, scenarios,
comparisons and method verification records. Pass `--schema` to the supervisor and
`PP_DATABASE_SCHEMA` to the API for an isolated demo. Do not expose the test registry.

One lane permits one active attempt and at most two waiting attempts. Heartbeats run independently; a separate watchdog enforces child deadlines even while database I/O blocks. Finalization and publication remain transactional and fenced. A child stopping does not free its slot until cleanup is confirmed and recorded.

## Shutdown and recovery

- SIGTERM drains: reject new work, finish the active attempt within its deadline, retain queued work, then exit.
- SIGINT requests an immediate controlled stop and records interruption after cleanup. Queued work remains durable.
- A lost supervisor is recovered by a new generation. It never automatically retries an interrupted job.
- Missing boundary identity (including a crash between sequential steps), inaccessible `/proc` or an unverifiable PID namespace quarantines the lane. Saved reads remain possible. Never clear control/attempt rows manually to force availability.

The internal operator command below records an attestation, not automatic containment proof. A1 in the ADR remains provisional for demo deployment. Use only after independently establishing that the old execution boundary is gone, with an attributable operator and evidence note:

```sh
uv run --frozen python -m app.workers.admin attest-cleanup --attempt ATTEMPT_UUID --operator OPERATOR_REF --note "Evidence that the old boundary is gone"
```

Process-group containment excludes descendants that call `setsid`; registered handlers must not escape their group. Boundary identities contain an internal nonce and must never be returned by future public status routes. The advertised 6 CPU / 8 GiB profile is not evidence of measured resource enforcement.

## Verification

From `apps/api`, set `PP_TEST_DATABASE_URL` to a disposable database whose name ends in `_test`, then run:

```sh
uv run --frozen pytest -q
uv run --frozen ruff check .
```

Integration tests reset their own test schemas. Without that variable they skip; Linux containment and real supervisor tests also skip on native Windows. Skips mean NOT RUN. Preserve the repository layout when testing in Docker: mount the whole checkout at `/repo`, run from `/repo/apps/api`, and use the image's installed Python environment. The forecasting fixture reads `/repo/data/demo`; mounting only API sources at `/app` omits that data and is not a full-suite test.

The review includes regressions for blocked database I/O with real Linux child/descendant termination, crashes before recording a later step's boundary, cancellation during uncertain COMMIT reconciliation, finalization outages without automatic reruns, and unreadable containment evidence. The [task packet](../pantrypulse/tasks/PP-31.md) records final results. Public-route/CSRF tests T24/T25 and measured resource limits T28 are outside this foundation's verified scope.
