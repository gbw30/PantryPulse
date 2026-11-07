# W0 decision: v1 optimizes per product; network-wide optimization is the next milestone

**Status:** decided by Gabriel, 2026-11-04, after spike S1 ([S1-optimizer.md](../spikes/S1-optimizer.md)). **Applies to:** W0-08 (contract and caps), W0-10 (re-plan of W1-S05), and the `w1-solver` and `w3-web` lanes.

## Decision

1. **Every v1 method solves one CP-SAT model per product.** By default only **at-risk** products are solved, meaning those where the no-transfer FEFO kernel projects unmet demand (Pantry: inside the allocation window; Retail: unmet demand or expiry within 7 days). Products that are not at risk get no transfers, and the result says so.
2. **Shared capacity is split between products before solving.** Route, receiving, source and global handling capacity are divided by each product's kernel need share, rounded down. An independent union check confirms that the combined plan respects every shared limit. Storage is not binding.
3. **Fairness and the EGP terms are per product.** The classical GP Z term and the EGP AP/RP normalization apply within each product, so a network total is the sum of per-product optima, not one network optimum.
4. **Honest labeling (required).** The methodology screen, the comparison view, plan exports and the API methodology response say that results are "optimized per product, with shared capacity split in advance", and name which products were solved. `research-claims-check` runs on that wording. EGP_PI_INSPIRED remains a bounded adaptation of Rampazo et al. (DOI 10.1111/itor.70252), applied per product.
5. **Next milestone, not v1:** a single network-wide objective. S1 showed that the bottleneck was Python model building, not CP-SAT. Solver time for one 100 × 500 model was never measured, so this needs its own spike. It joins the full-state / 60,000-SKU milestone (V1-D05).

## Evidence (S1, 6 CPUs, native WSL)

| Variant | Pantry CL | Pantry EGP | Retail |
|---|---|---|---|
| Single model, all or at-risk products | build did not finish in 330 s | same | same |
| Per product, all 500 | 253.7 s, 500/500 verified | 298.6 s (pair 554.4 of 690 s) | 251.7 s, 500/500 verified |
| Per product, at-risk (194) | 147.3 s, 194/194 verified | 167.4 s (pair 316.7 s) | 96.1 s (lead re-run 119.8 s), 194/194 verified |

V1-D15 step reached: **1**. No lower envelope and no raised ceilings.

## Open items carried to W0-10

- Independent review of the spike's capacity split and coupling check (verifier) before `w1-solver` copies the approach.
- Record per-product gaps for FEASIBLE (not OPTIMAL) products, and show FEASIBLE products honestly.
- The pool workers hold ~4.9 GB in total (six scenario copies). Keep that under the 8 GiB worker limit when a network has more at-risk products.

## W0-10 review of the spike (verifier, 2026-11-06)

- The split never exceeds a shared limit, and the spike's `coupling_check` is independent of it and catches a planted violation. Both hold.
- Corrections that W1-S05 carries as tests: split by need × handling units, not raw units; report products whose share is below one unit's handling (170 of 194 at-risk products in the spike); split the cost budget, which the spike copied whole to every product; make storage bind across products; assert the union check instead of only logging it.
- §3 is too strong: per-product objectives don't sum to a network optimum, and FEASIBLE products add time-limit noise (the EGP total moved from 949.51 to 955.88 between runs). Report per-product status and gap, and network totals of physical quantities only.

## Retail USD shared-capacity split (CR-w1-solver-2, Gabriel, 2026-11-07)

In Retail USD mode, shared receiving capacity is split across products in proportion to `need × handling_units_per_unit × unit_value_usd`, so the decomposed solve values capacity the way the USD objective does. Units mode keeps the need-weighted split. Built by w1-solver.
