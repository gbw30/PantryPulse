---
paths:
  - "apps/api/app/routers/**/*.py"
  - "apps/api/app/schemas/**/*.py"
  - "packages/contracts/**/*"
---

Pydantic/OpenAPI is the API authority. Keep /api/v1 routes and error envelope stable. Validate UUIDs, finite numbers, category/unit compatibility and site-local dates. Missing IDs return 404, invalid business inputs 422, stale versions 409. Export OpenAPI without starting inference or requiring production credentials. Regenerate TypeScript types; never hand-edit generated output. No model inference on dashboard GET. Bound forecasts and optimizer work; retain error states and request IDs.
