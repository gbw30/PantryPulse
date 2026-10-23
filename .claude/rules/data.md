---
paths:
  - "apps/api/app/models/**/*.py"
  - "apps/api/app/repositories/**/*.py"
  - "apps/api/app/services/inventory/**/*.py"
  - "data/demo/**/*"
---

Use transactions, nonnegative stock constraints and expected inventory versions. Exclude expired and reserved lots once, not twice. Approval/reservation and completion are separate events. Completed transfer decreases origin and increases destination exactly once. Never mutate the historical dataset for a scenario. Demo reset must be scoped to a dedicated demo organization and must not target non-demo data. Lead owns migrations.
