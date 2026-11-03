# PantryPulse demo — 2 minutes

Updated October 25, 2026. Current setup: **Vercel website → Cloudflare Tunnel → laptop API/worker → local PostgreSQL**. All data and recommendations are simulated.

Open [PantryPulse](https://pantrypulse-prototype-preview.vercel.app/overview) and sign in from the sidebar as `presenter` with your existing password. Keep Docker, the laptop and the tunnel running. For startup, use the [launch guide](../setup/LOCAL-LAUNCH-GUIDE.md).

## Present

| Time | Action | Say |
| --- | --- | --- |
| 0:00–0:25 | **Overview**: select a product and inspect a pantry's shortage. Confirm the live simulated-data label. | “PantryPulse helps a coordinator anticipate shortages across a food-sharing network.” |
| 0:25–1:05 | **Scenario Lab**: open Normal Week below. Compare classical goal programming with EGP-PI-inspired allocation, institution-level allocations and unmet need. | “Both methods use the same frozen supplies, needs and constraints. Changing priorities can change who receives food.” |
| 1:05–1:35 | Open Demand Surge, then Vulnerability Trade-off. | “More demand leaves more need unresolved. Vulnerability priorities change allocations even when total unmet need is unchanged.” |
| 1:35–2:00 | **Recommendations**: select the same comparison; inspect transfers, quantities and verification. | “A coordinator can review a feasible plan and its trade-offs before acting. This simulation dispatches no stock.” |

## Prepared comparisons

These October 25 results were computed and saved in advance. Open them after signing in; no import or recalculation is needed.

| Scene | Scenario Lab | Unmet need before → after, for either method |
| --- | --- | --- |
| Normal Week | [Open](https://pantrypulse-prototype-preview.vercel.app/scenarios?comparison=7015f6c2-1202-4c04-9431-19cd619e2657) | Water: 160 → 40 bottles; meals: 100 → 0 |
| Demand Surge +30% | [Open](https://pantrypulse-prototype-preview.vercel.app/scenarios?comparison=fbccf57c-1158-4d73-9934-ba1b011ddd2d) | Water: 220 → 100 bottles; meals: 145 → 25 |
| Vulnerability Trade-off | [Open](https://pantrypulse-prototype-preview.vercel.app/scenarios?comparison=20f04ba5-d226-4f19-9b57-e5c7c2329938) | Water: 226 → 106 bottles; meals: 166 → 46 |

Both methods have the same totals in these scenes but different allocations. Read the displayed provider, date and verification; describe older records as historical.

## Optional live calculation

In **Scenario Lab**, choose a source and forecasting strategy, then **Generate forecast**. Once planning-ready, select the forecast and assumptions, choose transfer mode and disruptions, **Create frozen scenario**, then **Compare methods**. Allow several minutes; use saved results during the short pitch.

Chronos-2 is enabled experimentally. The latest recorded live test requested Chronos but published **MOVING_AVERAGE**, with `fallback_used=true`, after strict validation rejected negative donation quantiles. Present it as a moving-average fallback. Keep strict validation and visible fallback labels; describe each new run using its actual provider.

Before recording, check presenter login, saved comparisons and the live source label. Keep a backup recording available.
