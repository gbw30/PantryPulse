> Historical task packet. The user withdrew its adjacent-layer ownership; read [current OR scope](../../optimization/SCOPE.md) and [execution revision 1.2](../../optimization/03_OR_Codex_Execution_Spec.md). Do not use this packet to reintroduce frontend, routes, DB or shared-worker work.

# OR-API

<!-- current-source-audit-2026-10-25 -->
> **Source audit — October 25, 2026:** This task packet preserves its original requirements, ownership and source-bound evidence. Its local/TODO/paused wording is not current merged status. See [current status](../CURRENT-STATUS.md), [the board](../BOARD.md) and [SPEC-V5](../SPEC-V5.md); do not infer new agent assignments or a fresh test pass from this record.

Issues #32/#33/#34; owner API/auth integration lane, lead reviews.
Base f3946c726e53fa546be1400d80ab717fcb2c3468 plus current disjoint OR/queue implementation.
Allowed: app/routers/or_api.py, schemas/or_http.py, services/or_access.py,
services/or_runtime.py, main.py registration, tests/integration/test_or_http.py.
Inputs: OR Draft1.1 schemas, canonical shared queue and OR repository. No second
queue or ledger; no worker or source calculation on saved GET/probes.
Acceptance: real PostgreSQL HTTP lifecycle/security and OpenAPI schema checks;
root completes generated contract/client and persisted real solve journey.
No locks/worker/policy edits. Preserve process health contract. No deployments.
