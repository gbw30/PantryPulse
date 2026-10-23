---
paths:
  - "apps/api/app/services/optimization/**/*.py"
  - "apps/api/tests/optimization/**/*.py"
---

Encode inventory, reserve, receiving capacity, category compatibility, no self-transfer and total handling budget as hard constraints. CP-SAT uses integer coefficients; record rounding and scaling. Shortages have explicit slack; do not declare inadequate supply itself infeasible. Check feasibility independently after solve. Preserve OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN/MODEL_INVALID. Only claim global two-stage optimality if both stages prove it.
