# ADR 0004: Worker and job queue foundation decisions

> **Authority:** [Project specification V5](../pantrypulse/SPEC-V5.md) §§12–13 and BD-11/12/30/31/34–38 remain the accepted requirements. This ADR records the lead's review of the technical proposals in [WORKER-JOB-QUEUE-SPEC.md](../pantrypulse/WORKER-JOB-QUEUE-SPEC.md) (WQ-D01–D11) for the internal foundation packages WQ-01–06 only. It does not close OPEN-29/30/31/33/35, expose public routes or select deployment.

Date: 2026-10-24. Base: main `04df41ced650896bd4f4a4cd10de1354b406d216`. Status: accepted for the internal foundation; items marked **USER CONFIRM** stay provisional until the user confirms them.

## Decisions

| ID | Decision |
|---|---|
| WQ-D01 | Accepted. One `default` lane serialized by `SELECT … FOR UPDATE` on `compute_control`; PostgreSQL 16, SQLAlchemy Core, psycopg 3, Alembic. No broker. |
| WQ-D02 | Accepted. Stable job, immutable attempts, the nine attempt states and the transition table in §5.1; manual retry from FAILED/TIMED_OUT/INTERRUPTED/EXPIRED/CANCELLED only. |
| WQ-D03 | Accepted. Global FIFO `(enqueued_at, attempt_id)`, at most two QUEUED, no API-reserved active slot. A third submission while two wait and none runs is rejected with `COMPUTE_QUEUE_FULL`; the UI must say so (WQ-09). |
| WQ-D04 | Accepted. Queue expiry at `now >= queue_deadline_at`; heartbeat fresh only when `0 <= age < 15 s`; a future heartbeat fails closed. Database `clock_timestamp()` is the persisted clock. |
| WQ-D05 | Accepted. Generation + per-attempt UUID token fence publication, heartbeats and finalization. Stale owners are recovered, never silently taken over. |
| WQ-D06 | Accepted with amendment A1. |
| WQ-D07 | Accepted. Jobs-only schema; accepted-command idempotency keyed by `(organization_id, action, idempotency_key)`. |
| WQ-D08 | Accepted with amendment A2. |
| WQ-D09 | Accepted. Atomic publisher interface; uncertain COMMIT is reconciled by attempt identity and recorded in audit, never recomputed. A confirmed-absent result after uncertainty finalizes FAILED `PUBLICATION_COMMIT_LOST` (manual retry). |
| WQ-D10 | Accepted. Drain, immediate controlled stop and crash recovery as §11.3; no automatic deletion. |
| WQ-D11 | Deferred to WQ-09 (OPEN-29/31). Error codes are defined internally; no routes are added. |

## Amendments

**A1 — containment evidence and quarantine (WQ-D06).** A lost active attempt is finalized INTERRUPTED only with concrete evidence: (a) same kernel boot and PID namespace, and a `/proc` scan shows the recorded process group empty after any owned members are killed; or (b) the kernel boot identity changed, so no process from the old boot can exist. Anything else (different PID namespace on the same boot, unreadable `/proc`, a non-Linux host) quarantines the lane and keeps the slot. A quarantined supervisor keeps heartbeating, keeps saved reads available, re-checks evidence periodically and accepts an explicit operator attestation through `python -m app.workers.admin attest-cleanup`; the attestation is recorded as `OPERATOR_ATTESTATION` evidence, never as automatic proof. **USER CONFIRM:** operator attestation is acceptable recovery evidence for the demo.

**A2 — process containment (WQ-D08).** Linux only: each step runs in a fresh child started with `start_new_session=True` (own process group), which sets `PR_SET_PDEATHSIG=SIGKILL` and exits if its parent already changed. Stop = `SIGTERM` to the group, `SIGKILL` after the grace or at the hard cutoff, then a `/proc` group scan must confirm it empty. Identity = boot id + PID-namespace inode + pgid + leader pid + leader start ticks; a bare PID is never used. Descendants that leave the process group (`setsid`) are outside the guarantee; registered handlers must not do that. Native Windows has no driver: the capability check fails and the supervisor never reports READY there.

**A3 — heartbeat from ownership.** The owner writes heartbeats from the moment it acquires the lane (including STARTING/RECOVERING/QUARANTINED) so a second supervisor cannot take over during recovery. Admission still requires state READY, so a startup heartbeat never admits work.

**A4 — budgets and steps.** Operation budgets: FORECAST 300 s, ALLOCATION 25 s, COMPARISON 60 s. Each handler declares sequential steps; forecast primary is hard-stopped by 270 s, a fallback step runs only after a timed-out or classified-failed primary, each comparison method is capped at 25 s inside the 60 s parent and is NOT_RUN if the remaining parent budget is below its minimum. Soft stop (SIGTERM) = hard cutoff − 2 s grace; force stop (SIGKILL) = hard cutoff − a 0.25 s kill margin, so termination latency still meets the cutoff (forecast primary: 268/269.75/270 s). An exit observed after the cutoff is recorded as `cutoff_breach_s` on the step and its output is never publishable. The attempt-level deadline is only a backstop: it fires at the hard deadline, or at budget − grace when no step is running, so it cannot pre-empt a step's own cutoff. A configurable publication reserve (initial 2 s, an engineering value, not a BD value) is kept inside the budget. Production values are asserted by policy tests; integration tests use explicit short profiles.

**A5 — capability advertisement.** The supervisor records effective limits, its registered handler contracts and its containment capability in `compute_control.effective_limits`. Admission rejects a contract the running supervisor does not advertise.

**A6 — test handlers.** Fixed test handlers live in `app/workers/testing.py` and load only through the named `test` registry. The `production` registry is empty until WQ-07/08. Fixture results go to a table that only the tests create; every fixture manifest is labeled `TEST_INFRASTRUCTURE_ARTIFACT`.

**A7 — acceptance scope.** WQ-01–06 target WQ-T01–T23, T26 and T27. WQ-T24/T25 wait for public routes (WQ-09) and WQ-T28 for runtime limits (WQ-10); they are reported NOT RUN, not passed. **USER CONFIRM:** this is the P0 test scope for the foundation.

**A8 — input identity.** The input hash covers the package exactly as JSONB stores it (JSONB rewrites values such as `-0.0` or `1e16`), and the handler must re-validate that stored form unchanged; input that changes on storage or cannot be stored (e.g. a NUL character) is rejected at submit with `INPUT_NOT_REPRESENTABLE`, never accepted and failed later.

## Rollback trigger

Revert to this ADR's base if PostgreSQL row locking cannot keep the two-waiter bound under concurrent tests, or if Linux group containment cannot confirm cleanup in the Docker runtime.
