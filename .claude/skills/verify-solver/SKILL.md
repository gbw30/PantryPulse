---
name: verify-solver
description: "Verify PantryPulse transfer invariants, statuses, integer formulation and replay."
---

Use independent arithmetic, not only solver-generated summaries. Execute the golden fixture and zero-stock, reserve-bound, capacity-bound, no-route, unavoidable-shortage, UNKNOWN and MODEL_INVALID cases. Confirm donor budgets include local need/reserve, receiving and handling capacity hold, and quantities stay in category units. Recalculate before/after with identical inputs. Validate returned vectors independently. Confirm replay snapshots and tied-solution semantics. Run focused solver tests. Report native status, objective, violations and evidence.
