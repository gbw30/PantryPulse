---
paths:
  - "apps/api/app/models/**/*.py"
  - "apps/api/app/repositories/**/*.py"
  - "apps/api/app/services/inventory/**/*.py"
  - "data/demo/**/*"
---

Use transactions, nonnegative stock constraints and expected inventory versions. Exclude expired and reserved lots once, not twice. In v1 an import creates an immutable dataset version atomically (all or nothing, including the network) and writes no stock events; plans are simulations with no approval or completion. Never mutate a dataset version for a scenario. There is no in-app reset in v1 (start over with `docker compose down -v`). For the P1 stock services that stay in the code: approval/reservation and completion are separate events, and a completed transfer moves stock exactly once. Lead owns migrations.
