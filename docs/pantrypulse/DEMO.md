# PantryPulse demo runbook

> **Current authority:** [Project specification V5](SPEC-V5.md). Historical demonstration runbook. Use the V5 research-first narrative, expanded population, paired methods, proxy/job architecture and current implementation limits.

Audience: Gator Hack V judges. Target length: 2–3 minutes, adjusted to the actual event limit. The official event deadline, eligibility, judging rubric, AI/tool disclosure, sponsor requirements, video length and submission format are not present in the source spec; confirm them from the organizer before the event. All hour numbers in this kit are relative to the actual start time.

## Preconditions

- Release SHA, deployed web/API URLs and dataset version recorded.
- Demo organization explicitly simulated; no personal or real operational data.
- Presenter reset protected and verified, or private seed reset ready.
- Fixed demo date/timezone, 90-day dataset, forecast run and scenario configured.
- Three sites and two categories; one projected shortage, one donor surplus, one reserve edge, capacity constrained.
- Model/fallback/cache labels reflect what actually ran. Baseline comparison is computed on the same inputs.
- Browser zoom/resolution, readable font sizes and no development overlays; backup recording available.

## Judge sequence

| Time | Action | What to communicate |
|---|---|---|
| 0:00–0:20 | Open seeded overview | Three pantries can look stocked today while demand creates a future shortage |
| 0:20–0:45 | Select category/site, reveal forecast | First projected deficit, seven-day horizon, actual model and uncertainty method |
| 0:45–1:15 | Generate/inspect transfer plan | Origin/destination/quantity, reserve and capacity constraints, solver status |
| 1:15–1:35 | Compare same-horizon unmet demand | Read actual baseline and after values, with category/unit and simulated label |
| 1:35–2:00 | Apply demand surge or supply reduction; Recalculate | The changed assumptions produce a new feasible plan/result while baseline stays intact |
| 2:00–2:30 | Open explanation/evidence | Forecasting predicts need; deterministic projection finds risk; optimization chooses feasible actions |
| 2:30–3:00 | Optional fallback/closing proof | Honest limitations, baseline fallback and reproducibility; finish with the operational value |

Suggested narrative: “PantryPulse helps a coordinator see a projected shortage early and evaluate feasible transfers. These results are from a simulated network. We can change assumptions, replan, and see which need remains unresolved.” Substitute actual site/date/quantity from the live seed. The research's 190→65 and 125-meal examples are illustrative, not validated app outcomes.

## Golden arithmetic rehearsal

For the two-day meals fixture only: North has 40 and needs 50 then 40. Central has 200, needs 30 then 30 and protects 40 at window end. South has 70, needs 30 then 30 and protects 10. Total handling budget is 40. Central sends North 40; unmet falls 50→10. With a North multiplier 1.25 and integer ceiling, need is 63 then 50 and unmet is 73→33. This fixture demonstrates the arithmetic; the seven-day live seed can contain different numbers. Do not hard-code these values into live UI cards.

## Five-run reliability checklist

For each run record reset result/dataset hash, start timestamp, model/run ID, baseline unmet, plan status, after unmet, changed scenario result, duration and observed issues. Exercise one cold start and one provider failure across the rehearsals. Each run starts with reset and ends with the full scenario change. A pass requires correct state change, honest labels, no stale-response overwrite and no hidden intervention outside the documented presenter workflow.

When live inference fails: show labeled baseline or the prepared cached run with timestamp; do not pretend it was recomputed. When backend fails: use the local release or clearly identified backup recording. When solver cannot resolve a case: show remaining shortage/status and limiting constraints, not a fake successful transfer.

## Submission assets

README includes problem, architecture, setup, command/env names without secrets, data/proxy/simulation provenance, forecasting limits, optimization scope, test commands, deployed URL and demo reset instructions. Include architecture diagram, primary screenshots, backup video, team attribution and license/source acknowledgements. Record third-party tools/AI usage as event rules require. Leave time to upload and verify playback. Only submit/publish to the event after the user's authorization and rules check.
