# OR runtime integration

Issues #13–18/#31/#44. Base f3946c7, existing worker source imported from d7e44ed.
Owner: runtime lane; lead reviews and integrates. User requested parallel work.

Allowed: apps/api/app/{workers,services/jobs,repositories/jobs.py}; tests/jobs,
tests/workers, tests/integration/test_or_jobs.py; migration 0003 only in coordination
with storage's 0002. Exclude OR handler/publisher implementation (lead), OR records,
other tests and shared locks/main.

Extend existing shared executor rather than create another queue. Add optional
parent-only fenced per-step publisher hook (publish_step(connection, identity,
validated, outcome)) after child cleanup and before starting partner. It must
retain checked first-method result if partner fails/cancelled/interrupted.
Allow final domain manifest outcome SUCCEEDED/PARTIAL/FAILED while retaining causal
timeout/cancel/interruption states. Keep backward compatibility for existing test
publishers. Integrate org epoch fence through OR publisher hooks, not new queue.

Enforce effective Linux CPU ceiling 6 equivalents and aggregate descendants memory
8 GiB where possible, demonstrate actual enforcement; report limitations precisely.
No child DB credentials. Deadline stop/kill/reap and cleanup remain shared behavior.
Add meaningful real-process and PostgreSQL tests with PP_TEST_DATABASE_URL dedicated
pantrypulse_or_test database only. Run focused tests and Ruff; hand off exact results.
No merge/push/deploy. Two failed fixes: report counterexample to lead.
