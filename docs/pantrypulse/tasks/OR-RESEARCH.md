# OR-RESEARCH

Issues: 10, 38. Owner: research lane; lead integrates/reviews.
Base: f3946c726e53fa546be1400d80ab717fcb2c3468; workspace: current repository, disjoint write boundaries for user-requested parallel work.
Inputs: docs/optimization/01..03 Draft 1.1; V5.
Allowed: docs/optimization/RESEARCH-MAPPING.md, NUMERICAL-PROOF.md, research evidence; apps/api/scripts/or_enumerate.py; apps/api/tests/optimization/test_or_oracle.py. Excluded: other lanes, shared locks/config/main.
Goal: Checked full text mapping and independent Fraction oracle and proofs. No solver implementation.
Acceptance: Python 3.12 focused pytest and Ruff; expected exact spec arithmetic, explicit remaining gates. Use /tmp/pantrypulse-forecast-venv/bin/python until frozen environment available.
Review: lead and independent lane; do not self-certify full integration.
Stop: report missing dependency or required out-of-bound edit; retain unrelated changes.
Handoff: diff, commands/results, assumptions and precise remaining limitations; no push/merge/deploy.
