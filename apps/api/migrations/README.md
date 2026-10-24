# Migration boundary

Alembic is configured (`alembic.ini`, `env.py`). Revision `0001_jobs_foundation` creates only the durable-job tables (`compute_control`, `compute_jobs`, `compute_attempts`, `compute_commands`, `compute_audit_events`) per [ADR 0004](../../../docs/architecture/0004-worker-job-queue.md). No domain schema exists yet: follow [Project specification V5](../../../docs/pantrypulse/SPEC-V5.md), especially OPEN-04–11/19/25/36, before defining domain models and migrations. The lead owns migrations.

`env.py` reads `DATABASE_URL`; tests pass an open connection instead. Test upgrade/downgrade and integrity against an isolated PostgreSQL test database (`tests/integration/test_job_migrations.py`, which needs `PP_TEST_DATABASE_URL` naming a `*_test` database). The research gate separately controls complex solver work. Do not run migrations against unrelated databases.
