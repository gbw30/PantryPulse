---
paths:
  - "apps/api/app/services/optimization/**/*.py"
  - "apps/api/tests/optimization/**/*.py"
---

Encode inventory, reserves, every capacity the scenario gives (receiving, dispatch, storage, route per-batch, global handling; a blank capacity means no limit, V1-SPEC §6.1), category compatibility, no self-transfer and any cost budget as hard constraints. In v1 each product is solved separately: split shared capacity and the cost budget between products in advance, then assert an independent union check over the combined plan (decisions/W0-optimizer-decomposition.md, W1-S05). CP-SAT uses integer coefficients; record rounding and scaling. Shortages have explicit slack; do not declare inadequate supply itself infeasible. Check feasibility independently after solve. Preserve OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN/MODEL_INVALID. Only claim global two-stage optimality if both stages prove it.
