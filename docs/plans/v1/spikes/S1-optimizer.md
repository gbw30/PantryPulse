# S1: optimizer at 100 locations × 500 products (W0-02, V1-SPEC §12 item 1)

Status: measured spike. The code is throwaway, on branch `spike/w0-s1` (base `ed3eb32`), under `apps/api/spikes/s1/`. Every number below comes from the run logs in `apps/api/spikes/s1/results/`. Nothing in the table is estimated.

## Setup

- **Machine:** native WSL2 (Linux 6.18.54.1-microsoft-standard-WSL2), 16 cores, 15 GiB RAM. No Docker.
- **Pinning:** every run used `taskset -c 0-5` (6 CPUs).
- **Software:** OR-Tools 9.15.6755, installed by `uv sync --frozen`. uv.lock was not changed.
- **Scenario:** `spikes/s1/gen.py`, generator seed `20261104`, CP-SAT `random_seed` 0. It has 100 locations: 4 hubs and 96 beneficiaries, in a 300 × 300-mile region. It has 500 products, each with its own unit, and handling coefficients of 1–3. That gives 50,000 forecast series and 68,987 lots, each with an expiry date or explicitly non-expiring. There are 1,000 routes: for each source, the k = 10 nearest beneficiaries within 150 miles (`HUB_AND_PANTRY`), with an ETA of 0, 1 or 2 days by distance. The planning window is 3 days and the horizon is 7 days.
- **Receivers:** about 86 receivers per product have a positive target (10% of targets are zero). These receivers form the RP group of each product.
- **Product classes, fixed by the seed:** AMPLE 60%, SHORT 25%, EXPIRY 15%.
- **Shared capacities (residual):** route 300; beneficiary source 1,500; hub source 20,000; receiving 400 per site per day; global handling 150,000. Storage is set non-binding (shortcut: it keeps the products decoupled).
- **Model code:** the existing pipeline is reused unchanged: `scenario.freeze_scenario`, `candidates.prepare_problem`, `constraints.build_physical_model`, `objective.attach` (via `classical_gp`/`egp_pi_inspired` semantics), `numerics.audit_model`, `service.solve_one`, `extract.read_candidate` and the verifier `verify.verify` (`services/optimization/verify.py`). `spikes/s1/scope.py` lifts only the v0 size caps: sites ≤ 14, products ≤ 8, routes ≤ 182, beneficiaries ≤ 12, hubs ≤ 2 and lots ≤ 256. All other `ORInputPackage` validation is the original source; `test_s1.py` shows that duplicate IDs are still rejected.
- **Pantry mode:** paired `CLASSICAL_GP` then `EGP_PI_INSPIRED` (AP/RP reified both ways; RP group means over each product's receivers), with the policy from `data/demo/or-v2/six-beneficiary-v2`.
- **Retail mode:** a throwaway objective, minimize `3 × expired + 2 × lost` over all 7 days, on the same physical region. The independent replay recomputes it from the verifier's projection. Retail still uses the stricter Pantry window rule (BD-51): a transfer must be consumed inside the window.
- **"At-risk" product:**
  - Pantry: the existing solver-free FEFO kernel (`kernel.project_kernel`), run with no transfers, projects unmet demand at some beneficiary inside the 3-day window.
  - Retail: the kernel projects unmet demand **or** expired units within 7 days.
  - Both definitions select the same 194 of 500 products (all SHORT and EXPIRY products). The screen runs in under 2 s.
- **Decomposition by product:** one scenario per product, solved through `solve_one` (1 CP-SAT worker each) in a 6-process pool. Coupled capacities (route, receiving, source, global) are partitioned by kernel need share and floored, so the per-product parts never exceed the network capacity. An independent sum over the union of all plans re-checks this (`coupling_check`).
- **Decomposed limits:** each solve has a 5 s search cap. The 330 s method deadline and the 690 s comparison deadline apply to the whole pool.
- **Monolithic `mono-merged` / `mono-atrisk`:** every product's physical model and objective are built into **one** CpModel, plus jointly coupled capacities. CP-SAT then runs with 6 workers and a 300 s cap.
- **Monolithic `mono-existing`:** one 100 × 500 `ORInputPackage` through the existing pipeline, unchanged.

## Commands

From `apps/api`, after `uv sync --frozen --directory apps/api`:

```
.venv/bin/python -m pytest -q -p no:cacheprovider spikes/s1/test_s1.py          # 4 passed
spikes/s1/run_all.sh "decomp pantry" "atrisk pantry" "decomp retail" "atrisk retail" \
  "mono-merged pantry" "mono-merged retail" "mono-existing pantry"
spikes/s1/run_all.sh "mono-atrisk pantry" "mono-atrisk retail"
```

`run_all.sh` runs each variant as follows:

```
/usr/bin/time -v -o results/<v>.time timeout --kill-after=10 700 taskset -c 0-5 \
  .venv/bin/python -m spikes.s1.run <variant> <mode> --search-seconds 5
```

**RSS columns:**
- "Max RSS" is the `/usr/bin/time -v` maximum resident set size, which is the largest single process.
- "Tree RSS" is the in-process peak of the sampled sum of VmRSS over the parent and the pool workers.

## Results (100 × 500)

| Variant | Mode / method | Wall s (method) | Native status | Verifier (`verify.verify`) | Max RSS MB | Tree RSS MB | Objective |
|---|---|---|---|---|---|---|---|
| (a) mono-existing | Pantry | killed at 700 (exit 124) | none: never reached CP-SAT | not run | 6,502 | n/a | none |
| (a) mono-merged | Pantry CLASSICAL_GP | 332.2, budget exhausted | none: build reached 172/500 products | not run | 4,203 | 3,723 | none |
| (a) mono-merged | Pantry EGP_PI_INSPIRED | 330.4, budget exhausted | none: build reached 154/500 | not run | (same run) | (same run) | none |
| (a) mono-merged | Retail | 330.4, budget exhausted | none: build reached 167/500 | not run | 3,489 | 3,009 | none |
| (c) mono-atrisk | Pantry CLASSICAL_GP | 333.5, budget exhausted | none: build reached 156/194 | not run | 3,962 | 3,482 | none |
| (c) mono-atrisk | Pantry EGP_PI_INSPIRED | 336.0, budget exhausted | none: build reached 116/194 | not run | (same run) | (same run) | none |
| (c) mono-atrisk | Retail | 330.7, budget exhausted | none: build reached 136/194 | not run | 3,232 | 2,753 | none |
| (b) decomp | Pantry CLASSICAL_GP | 253.7 | 483 OPTIMAL, 17 FEASIBLE | 500/500 pass; objective replay 500/500; coupling 0 violations | 761 | 4,939 | Σ 568.343672 (71042959/125000) |
| (b) decomp | Pantry EGP_PI_INSPIRED | 298.6 | 435 OPTIMAL, 65 FEASIBLE | 500/500 pass; replay 500/500; coupling 0 | (same run) | (same run) | Σ 949.509220 |
| (b) decomp | Pantry comparison | 554.4 total (budget 690) | as above | as above | | | |
| (b) decomp | Retail | 251.7 | 500 OPTIMAL | 500/500 pass; replay 500/500; coupling 0 | 749 | 4,876 | Σ 487,262 |
| (c) atrisk (decomposed) | Pantry CLASSICAL_GP | 147.3 | 175 OPTIMAL, 19 FEASIBLE | 194/194 pass; replay 194/194; coupling 0 | 764 | 4,931 | Σ 568.343672 |
| (c) atrisk (decomposed) | Pantry EGP_PI_INSPIRED | 167.4 | 128 OPTIMAL, 66 FEASIBLE | 194/194 pass; replay 194/194; coupling 0 | (same run) | (same run) | Σ 955.876328 |
| (c) atrisk (decomposed) | Pantry comparison | 316.7 total (budget 690) | as above | as above | | | |
| (c) atrisk (decomposed) | Retail | 96.1 | 194 OPTIMAL | 194/194 pass; replay 194/194; coupling 0 | 749 | 4,880 | Σ 487,262 |

No run exceeded 8 GiB. The largest was mono-existing at 6.5 GB when it was killed.

## Observations

1. **Monolithic never reaches CP-SAT inside 330 s.** This holds in both modes, even with at-risk products only.
   - mono-existing: `freeze_scenario` took 101 s. `prepare_problem` was still running when the run was killed at 700 s. Its candidate × lot scan (`candidates.py:58-72`) is the bottleneck.
   - mono-merged: the serial Python build costs about 2–3 s per product. At 150 products the model already had 882,464 variables (EGP log).
   - The CP-SAT solve time and memory of a full 100 × 500 single model are **not measured**.
2. **Decomposition by product fits both modes, verified.** Pantry EGP used 298.6 of 330 s, a margin of 31 s on an otherwise idle machine. 65/500 EGP solves ended FEASIBLE at the 5 s per-product cap. Their per-product gaps were not recorded.
3. **At-risk only shrinks the job.** It solves 194/500 products and gives the same classical and Retail objective sums as the full decomposed runs: the 306 AMPLE products contribute 0. It cuts Pantry to 316.7 s for the pair and Retail to 96.1 s.
4. **FEASIBLE results depend on wall-clock limits.** Both EGP runs solved the same 194 at-risk products, but the sums differ: 949.509 in the decomp run and 955.876 in the at-risk run. Replay must check validity and objectives, not identical vectors (as INVARIANTS already require).
5. **The decomposed objective is not the monolithic objective.** Each product has its own Z (Chebyshev) term and its own AP/RP excess normalization, and coupled capacities are partitioned by a heuristic. This is a contract change the lead must decide, not only a performance setting.
6. **The decomposed tree RSS (~4.9 GB) is mostly duplication.** Each of the 6 workers holds the whole generated package, about 0.75 GB each. That is spike-driver overhead, not the solver.

## Recommendation (V1-D15 order)

1. **At-risk only: adopt it, but only together with decomposition by product.** That configuration produced verified results in both modes, with every native status preserved, well inside 330 / 690 s and below 8 GiB. Full decomposition also fits, but the EGP margin is thin (31 s).
   - At-risk alone, inside one monolithic model, did not fit: the build alone exceeded 330 s.
   - If a real network has most products at risk, the measured worst case is the full decomposed row.
   - Required follow-ups:
     - freeze the per-product objective and the capacity-partition rule in the contract;
     - record per-product gaps;
     - load the scenario once per worker, or share it.
2. **Lower the envelope: not needed** for the decomposed configuration. For a monolithic single model no fitting envelope was measured. The builds that were measured reached only about 116–172 products × 100 locations before the 330 s method budget ran out.
3. **Raise ceilings: no evidence supports it.**

V1-D15 step reached: 1
