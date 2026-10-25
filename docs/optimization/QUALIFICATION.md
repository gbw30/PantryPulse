# OR computational qualification — October 25, 2026

This completes the remaining local qualification work under execution revision 1.2.
All **24 pairs / 48 method outcomes** returned VERIFIED and passed independent
parent replay and comparison assembly: five scale cases and nineteen policy cases.
There were 42 native OPTIMAL and six native FEASIBLE outcomes. All inputs are
SIMULATED. Defaults remain provisional and unchanged.

[Machine evidence](evidence/qualification-final.json) records exact input/policy/
settings and code hashes, dimensions, model sizes, objective components, goal vectors,
native statuses/bounds/gaps, timings and cumulative child RSS. The larger report is
retained locally at `artifacts/or-finalization/qualification-full.json`; its digest
is in the source evidence. No database, API, frontend or shared worker participates.

## Reproduce

From the repository root, using the already installed locked API environment:

```bash
apps/api/.venv/bin/python scripts/or/qualify.py \
  --output artifacts/or-finalization/qualification-full.json
apps/api/.venv/bin/python scripts/or/qualification_summary.py \
  --input artifacts/or-finalization/qualification-full.json \
  --output docs/optimization/evidence/qualification-final.json
```

`--suite scale` and `--suite sensitivity` select smaller runs. Qualification exits
nonzero if a pair lacks a verified result or a literal/limiting expectation fails.
It does not promote a provisional policy. New runs may select different tied vectors
or find different incumbents at a wall-time limit; retain the actual new evidence.

Environment: Python 3.12.13, OR-Tools 9.15.6755, Linux x86_64/glibc 2.39. Settings:
one native worker, seed 0, 15,000 ms search cap. The offline runner uses its existing
25-second method-child / 60-second pair boundaries. Profile/build audit is measured
separately; pair wall time includes final assembly and its physical rebuild/replay.
The source digest covers all OR modules, OR Python schemas and qualification driver.

## Scale and numeric cases

Each upper case simultaneously has **12 beneficiaries, 2 hubs, 2 products, 182
non-self routes, 228 original lots plus 28 confirmed arrivals, seven forecast dates
and H=3**. Routes include ETAs 0/1/2; early expiry restricts hub lot eligibility;
four beneficiary donors have protected own demand. Receiving/storage/source/global
handling capacities are explicit, with shared product handling coefficients 2/1.
The numeric variant reaches 100,000 units per lot and per planning goal and route
prices of 1,000,000 minor units. Future confirmed receipts arrive outside H and
cannot fund dispatch. This is generated supplied data, not a committed source read.

| Case | Pair wall incl. assembly (s) | Classical / research status | Classical / research gap | Variables classical / research |
|---|---:|---|---|---:|
| six-default | 3.281 | OPTIMAL / OPTIMAL | 0.0000% / 0.0000% | 216 / 244 |
| upper-size-HUB_ONLY | 38.443 | FEASIBLE / FEASIBLE | 44.1786% / 64.0022% | 8548 / 8600 |
| upper-size-HUB_AND_PANTRY | 42.554 | FEASIBLE / FEASIBLE | 99.9978% / 99.9986% | 20084 / 20136 |
| upper-numeric-HUB_ONLY | 23.738 | OPTIMAL / FEASIBLE | 0.0000% / 0.0014% | 6436 / 6488 |
| upper-numeric-HUB_AND_PANTRY | 30.215 | OPTIMAL / FEASIBLE | 0.0000% / 8.3478% | 17780 / 17832 |

Native search stayed at or below about 15.03 seconds; observed method totals include
build/audit/checking and remained below 19 seconds. The maximum audited activity
was **228,000,000,000,000,000**, strictly below **2^60 = 1,152,921,504,606,846,976**.
The maximum individual-child RSS observed since this qualification process began
was about 228 MiB. This is a cumulative Linux child high-water measurement, not
per-case attribution, aggregate tree memory, parent profile memory or a kernel quota.

**Solution quality remains a limitation at the size ceiling.** Both size cases
reach FEASIBLE; the pantry case has gaps near 100%, so this run establishes valid
bounded computation, not a useful near-optimal plan for every dense instance.
The numerical research cases also remain FEASIBLE, including one with a small
nonzero gap that must not be relabeled OPTIMAL. Hardware, expiry structure, route
ordering and search history matter; this is not a production latency/quality SLA.

The initial dense pantry qualification timed out for both methods; removing
fixed-zero route bookkeeping alone still left the research method UNKNOWN. The
final reduction also omits necessarily-zero post-H inbound trajectories and reuses
no-inbound donor projections when identical. HUB_ONLY physical variables fell from
21,020 to 8,548. These algebraic reductions preserve route vectors, deterministic
service and both methods' common physical feasible set; their proof and native
regressions are in [NUMERICAL-PROOF.md](NUMERICAL-PROOF.md). No search limit,
objective priority or policy coefficient was relaxed to obtain a passing result.

## Policy sensitivity

The nineteen cases cover lambda 0/50; beta 0/100; AP/RP thresholds 0/20000; caps
0/10000; penalties 1000; diagnostic zero vulnerability/penalties; cost/waste weights
10000; a single-attribute endpoint; three opposed-attribute mixes; and full/disabled
AP and RP fixtures. Every changed policy is explicitly ABLATION with its own version
and hash; full fixture controls retain PRIMARY. All thirty-eight native outcomes
in this sweep are OPTIMAL, with independent exact metric replay.

Observed in the simulated six-beneficiary fixture, for each product:

| Configuration | Research fulfilled vector in ascending site order |
|---|---|
| Default | (2,2,1,1,0,0) |
| Lambda 0 / diagnostic no research terms | (1,1,1,1,1,1) |
| Opposed attributes, equal coefficients | (1,1,1,1,1,1) |
| Opposed attributes, need only | (2,2,1,1,0,0) |
| Opposed attributes, access only | (0,0,1,1,2,2) |

The original two columns coincide, so its need-only case is intentionally unchanged.
A separately fingerprinted synthetic source reverses the access column to test a
meaningful coefficient response. These are simulated trade-offs, not evidence of
real-world benefit or a reason to adopt a new default. Endpoint beta runs can have
tied optima; their observed vectors are not asserted as unique universal choices.

Independent literal checks retain AP full `(1,0), 19/8` versus no-AP `(0,1), 2`,
and RP full `(0,1), 11/4` versus no-RP `(1,0), 21/8`. The zero-research limit matches
the classical objective `163/50`; maximum thresholds flag nobody and full caps
produce zero excess. Exact strict-boundary equality/+1 and complete tiny-vector
feasibility are checked separately in the retained native test suite.

## Interpretation limits

This qualifies these generated inputs and selected policy grids only. Structural
ceilings do not guarantee that all policy/quantity combinations pass conservative
integer activities or reach a useful incumbent within the timer. The auditor rejects
unsupported numerical ranges before search. Fixed loading order restricts schedules;
the solver is not a complete multi-period/endogenous-weight reproduction of the
paper. Domain policy approval, broader real-data qualification and API/storage/
shared-runtime integration remain external work. No social outcome or LIVE readiness
is claimed. [FINALIZATION.md](FINALIZATION.md) records the tested commit milestone.
