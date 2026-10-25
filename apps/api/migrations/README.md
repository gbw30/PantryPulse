# Operational, forecast and planning migrations

Integration candidate head: `ppvp_0007`, joining main `ppor_0005` and VP `pp49_0006` without rewriting either history. It adds canonical plans and append-only simulation reviews. See the [VP review](../../../docs/pantrypulse/VP-API-INTEGRATION.md). PR #75 integrated operational/worker/forecast histories; PR #76 added four immutable planning tables. Earlier revisions and dated application records below are preserved. See [current status](../../../docs/pantrypulse/CURRENT-STATUS.md).

`pp19_0001` implements [operational-v1](../../../docs/pantrypulse/OPERATIONAL-CONTRACT.md)
with 22 domain tables. SQLAlchemy models live in `app/models/operational.py`.
The revision reads frozen sibling SQL files, never mutable current ORM metadata.
Subsequent changes require a new migration. `alembic_version` is an additional
infrastructure table. Main also supplies the five durable-job tables from immutable
revision `0001_jobs_foundation`, per [ADR 0005](../../../docs/architecture/0005-worker-job-queue.md).
Forecast persistence is added by `pp45_0004`; `ppor_0005` adds planning assumptions, scenarios, comparisons and verification records.

`pp21_0002` follows that baseline and adds positive/reversal partial unique indexes
for supply allocations. Both revisions are applied to the selected Neon branch.
The baseline SQL is unchanged. Full internal stock services are now implemented;
see [PP-37](../../../docs/pantrypulse/tasks/PP-37.md). Their HTTP exposure is separate.

`pp_merge_0003` joins `pp21_0002` and `0001_jobs_foundation` into one Alembic head.
Its upgrade/downgrade has no SQL; Alembic applies any missing parent branch first.
The combined schema has 22 operational and five job tables plus `alembic_version`.
Existing published revision files are unchanged. This local integration does not
apply the new head to the user's Neon schema automatically.

`pp45_0004` now follows the merge head. It adds three immutable forecast tables,
presenter sessions, and scoped queue identity constraints, without rewriting any
earlier revision. That revision's schema has 31 application tables plus
`alembic_version`. See [forecast API flow](../../../docs/pantrypulse/FORECAST-API-FLOW.md).
The local demo loader applies this only inside its new `pp45_demo_*` schema;
existing `public` tables/data are not migrated or reset by that command.

## Run an explicit migration

From `apps/api`, using the project environment:

```powershell
.\.venv\Scripts\python.exe scripts/migrate.py upgrade head --env-file .env
.\.venv\Scripts\python.exe scripts/migrate.py current --env-file .env
```

The file must contain exactly one active `DATABASE_URL_UNPOOLED`. No `.env` is
loaded implicitly by the runner. The worker's direct Alembic CLI also accepts an
explicit direct `DATABASE_URL` when `DATABASE_URL_UNPOOLED` is absent; pooled URLs
are rejected. Direct URLs are required for migrations. Credentials are not printed. The default schema is
`public`; `--schema NAME` targets an existing explicitly selected schema.
Importing models or starting FastAPI does not connect or create tables.

Downgrade is explicit and destructive to these tables; test it only on isolated
synthetic data. The runner never drops a schema. Do not downgrade a shared branch
to make a test pass. A supplied test connection retains its current schema unless
an explicit schema attribute overrides it. Do not overwrite either historical root.

## PostgreSQL verification

Set `PP19_TEST_DATABASE_URL` to a dedicated direct test connection and explicitly
set `PP19_TEST_SCHEMA_ISOLATION=1`, then run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_operational_postgres.py -q
```

Tests create a random `pp19_test_<uuid>` schema, exercise actual migrations and
constraints, and remove only that generated schema. They never migrate/reset
`public`. Without both environment values, these integration tests are skipped,
which does not qualify PostgreSQL persistence. Never print/export the URL into
source or shell history. CI should inject it privately.

Worker tests separately use `PP_TEST_DATABASE_URL` naming a dedicated `*_test`
database and isolated `wq_*` schemas. Never point that reset harness at the user's
shared `neondb`. Their historical jobs-only test targets `0001_jobs_foundation`
explicitly; combined-head operational tests verify both metadata collections.

## Enforced boundaries

- SQL: tenant/context FKs, UUID identity, BIGINT count bounds/nonnegativity,
  arithmetic, revisions/duplicate keys, expiry declarations, command key identity,
  confirmed-supply counters and required dates.
- PostgreSQL triggers: append-only history/audit, immutable product units,
  valid site calendars and receipt days, complete immutable receipt line sets,
  and bounded supply allocation/reversal amounts across rows.
- Caller-owned repositories: scoped reads and complete historical receipt writes
  without stock changes; no independent commit inside a repository.
- Issue #21 now supplies exactly-once stock posting/correction services,
  ledger/balance consistency checks, expected versions, idempotent replay and real
  concurrency evidence. These require caller-owned transactions and trusted actor
  context; schema constraints alone are not a substitute for the services.

The new Neon branch supplied by the user is the authorized target; old commented
connections are not used. See [PP-35](../../../docs/pantrypulse/tasks/PP-35.md) for
the exact test/installation evidence and limitations.
