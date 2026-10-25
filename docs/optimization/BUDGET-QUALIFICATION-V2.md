# OR-v2 dense budget sweep

Measured October 25, 2026 on Linux (Docker Desktop), Python 3.12.13, OR-Tools 9.15.6755. Each child used one solver worker and seed 0; the container had 6 CPUs / 8 GiB. Other verification activity shared the host, so these are recorded observations rather than universal latency guarantees.

Both modes freeze the same dense generated network for all five budgets: 12 beneficiaries, two hubs, two products, 256 inventory/arrival rows. Exact scenario dimensions and all source/settings identities are in the [complete machine evidence](evidence/budget-sweep-v2.json). Each row contains the full native result, independent report, objective, bound, runtime and fresh-child peak RSS.

All 20 results are **FEASIBLE / VERIFIED**, none OPTIMAL. A separate parent replay of all ten pairs passed. No policy defaults were changed. v1 historical outcomes use different expiry semantics and are not a budget baseline for this table.

| Mode | Method | Search cap (s) | Objective | Best bound | Gap (%) | Child wall (s) | Peak RSS (MiB) |
|---|---|---:|---:|---:|---:|---:|---:|
| HUB_ONLY | CLASSICAL_GP | 15 | 4.116805 | 4.018896 | 2.3783 | 16.49 | 175.4 |
| HUB_ONLY | EGP_PI_INSPIRED | 15 | 5.601335 | 5.413675 | 3.3503 | 16.32 | 173.4 |
| HUB_ONLY | CLASSICAL_GP | 30 | 4.060386 | 4.026682 | 0.8301 | 31.28 | 178.4 |
| HUB_ONLY | EGP_PI_INSPIRED | 30 | 5.561894 | 5.418119 | 2.5850 | 31.27 | 173.6 |
| HUB_ONLY | CLASSICAL_GP | 60 | 4.060360 | 4.037835 | 0.5548 | 61.64 | 178.0 |
| HUB_ONLY | EGP_PI_INSPIRED | 60 | 5.561894 | 5.418119 | 2.5850 | 62.33 | 173.4 |
| HUB_ONLY | CLASSICAL_GP | 120 | 4.060281 | 4.050342 | 0.2448 | 122.77 | 177.7 |
| HUB_ONLY | EGP_PI_INSPIRED | 120 | 5.525423 | 5.418193 | 1.9407 | 122.11 | 181.3 |
| HUB_ONLY | CLASSICAL_GP | 300 | 4.060281 | 4.050362 | 0.2443 | 302.51 | 178.9 |
| HUB_ONLY | EGP_PI_INSPIRED | 300 | 5.482668 | 5.418193 | 1.1760 | 302.06 | 197.8 |
| HUB_AND_PANTRY | CLASSICAL_GP | 15 | 3.557121 | 0.000453 | 99.9873 | 18.68 | 234.7 |
| HUB_AND_PANTRY | EGP_PI_INSPIRED | 15 | 11.126830 | 0.000069 | 99.9994 | 17.67 | 238.2 |
| HUB_AND_PANTRY | CLASSICAL_GP | 30 | 2.612993 | 1.776489 | 32.0132 | 32.83 | 243.3 |
| HUB_AND_PANTRY | EGP_PI_INSPIRED | 30 | 11.126830 | 3.072337 | 72.3880 | 31.82 | 238.9 |
| HUB_AND_PANTRY | CLASSICAL_GP | 60 | 2.279242 | 2.250981 | 1.2399 | 61.98 | 246.0 |
| HUB_AND_PANTRY | EGP_PI_INSPIRED | 60 | 3.562632 | 3.072519 | 13.7570 | 61.83 | 244.2 |
| HUB_AND_PANTRY | CLASSICAL_GP | 120 | 2.279146 | 2.250981 | 1.2358 | 121.71 | 247.4 |
| HUB_AND_PANTRY | EGP_PI_INSPIRED | 120 | 3.217543 | 3.072519 | 4.5073 | 122.55 | 242.5 |
| HUB_AND_PANTRY | CLASSICAL_GP | 300 | 2.278944 | 2.250999 | 1.2262 | 302.01 | 253.0 |
| HUB_AND_PANTRY | EGP_PI_INSPIRED | 300 | 3.191617 | 3.073190 | 3.7106 | 301.78 | 248.0 |

Longer search substantially reduced the recorded dense pantry gaps, but the classical method changed little after 60 seconds and the research method still had a 3.71% gap at 300 seconds. Native objectives have different definitions and must not be ranked across methods. Peak RSS is per child, not an aggregate container-memory measurement.

The evidence records the exact source bytes used during measurement. Subsequent review tightened only the offline orchestration deadline checks; this sweep calls `solve_one` directly, and its solver/model/verifier files remained unchanged. The frozen output passed replay against the final tree.

Reproduce the sweep and independently replay its saved vectors:

```sh
apps/api/.venv/bin/python scripts/or/benchmark_budgets.py --output evidence.json
apps/api/.venv/bin/python scripts/or/verify_budget_evidence.py evidence.json
```

Machine-evidence SHA-256: `5f64914cff53ae099d0ad41e49643fe68d57de4ab9f35b6c9cde4a56a608acfa`.
