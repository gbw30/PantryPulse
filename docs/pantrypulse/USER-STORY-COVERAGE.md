# User-story coverage: origin/main e1c6663 (2026-10-25)

This is a read-only analysis by an independent subagent. Verdicts come from the code on main, not from planning docs.

- **CI evidence:** run 40212214710 passed on e1c6663: backend 1213 passed with 0 skipped, and browser 63 passed with connected tests run (`PP_RUN_CONNECTED=1`). The specs that mock the API are not counted as end-to-end proof.
- **What exists:** only `/overview` (live for presenters, labelled fixture otherwise) and `/optimization` (presenter-only workspace) have real UI. Data Explorer, Recommendations, Scenario Lab, Methodology and Site Detail do not exist yet.
- **Out of date:** the read-only visitor scope and local launcher on `pp/visitor-read-launcher` (1ecaa9e) were added after this analysis. They change the visitor rows below once merged.

## SOURCE-SPEC US-01–US-12

| ID | Persona | Story | Status | Gap |
|---|---|---|---|---|
| US-01 | Coordinator | Inventory and shortage status per site | Enabled end-to-end (presenter) | Site Detail disabled; visitors see the fixture |
| US-02 | Site manager | Adjust stock with a reason | API only | No UI (`inventory.py:29-40`) |
| US-03 | Analyst | Upload historical demand CSV | API only | No upload UI; imports are all-or-nothing |
| US-04 | Coordinator | 7-day expected demand | Enabled end-to-end (presenter) | No model version; baseline only |
| US-05 | Site manager | Know when my site may run out | Enabled end-to-end (presenter) | Physical stock only; arrivals excluded |
| US-06 | Coordinator | Range of outcomes | Partially enabled | UI hard-codes CENTRAL (`workspace.tsx:146`) |
| US-07 | Coordinator | Suggested transfers | Enabled end-to-end (presenter) | — |
| US-08 | Coordinator | Why each transfer | Partially enabled | No shortage addressed / both-site effect |
| US-09 | Coordinator | Change assumptions and replan | Partially enabled | Multiplier + raw JSON; no side-by-side |
| US-10 | Coordinator | Resources can't cover need | Partially enabled | Termination reason, violations and warnings not shown |
| US-11 | Judge | Reset to a prepared scenario | Partially enabled | No reset API or UI |
| US-12 | Analyst | Models and data behind a result | Partially enabled | No Methodology page; `/allocation-methodology` unused |

## V4 research stories (US-15–US-18)

| ID | Persona | Story | Status | Gap |
|---|---|---|---|---|
| US-15 | Coordinator | Compare CLASSICAL_GP vs EGP_PI_INSPIRED | Partially enabled | Decision differences not highlighted |
| US-16 | Analyst | Inspect vulnerability sources and weights | Partially enabled | Raw JSON only |
| US-17 | Coordinator | Tune AP/RP thresholds and weight | Partially enabled | JSON editing only; AP/RP values not shown |
| US-18 | Judge | Trigger a research change | Partially enabled | Presenter only; no highlighted change |

The blueprint's Recommendations story (inspect corrective options and record a simulated review) is not enabled in the UI. The review route exists only in the API (`planning.py:205`).

## Persona rollup

- **Coordinator (presenter):** sees live risk on the Atlas. In `/optimization` they can generate a forecast, freeze a scenario, compare both methods, and revise or retry. They can't see AP/RP values or decision differences, and can't mark a plan reviewed.
- **Site manager:** sees eligible stock, the expiring-lot count and the next deficit in the inspector. Lots, receipts and adjustments are API only.
- **Analyst:** reads provenance hashes and edits policy JSON. CSV import is API only, and there's no methodology or audit page.
- **Presenter:** signs in on `/optimization`. Imports, stock commands and review exist only in the API, and there's no reset.
- **Visitor / judge:** sees the labelled fixture only. The visitor scope on `pp/visitor-read-launcher` fixes this.
- **Beneficiary institution:** its target, served and unmet values appear; its vulnerability and AP/RP values don't.

## Top demo gaps (90-second narrative, blueprint §16)

1. **Per-institution method difference with AP/RP.** Add a goal diff table and an assignment diff in the `/optimization` results, and show `common_differences`.
2. **Recommendations with "Mark reviewed — simulation".** Add a review button that POSTs to `plans/{id}/review` (already allowed by the proxy), or a `/recommendations` page.
3. **Data Explorer forecast chart and Site Performance table.** A `/data` page reusing `overviewApi.summary` and `overviewApi.shortages`. The history segment needs a history read API.
4. **Methodology page.** Render `GET /allocation-methodology`, the DOI and the adaptation limits.
5. **Overview → saved comparison deep link and Site Detail.** Add a `comparison=<id>` parameter in `/optimization`.

## Conflicts between sources

- US-01–US-12 and the V4 US01–US13 lists reuse numbers for different stories.
- Three sites (SOURCE-SPEC, PROJECT-CONTRACT, DEMO) vs six beneficiaries plus hubs (V5, followed by the code).
- Per-transfer benefit (FR-11, US-08) vs OPEN-02.
- "Approve" (SOURCE-SPEC) vs simulation-only review (V5).
- Judge mutates (US-11, US-18) vs read-only visitor (blueprint, V5).
- Accept-valid-rows import (D07) vs all-or-nothing import (V5 and the code).
- Uncertainty as p50/p90 vs point baseline plus buffers (V5).
- No-transfer/equal-share/greedy baselines vs classical-vs-research (OPEN-34).
- Supplier stories are P0 in V4 but paused in V5.
- 2–3 minute demo (DEMO.md) vs 90 seconds (V5).
- SPEC-V5 §12.1 still lists routes on main as "PP-50 candidate".
