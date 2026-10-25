# PP-09/10/11: Forecasting core (V4 workstream Task 03)

Date: 2026-10-24. Owner: lead implementation session.
Base: `a0ad11f45bb15a3c3158ed6678f9522652d2a723`; canonical outer workspace.

Implement the supplied forecasting plan's provider-independent preparation,
baselines, validation, evaluation and frozen planning handoff. Follow ADR 0001,
BD-02–10, BD-17, BD-27–29 and the forecasting/API/data rules. Preserve the
user-supplied untracked plan.

Write boundaries: `apps/api/app/services/forecasting/**`, pure
`apps/api/app/services/inventory/projection.py`, corresponding tests,
`apps/api/scripts/evaluate_forecasting.py`, a deterministic expanded fixture,
forecasting documentation, and truthful README/board status.

Internal Pydantic contracts are versioned experimental service contracts, not
new public endpoints. Proposed 14-day/three-sample sparse history is explicitly
configured in the demo; no silent production policy decision. Do not freeze SQL,
public API/job contracts or resume model downloads/hosting/supplier/solver setup.
Pure code cannot qualify live PostgreSQL, a durable supervisor, or Chronos.

Checks: focused expected-value/adversarial forecasting tests, all existing API
tests, Ruff, measured synthetic chronological evaluation and diff checks.
Evidence and remaining OPEN gates: `../forecasting/IMPLEMENTATION.md`.
