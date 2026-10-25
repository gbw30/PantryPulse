# OR-PURE

Issues: 11, 23, 25, 56. Owner: input / projection lane; lead integrates/reviews.
Base: f3946c726e53fa546be1400d80ab717fcb2c3468; workspace: current repository, disjoint write boundaries for user-requested parallel work.
Inputs: docs/optimization/01..03 Draft 1.1; V5.
Allowed: apps/api/app/schemas/or_inputs.py, or_outputs.py; optimization/{canonical,decisions,forecast_adapter,scenario,packing,candidates,metrics,verify}.py; inventory/projection.py or shared kernel; tests/optimization excluding oracle and solver tests; data/demo/or-v1. Excluded: other lanes, shared locks/config/main.
Goal: Strict frozen schemas, adapter, pure dated simulation/checker and fixtures. Publish callable contract early to lead. No CP-SAT imports.
Acceptance: Python 3.12 focused pytest and Ruff; expected exact spec arithmetic, explicit remaining gates. Use /tmp/pantrypulse-forecast-venv/bin/python until frozen environment available.
Review: lead and independent lane; do not self-certify full integration.
Stop: report missing dependency or required out-of-bound edit; retain unrelated changes.
Handoff: diff, commands/results, assumptions and precise remaining limitations; no push/merge/deploy.
