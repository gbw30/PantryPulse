# OR-API

Issues #32/#33/#34; owner API/auth integration lane, lead reviews.
Base f3946c726e53fa546be1400d80ab717fcb2c3468 plus current disjoint OR/queue implementation.
Allowed: app/routers/or_api.py, schemas/or_http.py, services/or_access.py,
services/or_runtime.py, main.py registration, tests/integration/test_or_http.py.
Inputs: OR Draft1.1 schemas, canonical shared queue and OR repository. No second
queue or ledger; no worker or source calculation on saved GET/probes.
Acceptance: real PostgreSQL HTTP lifecycle/security and OpenAPI schema checks;
root completes generated contract/client and persisted real solve journey.
No locks/worker/policy edits. Preserve process health contract. No deployments.
