# PostgreSQL migrations

The shared queue owns revision `0001_jobs_foundation`. OR Draft 1.1 adds
`0002_or_snapshots`: immutable input packages, policies, complete scenarios, verified
plans/transfers/checks, comparisons, append-only reviews/audit, presenter session
hashes, and a simulated dataset revision/epoch fence. OR tables reference the
existing queue through organization-scoped foreign keys; there is one compute
lane and no new stock ledger.

Run from the repository root with a dedicated local database URL in `DATABASE_URL`:

```bash
uv run --frozen --directory apps/api alembic upgrade head
```

`DATABASE_URL` is read at runtime; never put credentials in `alembic.ini` or source.
Migrations accept an explicit SQLAlchemy connection for isolated integration tests.
The tests require `PP_TEST_DATABASE_URL` naming a database ending in `_test`; OR
persistence tests create/drop only a random schema they own:

```bash
uv run --frozen --directory apps/api pytest tests/integration/test_or_persistence.py -q
```

Missing PostgreSQL configuration skips these tests and does not establish database
acceptance. SQLite does not qualify PostgreSQL constraints, triggers, transactions,
concurrent idempotency, or migration evidence.

OR-DEC-009/012/015/020 remain provisional draft choices. Snapshot/result/review/audit
updates and deletes are denied by database triggers. A deferred constraint trigger
requires a passed verification in the same transaction as a plan. Paired-plan
identity checks require the same scenario, attempt, job, organization and settings,
with classical and research methods in their respective positions. Repository
publication also independently replays a candidate, checks its objective, and
requires the shared supervisor's current owned running attempt and dataset epoch.

A demo reset advances only an explicitly registered demo dataset's epoch after
its compute work is quiescent. It preserves immutable snapshots/results/audit for
historical reading. The supervisor must cancel queued work and terminate/reap its
running child before calling the storage reset; storage rejects an active scope.
Reseeding can create new scenario rows in the new epoch without altering old rows.
This is no physical stock change or production reset mechanism.

Source inventory/receipt/forecast publication remains an upstream responsibility.
Arbitrary client `LIVE` stock cannot bypass the trusted read-port boundary.
