> Historical task packet. The user withdrew its adjacent-layer ownership; read [current OR scope](../../optimization/SCOPE.md) and [execution revision 1.2](../../optimization/03_OR_Codex_Execution_Spec.md). Do not use this packet to reintroduce frontend, routes, DB or shared-worker work.

# OR-STORAGE

Issues: 19, 30. Owner: persistence lane; lead integrates/reviews.
Base: f3946c726e53fa546be1400d80ab717fcb2c3468; workspace: current repository, disjoint write boundaries for user-requested parallel work.
Inputs: docs/optimization/01..03 Draft 1.1; V5.
Allowed: apps/api/app/models/or_*.py; repositories/or_*.py; apps/api/migrations; apps/api/alembic.ini; tests/integration/test_or_persistence.py. Excluded: other lanes, shared locks/config/main.
Goal: PostgreSQL schema/repositories, immutable records/scoped FKs/audit/reviews. No queue implementation except shared table definitions, no stock ledger.
Acceptance: Python 3.12 focused pytest and Ruff; expected exact spec arithmetic, explicit remaining gates. Use /tmp/pantrypulse-forecast-venv/bin/python until frozen environment available.
Review: lead and independent lane; do not self-certify full integration.
Stop: report missing dependency or required out-of-bound edit; retain unrelated changes.
Handoff: diff, commands/results, assumptions and precise remaining limitations; no push/merge/deploy.
