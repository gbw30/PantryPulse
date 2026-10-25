# PantryPulse — Frontend Design Blueprint

**Document:** `PantryPulse_Frontend_Design_Blueprint.md`  
**Updated:** 2026-10-25  
**Status:** **Finalized frontend design revision 1.3** — October 25, 2026 decisions select the Collage 2 sidebar and Recommendations page, a numbered Scenario Lab wizard and results/comparison panels, and a single consistent top navigation without a duplicated profile icon. Overview and Data Explorer selections from v1.1 remain in force. **This is a UI design companion, not a replacement for the authoritative V5 product specification.**  
**Source of truth:** [`docs/pantrypulse/SPEC-V5.md`](https://github.com/gbw30/PantryPulse/blob/main/docs/pantrypulse/SPEC-V5.md). Also follow [ADR 0002 — UI stack](https://github.com/gbw30/PantryPulse/blob/main/docs/architecture/0002-ui-stack.md), [ADR 0004 — isolated 3D exception](https://github.com/gbw30/PantryPulse/blob/main/docs/architecture/0004-design-lab-3d-exception.md), and the compatible [`ART-DIRECTION.md`](https://github.com/gbw30/PantryPulse/blob/main/docs/pantrypulse/ART-DIRECTION.md).  
**Project:** Gator Hack V, October 23–25, 2026. Operational data and example results are simulated.  
**Important:** Design decisions made here do not adopt unapproved model weights, supplier policies, runtime contracts, or real fulfillment permissions. Implementation status must be checked against the repository at development time.

---

## 1. Executive design direction

**Product experience:** A calm, premium **food-distribution operations desk** with a visually explorable network, serious analytics, explainable recommendations, and a dedicated research-comparison lab. The interface must answer, in order:

1. **Where is the network at risk?** — Overview / map-centric Network Atlas (Collage 1 inspiration).
2. **What evidence predicts that risk?** — Data Explorer / Collage 2 layout with Network Demand Forecast, four KPI cards, in-place flip panels, Site Performance, Seven-Day Pulse and Operations Board.
3. **What feasible corrective actions are available?** — Recommendations / **Collage 2 Action Plan + recommendation queue + impact inspector** (selected; simulation only).
4. **How do allocation choices and fairness priorities change outcomes?** — Scenario Lab / **numbered guided builder (Collage 1) + results/comparison/trade-offs and fill-rate-by-site panels (Collage 2)**.

### Agreed decisions from the design discussion

| Area | Selected direction | Decision status |
| --- | --- | --- |
| Overview | **Network Atlas inspired by Collage 1**: large cartographic-style map canvas with interactive site markers, route overlays, compact legend, map controls and selected-site popover; future Google Maps-ready | **Updated/selected 2026-10-25** |
| Data Explorer | **Collage 2 dashboard composition**: four fixed-position KPI cards; Network Demand Forecast line chart; one in-place flip card for Fill Rate by Region ↔ Item Risk Overview; Site Performance table. Seven-Day Pulse and Operations Board remain accessible within explorer subviews. | **Updated/selected 2026-10-25** |
| Recommendations | **Collage 2 layout selected**: persistent left sidebar, page tabs, reviewable action-plan list/table and contextual Impact Preview; **Resource River/Sankey is not the primary view** | **Selected 2026-10-25; exact fine-grained styling provisional** |
| Scenario Lab | **Collage 1 numbered, guided setup + Collage 2 results composition**: decision controls, Scenario Results, Projected Fill Rate by Site, Comparison and Key Trade-offs; full V5 method, policy and constraint evidence | **Selected 2026-10-25; inputs gated by V5** |
| Aesthetic | Neutral, manager-oriented, off-white/chalk surfaces, slate/navy typography, muted teal action and sparse semantic risk accents | **Selected direction; exact tokens proposed** |
| Primary overview rule | The map is the hero; **no data-dense tables, sprawling KPI grids, or complex allocation knobs on Overview**. The four selected summary KPIs belong to **Data Explorer**, not a competing Overview dashboard. | **Reaffirmed** |
| Navigation | **Exact Collage 2 navigation-shell composition across all four tabs**: persistent left sidebar with logo, four page links and bottom account identity; top bar has search, seven-day period selector and compact utility icons **without a top-bar profile icon**. Do not duplicate the account identity in top and side navigation. | **Finalized 2026-10-25** |
| Scenario Lab results | **Collage 2** Scenario Results compact cards + Projected Fill Rate by Site + Comparison chart + Key Trade-offs; display only verified model outputs with declared metrics | **Selected 2026-10-25** |
| Production graphics | **Geographic-ready 2D map presentation**, initially SVG/HTML + Motion. Add real basemap tiles/Google Maps only through a separately approved adapter with grounded coordinates and provider terms. No production WebGL/Three.js approval. | **Aligned with V5/ADR; Google Maps future option only** |
| 3D exploration | Three.js only in optional `/design-lab`, with accessible 2D fallback and lazy loading | **Existing approved prototype-only exception; unchanged** |
| Data Explorer summary KPI 1 | **Households Served** design and label from Collage 1 | **Selected; needs independently sourced household-count data** |
| Data Explorer summary KPI 2 | **Predicted Fill Rate** card from Collage 2 | **Selected; definition/unit filter required** |
| Data Explorer summary KPI 3 | **Risk flip card: Items at Risk ↔ Sites at Risk** | **Selected; in-place 3D-like card flip with fixed geometry** |
| Data Explorer summary KPI 4 | **Food Waste Rate** | **Selected; source/denominator must be explicit** |
| Data Explorer analytic flip panel | **Fill Rate by Region ↔ Item Risk Overview** in the same card slot | **Selected; must not reflow surrounding grid** |
| Data Explorer persistent sections | **Network Demand Forecast line graph** and **Site Performance table**, both based on Collage 2 | **Selected** |

### Core non-goals

- Do not build a generic BI dashboard as the landing page.
- Do not pass illustrative map artwork or fictional marker positions off as verified geography. The Overview is *cartographic in appearance*; real basemaps, place names, directions, geographic locations, distances and ETAs require grounded data and separately reviewed integration.
- Do not imply plan simulation has reserved inventory, approved purchases, completed shipments, or executed financial transactions.
- Do not use autonomous actions, live purchases, uncontrolled allocation changes, or an LLM as the source of inventory/forecast/optimization truth.
- Do not insert unnecessary carousels, decorative particles, constant motion, overlapping glass panels, or competing animation systems.
- Do not describe optional research models or suppliers as implemented when V5 says they are incomplete, paused, or unverified.

## 2. Personas and task-oriented information architecture

| Persona | Primary question | Primary entry point | System behavior |
| --- | --- | --- | --- |
| Network coordinator | Which sites need support, and what should we do? | Overview → Recommendations → Scenario Lab | Observe risk, explore eligible options, review a simulated plan |
| Site manager | What is actually usable at my site, and when will I run short? | Data Explorer → Site detail | Inspect lots, local demand, reserves and versioned adjustments |
| Analyst | What inputs, models and equity terms produced this result? | Data Explorer → Scenario Lab → Methodology/Audit | Compare data, provider provenance, AP/RP metrics and solver evidence |
| Presenter (demo authorization) | Can I run a reproducible end-to-end demonstration? | Any page; protected edit controls | Submit changes/scenarios/jobs, mark plans reviewed (simulation), reset isolated demo only |
| Read-only visitor / judge | Can I understand the decisions without changing the system? | Overview → saved results | Inspect synthetic data and previously saved results; no mutation or reset |
| Beneficiary institution | Will our community's unmet demand be visible and considered? | Represented in coordinator results | Per institution/product projected target, served units and residual shortfall |

**Site roles are product personas, not separate implemented authentication/authorization roles for P0.** One authenticated presenter can perform demo mutations; read-only visitors cannot. Volunteers and production procurement staff are future/supporting personas.

### Navigation model

```text
GLOBAL SHELL
├── Overview                /overview            Cartographic-style Network Atlas; site popovers; no dense analytics
├── Data Explorer           /data                KPI row + Network Demand Forecast + flip panel + Site Performance
│   ├── Forecasts           /data/forecasts      Seven-Day Pulse, demand/donation trends and provenance
│   ├── Operations Board    /data/operations     Six-site cards and risk overview (proposed route)
│   ├── Inventory           /data/inventory      Lots, expiry, eligible stock, corrections
│   └── Site detail         /data/sites/[id]    Inbound/outbound + dated service + audit
├── Recommendations        /recommendations     Collage 2 Action Plan / action queue / Impact Preview
├── Scenario Lab           /scenarios           Numbered scenario wizard + Decision Studio outcomes
│   └── Scenario detail     /scenarios/[id]      Immutable replay & method outcomes
└── Methodology & Audit    /methodology         Formulas, source, versions, events
```

Routes are **proposed frontend route names**, not declared API endpoints or existing pages. `/design-lab` stays separate from the production navigation as an optional prototype route.

### Persistent global shell

- **Desktop left sidebar follows Collage 2 exactly**: PantryPulse mark/name at top; labeled icon links in this order: `Overview`, `Data Explorer`, `Recommendations`, `Scenario Lab`; restrained teal-highlighted active row; `Settings` near the lower-left area, and **the sole account/avatar identity in the lower sidebar footer** (only if there is a supported authenticated session). Preserve its geometry and chrome across all four main tabs. Keep `Methodology & Audit` reachable through a clearly labeled utility or secondary navigation link; do not hide essential provenance behind an icon alone. Collapse to an accessible drawer at narrow widths without introducing a redundant avatar.
- **Top navigation follows Collage 2 exactly**: a compact horizontal search field (`Search sites, regions, or products…`) toward the left, `Next 7 Days` or another truthful horizon label near the right, and the same compact utility icons from the chosen collage. **No user profile photo, avatar, account initials or extra user dropdown in the top navigation**. The top navigation must not differ among Overview, Data Explorer, Recommendations and Scenario Lab. Utility icons must have accessible labels and only display actionable controls when corresponding functionality exists; otherwise remove or clearly disable placeholders.
- **No duplicate identity rule**: when an authorized user/presenter identity is available, it appears **once**, in the bottom of the left sidebar as in the collage. Never mirror it in the top bar or title area. Read-only/demo visits must not display a fabricated authenticated profile.
- Global context strip, where supported by available data: **Simulated network**, selected resource/product with base unit, seven-day date horizon (local date/timezone), current snapshot/scenario identity, last computed/updated timestamp, access mode (presenter/visitor). Integrate these labels unobtrusively with the chosen Collage 2 shell rather than constructing a second competing toolbar.
- Preserve URL-addressable filters where useful: site, product, selected day, scenario ID; changing a filter **never recomputes or edits** the snapshot.
- Global alert area for genuine pending/failure/stale context only. Avoid toasts for ordinary successful filter changes.
- Consistent terminology: **projected deficit**, **eligible stock**, **transferable surplus**, **proposed transfer**, **unmet demand**, **simulated review**, **confirmed arrival**, **forecast method**, **research method**.
- Distinguish visual states for current-data overview, historical scenario snapshot, draft edits, successfully computed plan, partially available comparison, and stale recommendation.


#### Locked navigation-shell reference (final collage consistency decision)

```text
COLLAGE 2 SHELL — IDENTICAL ON EVERY MAIN PAGE
┌─────────────────┬─────────────────────────────────────────────────────────────┐
│ PantryPulse     │ [Search sites, regions, or products…]    [Next 7 Days] ◦ ◦  │
│                 ├─────────────────────────────────────────────────────────────┤
│ Overview        │ Page heading + page-specific, evidence-based content       │
│ Data Explorer   │                                                             │
│ Recommendations │                                                             │
│ Scenario Lab    │                                                             │
│                 │                                                             │
│                 │                                                             │
│ Settings        │                                                             │
│ [Avatar] User   │       ACCOUNT IDENTITY ONLY IN SIDEBAR FOOTER              │
└─────────────────┴─────────────────────────────────────────────────────────────┘
```

The depicted avatar is conditional on a real authenticated presenter/session; this is a layout specification, **not** an instruction to invent accounts or user identities. Two right-edge utility icons refer to the **selected visual reference**, not approved alert/message workflows. Preserve overall header/sidebar sizes and placements as closely as practical across pages. Use the supplied Collage 2 mockup, not the later isolated atlas render with an extra top-right profile photo, as the common chrome reference. The Network Atlas may retain the richer original Collage 1 map and overlay layout **inside** this shared shell.

## 3. Overview — Network Atlas (UPDATED: Collage 1 direction, 2026-10-25)

### Locked visual decision and goal

**Use the Overview panel of Collage 1 as the primary visual reference**, not the later simplified diagram mockup. The landing page is a map-first, animated resource-network control center with a calm light-gray cartographic backdrop, multiple risk-coded site markers, connecting linework where supported, a restrained legend, zoom/fit tools, and a selected-location popover. This is a **visual design decision**, not a commitment to any mapping vendor or to actual geographic coordinates.

The coordinator should be able to locate a pantry with a projected shortage, identify the first affected day/product, and open relevant details in about ten seconds (proposed usability goal, not a measured result).

### Desktop composition — Collage 1 inspiration

```text
┌────────────────────────────────────────────────────────────────────────────────┐
│ [Slim left sidebar]    Overview · Network Atlas            [Product] [7 days] │
│                        Explore predicted needs across the simulated network.  │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ CARTOGRAPHIC-STYLE MAP CANVAS / FUTURE BASEMAP SLOT                       │ │
│ │ ┌──────────────┐                                    ┌─────────────────┐ │ │
│ │ │ Site status  │                                    │ Selected site   │ │ │
│ │ │ ● Coverage   │       ○ A   ○ B    ◎ HUB  ○ D       │ Name + role     │ │ │
│ │ │ ● Watch      │           ○ C          ○ E  ○ F     │ First deficit   │ │ │
│ │ │ ● Shortfall  │                                    │ Product + date  │ │ │
│ │ │ ● Unknown    │   Optional verified plan/route      │ Inspect site →  │ │ │
│ │ └──────────────┘   overlay, not live shipments       └─────────────────┘ │ │
│ │                                                            [ + ][ − ][fit]│ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
│ Small status/provenance footnote · scenario identity · data timestamp         │
└────────────────────────────────────────────────────────────────────────────────┘
```

This captures Collage 1's **large atmospheric map, floating legend, marker hierarchy, context popover and map controls**. A right-hand persistent inspector may replace the popover only when needed for accessibility/long content; it must not shrink the map into a chart-sized card. Do **not** carry over Collage 1's unsupported 24-location / national-scale numeric claims or invent site photos.

### Visualization layers and geographic readiness

1. **Background layer** — neutral map-like artwork or abstract topographic/road texture in the prototype, clearly labeled *illustrative/schematic*. Do not draw recognizable or labeled real streets unless they match actual grounded site coordinates. A true geographic basemap can be added later.
2. **Site markers** — at least six fictional beneficiary institutions and one or two hubs; selected/hover/focus/risk state represented by shape/outline, text and color. Do not declare arbitrary red/yellow severity thresholds to be V5 policy.
3. **Route layer** — only routes supported by a selected transfer mode; separately identify potential topology from independently verified plan recommendations. A curved line is **not** a real road route, delivery confirmation or transportation ETA.
4. **Selection layer** — a compact floating popover/inspector with site, resource, first projected deficit, local day, projected service/shortfall, data confidence/provenance and an `Inspect site` link. Suppress unrelated site cards and large charts.
5. **Controls layer** — map fit, zoom, site selector, product, date, route overlay toggle and concise status legend. Implement an accessible list of all sites independently of the map.

**Future Google Maps API integration seam (not yet adopted):** define a presentation-agnostic `NetworkMap` boundary whose data consists of stable site IDs, roles, optional *validated* `lat/lng`, selected product/day, result/snapshot ID, marker status, and eligible or planned transfer edges. The initial `SchematicMapRenderer` uses SVG+Motion. A future `GoogleMapsRenderer` may reuse exactly the same selection/inspector/state interfaces while supplying geographic tiles, markers, accessibility alternatives, zoom and real geography. It requires separate consent/decision, key handling, map provider cost/terms, privacy review and geocoded or seeded-but-explicitly-simulated coordinates. If coordinates are unavailable, **fallback to the schematic renderer**, not guessed coordinates. Route travel times require an actual route service, not geometric line length.

### Mapping/operational invariants

- `HUB_ONLY`: hub → beneficiary proposals only. `HUB_AND_PANTRY`: eligible hub or pantry → beneficiary proposals, with donor protected local demand and reserves. No mode defaults on new scenarios.
- A map marker's shortage state is specific to the selected **product and local date/horizon**. Meals and bottles retain independent units. Insufficient observations are labeled unknown, not safe.
- In the prototype the number of markers corresponds to V5's fictional network, not the large number of markers in inspiration imagery. Do not infer real coverage from illustrated geography.
- Map connections indicate feasible or hypothetical transfer relationships only when those facts are actually available. Never animate stock movement for queued, failed or unverified plans.

### Interactions

| Trigger | Presentation | Guard |
| --- | --- | --- |
| Select marker via pointer/keyboard/list | Highlight marker, keep map framing stable, open floating inspector | Selection is read-only; focus restored when inspector closes |
| Map zoom/pan/fit | Respond within bounded neutral map canvas, preserve label readability | No separate globe/3D runtime required |
| Site search | Locate marker, focus accessible site list/popover | Do not search/geocode arbitrary outside locations for demo |
| Change product/local day | Update saved projection labels and marker states | No inference, solver run or inventory change on filter |
| Toggle eligible paths vs planned transfers | Visually distinct styles/legend | Route permission ≠ quantity/date/capacity feasibility; planned paths require independently verified result |
| Inspect site / review action | Deep link to Data Explorer or Recommendations, preserving site/product/date/snapshot | No automatic dispatch or approval |

### Motion

Use **Motion** only for subtle marker selection, popover entrance and one brief route reveal after a verified saved plan is chosen; suggested 160–220ms focus/inspector and 500–800ms on-demand route reveal. Do not use perpetual moving dots, fake shipment vehicles, aggressive zooming, infinite map pulses or fake real-time counts. Under reduced motion, provide stable markers, static arrows and a non-animated popover.

### Overview density boundary

The map is the dominant surface. Keep a compact title, one short operational status statement, filters, legend and inspector. No large Site Performance table, forecast analytics grid, objective sliders or four-card metrics row here; **the four agreed KPI cards live in Data Explorer**. Tiny context measures may be used if they don't crowd the map, but must come from actual data.

### Empty/unknown states

The map should remain navigable when forecast data is missing. Show `Not evaluated`, `Insufficient data`, `No eligible lot information` or similar precisely, with provenance. Never color absent/unknown data as healthy. If geography is unavailable, use the 2D conceptual network with an explicit illustrative label.

## 4. Data Explorer — UPDATED Collage 2 dashboard + Seven-Day Pulse + Operations Board

### Locked design reference and purpose

**Use the Data Explorer panel of Collage 2 as the core desktop composition.** This is the data-rich counterpart to the visually minimal Overview. Keep the dashboard grid stable while allowing users to flip the content of two **specific, independently controlled card slots**. The Network Demand Forecast line graph and Site Performance table are **persistent**, not conditional panels.

### Default dashboard composition (locked)

```text
┌────────────────────────────────────────────────────────────────────────────────┐
│ Data Explorer / [Seven-Day Pulse] [Operations Board] [Inventory] [Forecasts]   │
│ Filters: [Product ▾] [Scope ▾] [7 local days]  Snapshot · provider/quality      │
├────────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────┐ ┌───────────────────┐ ┌────────────────┐ ┌───────────────┐ │
│ │ Households Served│ │ Predicted Fill    │ │ ↻ FLIP KPI     │ │ Food Waste    │ │
│ │   count (source) │ │ Rate: %          │ │ Items at Risk  │ │ Rate: %       │ │
│ │                  │ │                  │ │ Sites at Risk ↻│ │               │ │
│ └──────────────────┘ └───────────────────┘ └────────────────┘ └───────────────┘ │
│ ┌────────────────────────────────────────────────┐ ┌────────────────────────┐ │
│ │ NETWORK DEMAND FORECAST (LINE CHART)            │ │ ↻ FLIP ANALYTICS CARD  │ │
│ │ Historical boundary + 7-day horizon            │ │ Face A: Fill Rate      │ │
│ │ Demand vs selected supported comparator        │ │         by Region      │ │
│ │ [labeled units · method · accessible data]      │ │ Face B: Item Risk     │ │
│ │                                                │ │         Overview       │ │
│ └────────────────────────────────────────────────┘ └────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────────────────────────┐ │
│ │ SITE PERFORMANCE — searchable/sortable fixed location                    │ │
│ │ Site | Scope/region | Served households | Projected fill rate | Risk | Trend│ │
│ │ ...                                                                        │ │
│ └────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

The top row contains **exactly four cards in the default wide layout**. Below them, a wide left forecasting line chart and a narrower right **fixed-footprint** flip card share a row. The Site Performance table spans the width below. At smaller sizes, cards may stack responsively, but **toggling/flipping never changes their occupied slot**.

### A. Four KPI cards — exact selections

| Card/slot | Source inspiration | Display contract | Interaction |
| --- | --- | --- | --- |
| **Households Served** | Collage 1 | Actual observed or explicitly modeled number of unique households served for a stated interval, source and coverage; **never derive household counts from meal/bottle unit totals** | Contextual drilldown; compact microtrend only when sourced |
| **Predicted Fill Rate** | Collage 2 | Percent of forecast-derived requested units expected to be served for the **selected product/scope/window**, with numerator, denominator and source visible in details; do not aggregate incompatible product quantities | Opens service coverage evidence; could include restrained ring indicator |
| **Risk Flip Card** | User decision | **Front: Items at Risk**; **Back: Sites at Risk**. Both faces show a count, explicitly defined first-deficit criterion, product/window/scope and change only when supported. "Items" means distinct product/category entries with projected unmet demand, **not arbitrary physical pieces or lots** unless separately labeled. "Sites" means beneficiary institutions with ≥1 qualifying projected deficit. | Dedicated, clearly labeled flip button or segmented face control; fixed card size, accessible semantic updates |
| **Food Waste Rate** | Existing mockup | Defined percentage (e.g. measured expired/discarded units ÷ documented comparable handled units, by product and period); **V5 does not authorize inventing a production waste rate**, so show unavailable when data insufficient. Forecast waste estimates must be labeled projected and distinct from observed waste. | Opens expiration/waste evidence, no unsupported trend claim |

**Definition gates:** `Households Served` requires household-level or aggregate household service data and deduplication rules not inferred from current meal/water fixture. If missing, show `Unavailable — household data not supplied` rather than a fabricated count. For fill and waste, surface denominator, reporting basis, dates, model/stock provenance, and `N/A` for zero/unknown denominators. Do not claim region-based aggregates unless site region membership exists and is traceable.

### B. Network Demand Forecast — permanent large line graph (Collage 2)

This is the **dominant analytic chart**, not the older bar chart for "Supply vs Demand". Use Recharts for a clean **time-series line chart** with labeled dates on X and product-specific units on Y, legible legends and neutral teal/slate/blue trajectories. Plot historical demand and the seven-day predicted demand on distinct solid/dashed or separated segments with an explicit forecast boundary. Supported comparison series can be **confirmed available supply or projected eligible stock** (labeled correctly), or **forecasted donations** (distinct from confirmed arrivals). Do not mix units or call donations physical on-hand stock.

- Filters: scope (network or site), product, seven local dates, historical display range, saved forecast run and central/conservative assumptions where valid.
- Mouse/keyboard inspection reveals date, historical requested demand or forecast, provider/quality marker, actual source, appropriate unit and selected snapshot.
- Quantile bands appear **only when genuinely produced/qualified** and truthfully labeled; baseline point-only forecasts display no fake interval or confidence probability.
- `Network` aggregation sums values only within the **same product/base unit** and consistent local-date/cutoff policy; site-local dates must be handled explicitly.
- Preserve chart geometry when the *adjacent analytics panel* flips; the line chart **never shrinks or remounts** due to the side panel's state.
- Provide a text summary and an accessible underlying data table.

### C. Flip analytics panel — fixed slot adjacent to Network Demand Forecast

**Front face: Fill Rate by Region.** Compact bar chart comparing predicted service coverage percentages by region/group, with clear product, reporting interval, denominator, and simulated geographic-group labels. Region is **optional metadata** in V5; if regions do not exist in saved fixtures, show a meaningful `Regional grouping unavailable` state or explicitly seeded simulation grouping, **not made-up regions**. Avoid averages of percentages without declared weighting/aggregation.

**Back face: Item Risk Overview.** Compact item/product table (or horizontal ranked bars) with product label, first projected deficit date or days until it, demand versus projected service, unmet units, and evidence/risk wording. Sort mode is explicitly a **display sort**, not an accepted procurement/fairness policy. Because the demonstration fixture contains two products, do not fabricate five risk items solely to fill the card.

**Geometry and control:**

- Both faces occupy the **same grid cell with locked width and height** (e.g. 360–420px panel height at 1440px, responsive via container rules). The wider chart and the table beneath **must not shift, resize or reflow** as the card turns.
- The front/back controls should be visibly labeled `Fill Rate by Region` and `Item Risk Overview`, with flip affordance and current face announced. The user can switch back at any time; state does not change filters or query/plan identity.
- Suggested physical effect: Motion-controlled `rotateY(0deg ↔ 180deg)` on an isolated perspective container, 300–450ms, ease-in-out; render reverse content upright, control `aria-hidden`/`inert` for the hidden face and direct focus to the newly visible face if the user initiated the flip. No backface or hidden buttons may remain tab-focusable.
- On `prefers-reduced-motion`, perform **instant content replacement** (or brief opacity only) with no spatial rotation. Avoid animation before data arrives or for asynchronous solver states.
- Flip state is independent from the risk KPI flip. Do not swap between the forecast graph and the analytics card: **only the small right-hand panel flips**.

### D. Risk KPI flip — independent from analytics flip

The third **top-row KPI card** flips between **Items at Risk** and **Sites at Risk**, without changing any other card, line chart, side panel or table. Both faces use exactly the same metric typography, fixed vertical alignment, card dimensions and stable labels. Use the same interaction/a11y pattern as the analytics flip, optionally a shorter 250–350ms animation. Do not start two simultaneous flips as one combined carousel; each has separate local face state.

### E. Site Performance table — persistent (Collage 2)

A full-width, high-density but readable table *under* the forecast/flip row. Its position remains unchanged during both flips. Recommended columns: **Site/Pantry**, **Region or Scope** (only when grounded), **Households Served** (when sourced), **Predicted Fill Rate (selected product/interval)**, **Sites/Items Risk Evidence** (deficit and first date, not unspecified severity), and **Trend** (only with actual series). Include optional `Eligible Stock`, `First Deficit`, `Unmet Units` via column visibility, not by widening the default table until unreadable.

- Search, sort, product filter, row selection, pagination/virtualization only when needed, and deep links to Site Detail.
- Include all six beneficiaries in the full table; hubs may be separately labeled as sources and not silently counted as beneficiary demand sites.
- Sticky table headings, explicit units, row status text alongside indicators and read-only access for visitors.
- If households or region data are unavailable, show `—`/explicit unavailable state rather than silently synthesizing them.

### F. Seven-Day Pulse — accessible drilldown/subview (retained)

Retain the previously selected **site × seven-local-date projected coverage heatmap**, accessible via Data Explorer secondary navigation (`Seven-Day Pulse`). This is **additional detailed analysis** and does not displace the locked default dashboard layout. Each cell provides forecast-derived target, eligible supply, confirmed arrivals, projected service and unmet units; use distinct observed-zero/missing/unavailable states and an accessible grid/table alternative. Central/conservative modes must be clearly labeled, with no fabricated stockout probability or p90.

**Backend semantics:** daily served = min(eligible available, target); daily unmet = target − served. The backend must independently project dates, arrivals, expiry and donor protection. Late arrivals cannot repair yesterday's unmet demand. Do not sum repeated negative stock-balance traces as if they were unserved units.

### G. Operations Board — accessible site-card subview (retained)

Retain a six-pantries/two-products **site-card grid** under its own secondary tab (`Operations Board`). Each tile shows site name, selected scenario/time context, per-product units, first projected deficit, eligible/held/expired status and incoming assumptions, with a link to detailed inventory. This supports managers drilling deeper **without adding six dense site cards to the main dashboard**.

### H. Forecast evidence, inventory and Site Detail (retained V5 requirements)

- Forecast Explorer: demand and donation forecasts shown separately, historical versus forecast cutoff, actual provider/version/cutoff, missingness/fallback/reuse, chronological MAE/bias/WAPE evaluation with comparable scored sets and sample/coverage counts.
- Inventory: lot-level physical/eligible/held/expired/committed and transferable stock, expiration-aware **hard FEFO** eligibility, confirmed versus predicted arrivals, stock version and immutable audit.
- Site detail: served/unmet by day and product, local reserves, source/recipient plans and limitations. Counts are not corrections; an authorized recorded adjustment is a separate transactional event.
- Simulation and provenance remain visible. Typed backend/Next.js proxy is the source of computation; UI must not invent shortage, household, waste or fairness values.

### I. Unavailable/empty data and consistency rules

If source household counts, grouping fields or disposal accounting are absent, those particular KPI/table cells show unavailable; the rest of the dashboard remains usable. Network Demand Forecast may use an approved labeled baseline/fallback when permitted. No missing data is treated as a true zero; no proposed transfers are labeled executed. Flipping cards does **not** trigger backend compute, silently change the selected scenario, or mutate cached results. All charts/tables display the same selected snapshot and product scope.

## 5. Recommendations — Collage 2 Action Plan (SELECTED, 2026-10-25)

### Selected visual direction and user story

**Keep the Recommendations tab from Collage 2**, rather than Resource River or the unselected earlier mockup. The screen should resemble an operations decision queue, not a shipment-tracking app. Its user story is: *As a network coordinator, I want to inspect feasible corrective options derived from predicted shortages and saved allocation plans, understand who benefits and what remains unresolved, and record a simulated review without executing physical actions.* Related inherited stories: US-07 (feasible plans), US-08 (explanations), US-09 (scenario comparison), US-10 (scarcity/failure), US-12 (transparency), and V4 US-15–18 (research difference). In V5, its lifecycle comes from §§2, 8–14 and acceptance V5-A09/A11/A14/A15.

### Composition (locked pattern; final copy and spacing may be refined)

```text
COLLAGE 2 LEFT SIDEBAR │ RECOMMENDATIONS / Actionable Insights   · SIMULATED
                        │ [Action Plan] [Site Recommendations] [Network Optimization] [Impact & Fairness]
                        │ ┌────────────────────────────────────────────────────────────────────────┐
                        │ │ Network need summary: dated shortages / unresolved beneficiary goals     │
                        │ │ Selected scenario, method, mode, provenance, solver/verification status │
                        │ └────────────────────────────────────────────────────────────────────────┘
                        │ ┌─────────────────────────────────┐ ┌──────────────────────────────────┐
                        │ │ RECOMMENDED ACTIONS             │ │ IMPACT PREVIEW                   │
                        │ │ [Site ▾] [Product ▾] [Sort ▾]   │ │ Selected *whole verified plan*   │
                        │ │                                 │ │ Before/after service & unmet     │
                        │ │ [ ] Candidate transfer A        │ │ Evidence / source / constraints  │
                        │ │ [ ] Candidate transfer B        │ │ Trade-offs / residual needs      │
                        │ │ [ ] Expiry-related finding      │ │ [Inspect evidence]              │
                        │ │ Supplier drafts: paused/NA      │ │ [Compare in Scenario Lab]        │
                        │ └─────────────────────────────────┘ └──────────────────────────────────┘
                        │ [Open plan details] [Mark reviewed — simulation]* [View audit]
                        │ *Only for authenticated presenter, saved eligible plan; no stock/dispatch effect
```

**Four in-page tabs** are the visual hierarchy from Collage 2; they are subsections of Recommendations, not extra global left-sidebar items:

1. **Action Plan (default):** recommendation queue/table with source, target, product/unit, first deficit, candidate type, scenario/method origin, and `View details`/`Inspect evidence` controls. Urgency tags are *display descriptions of dated risk*, not an unapproved algorithmic priority score. Use checkboxes only for visual multi-selection or side-by-side inspection; they must not execute shipments, purchases or bulk approval. Do **not** copy the mockup's `Implement selected` CTA; replace it with `Review selected` or `Inspect plan`, conditioned on backend capabilities.
2. **Site Recommendations:** filter the same saved advice by site, display donor/local reserve implications, affected inventory lots and projected remaining unmet need. Distinguish a receiving beneficiary from a sending source.
3. **Network Optimization:** show which `CLASSICAL_GP` or `EGP_PI_INSPIRED` verified plan the proposals belong to, a read-only methods-summary link, common frozen scenario/mode, constraints and uncovered demand. A navigation action opens Scenario Lab; this tab does not run hidden optimization.
4. **Impact & Fairness:** show plan/site before–after metrics, per-beneficiary/product `target`, `served`, `unmet`, coverage, normalized/weighted shortfall and AP/RP indicators, plus cost/waste trade-offs **only when supported**. Refer to research-specific explanations without asserting one plan is universally best.

### Impact Preview, evidence and allowed actions

- The **right-side Impact Preview** remains in a fixed-width panel next to the recommendation list at desktop widths. On mobile, it becomes an explicit selected-action details sheet or follows the list; the list must not become unusably narrow.
- A selection changes visible details **without changing the underlying scenario, plan, audit or data**. Show separate headings for **selected recommendation details**, **plan-level projected impact**, and **remaining unmet need** to prevent causal confusion.
- Before/after values must be produced from a **saved, independently checked plan/scenario** and must declare product, unit, horizon, method and snapshot. A verified *whole-plan* comparison or documented before/after service is permissible. **V5 OPEN-02** has not selected a stand-alone per-transfer counterfactual benefit method; consequently **do not claim `+300 households`, `-90% stockout probability`, or additive per-transfer improvement** from a selected action without independent evidence and an approved definition.
- Recommendation details must show **origin, destination beneficiary, product and unit, eligible lot(s), suggested quantity, dispatch/arrival/use eligibility, first deficit, sender reserve protection, receiving/handling limits, cost basis when finalized, stock/version references and unresolved residual need**. Display only valid evidence; unsupported fields say `Unavailable` rather than fabricating estimates. The renderer does not calculate eligibility.
- **Priority and sort controls:** `First deficit date`, `Site`, `Product`, `Unmet units (same product/unit only)`, and `Plan/method` are allowable presentation sorts/filters when the fields exist. Labels like `High` or `Critical` must have published display thresholds and never silently act as solver policy, protected vulnerability classification or procurement ranking. Different products must not be ranked by an undeclared aggregate unit total.
- If a draft supplier proposal feature later becomes available, render **separately** with `DRAFT — simulated / not submitted`, vendor terms, arrival-dependent coverage, shared *supplier-only* budget, alternatives and uncovered need. **V5 §11 / OPEN-26–28 remain PAUSED**. No `Purchase now`, no live vendor integration and no automatic increase to confirmed/on-hand stock. Do not treat a supplier budget as a general transfer optimizer budget.
- Actions: `Inspect evidence`, `View site`, `Compare methods`, `Create scenario from assumptions` (new frozen scenario; presenter), and `Mark reviewed — simulation` (presenter and saved valid plan, with **no** stock/dispatch/payment effect). On the visitor view, show explanation and disabled/hidden presenter actions with clear permissions. Do not show `Take Action`, `Implement Selected`, `Send Transfer`, or `Approve Purchase` as operating P0 commands.
- If results are queued, incomplete, stale, infeasible, invalid or method-specific failures occur, keep the last valid plan visible with its timestamp and an explicit warning; **never use recommendation cards that imply a verified allocation when the actual solver result is unavailable**.

### Motion and interaction boundaries

- Selecting a row highlights it and updates the inspector with a short 160–220ms transition; on keyboard, focus stays controlled and details are available without hover. Respect reduced motion.
- Switching the four in-page tabs preserves the global shell and fixed contextual filters; changing a tab must not submit compute or mutate data.
- The Impact Preview is a contextual **plan-impact explanation**, not a Resource River network/Sankey and not evidence that any corrective action has been performed.

### Acceptance checklist for this tab

- [ ] Collage 2 sidebar and Recommendations layout are identifiable: four subsection tabs, queue left, context-rich Impact Preview right.
- [ ] At least six beneficiary sites and both products can be represented across the selected scenario; no fabricated demo action count.
- [ ] Each suggested transfer ties to a frozen scenario, method, verified plan and backend-proven feasibility or is clearly unavailable.
- [ ] All data-rich impacts distinguish plan/site-level metrics from unapproved per-transfer benefit attribution.
- [ ] Explicit residual unmet demand, product units, first deficit dates, donor protection and plan limitations are inspectable.
- [ ] Presenter review writes a simulation-only reviewed marker, with no inventory/order/shipment effect; visitor remains read-only.
- [ ] Supplier draft section remains clearly paused until its separate contract/implementation decisions are resumed.

## 6. Scenario Lab — guided Collage 1 wizard + Collage 2 Decision Studio (SELECTED, 2026-10-25)

### Primary concept

**Two allocation methods, one controlled comparison:** classical goal programming (`CLASSICAL_GP`) vs the bounded vulnerability/AP/RP-informed research adaptation (`EGP_PI_INSPIRED`). Both receive the same **immutable operational snapshot, transfer mode, candidates, hard feasible region and equivalent solver settings**. A change in objective can change who receives resources without meaning one method is universally "better." Scenario Lab retains the detailed V5 comparisons while adopting **Collage 1's numbered guided sidebar** and **Collage 2's results/insights layout**.

### Selected desktop composition — guided wizard + analytical results

```text
GLOBAL LEFT SIDEBAR (Collage 2): Overview | Data Explorer | Recommendations | Scenario Lab
SCENARIO LAB  /  saved scenario + snapshot + mode + policy + job/verification status
┌──────────────────────────┬───────────────────────────────────────┬───────────────────────────┐
│ GUIDED CONTROLS          │ SCENARIO RESULTS (Collage 2)          │ COMPARISON (Collage 2)    │
│ ① Choose context & goals │ KPI cards (declared basis only):      │ Baseline ↔ new scenario   │
│ - Site/product scope     │ - Service coverage / unmet demand    │ or classical ↔ research   │
│ - Forecast/run cutoff    │ - Cost / eligible waste if supported  │ (explicit comparison type)│
│ - Policy version (read)  │ - AP/RP research measures            │                           │
│ ② Adjust constraints    │                                       │ KEY TRADE-OFFS            │
│ - EXPLICIT transfer mode │ PROJECTED FILL RATE BY SITE          │ - Who gains/loses service │
│ - Validated disruptions  │ Six beneficiary rows/plot by product │ - Residual shortages      │
│ - Eligible capacity/ETA  │ Target vs served; zero-target = N/A  │ - AP/RP/cost/waste effects │
│ ③ Freeze & compare      │                                       │ - Reasons & limits        │
│ - Preview draft diff     │ Saved scenario/method details         │                           │
│ - Create NEW scenario    │ + plan status/independent evidence   │                           │
│ - Run paired comparison  │                                       │                           │
└──────────────────────────┴───────────────────────────────────────┴───────────────────────────┘
             Expandable: per-beneficiary × product table, allocation diffs, binding constraints,
                         attributes, full objective terms, snapshots, methodology/audit
```

**Desktop:** left wizard fixed/readable (~260–320px subject to viewport), results dominate center, comparison and trade-offs in right rail; charts and facts must not be so compressed that units/status disappear. The stepper's **numbered circles are retained visually from Collage 1** (`1. Set Your Goals`, `2. Adjust Constraints`, then an explicit third submission step), but the actual controls are bounded by V5. At ~1280px allow the comparison rail to stack below results; at 390px use one step at a time and stacked result panels. The global sidebar remains the Collage 2 shell.

### Numbered guided flow and permitted controls

| Wizard step | User intent | UI elements | Product-authority guard |
| --- | --- | --- | --- |
| **1 — Select context & goals** | Decide *what is being examined* | Selected dataset/snapshot, beneficiary/product scope (six+two required for full demo), saved seven-day forecast run, explicit comparison type, approved immutable policy version; show short readable objective summaries | **Do not** interpret the Collage 1 `Minimize Stockouts / Reduce Food Waste / Improve Equity / Minimize Cost` sliders as four already-accepted independent policy weights. Use these phrases as explanatory goals or non-operative preview labels **until OPEN-23/24/25 have been resolved and documented**. The actual primary pair must be `CLASSICAL_GP` vs `EGP_PI_INSPIRED`. |
| **2 — Adjust constraints & disruptions** | Explore a plausible alternative scenario | Required `HUB_ONLY` or `HUB_AND_PANTRY` mode with **no preselected default**, currently validated dated donation/demand/confirmed-supply assumptions, explicit eligible route/ETA/capacity fields **only if backend contracts support editing them**, product/unit and horizon choices | Constraints are **hard feasibility rules**, not sliders to weaken donor protection/FEFO/conservation. A `Total Budget $50,000` or `Max Redistribution Distance 100 miles` slider from Collage 1 is **not an accepted general solver parameter**; supplier draft budgets are separate and paused, while route/ETA/capacity and costs remain subject to OPEN-19/21/22. Do not expose `Priority Regions` as a fairness group selector without verified region data and accepted policy mapping. |
| **3 — Review, freeze & submit** | Compare an explicit what-if against reproducible evidence | Draft-vs-current diff, input validation and estimated effect caveat (no claimed result); `Create New Frozen Scenario`, then `Compare Methods`/`Run Scenario` submits a durable comparison job; display progress/outcomes | Frozen immutable scenario with all source/version references; user edits never modify a saved one. Submitting returns **202 accepted**, not a completed result. Paired solvers run on the **same** snapshot/mode/constraint set; do not display an unverified vector, fake ETA or synthetic success. Presenter-only submissions. |
| **4 — Inspect & review outcomes** | See which trade-offs were produced and why | Scenario Results, per-site fill chart, comparison, key trade-offs, allocation diff, AP/RP, provenance, `Mark reviewed — simulation` for authorized valid plan | This is the **results stage**, not a separate hidden optimizer. Failures/partial availability, staleness, manual retry, and independent verification remain visible. No real dispatch or purchase. |

**Additional control constraints from V5 §§8–11:**

1. **Topology:** `HUB_ONLY` permits hub → beneficiary; `HUB_AND_PANTRY` additionally permits eligible beneficiary → beneficiary while protecting the origin's *dated* local service and reserve. No self-transfer, beneficiary as destination only, no same-batch forwarding; route permission alone does **not** prove a feasible shipment.
2. **Dated demand and stock:** forecast-derived per-day rounded targets across a bounded planning window within **seven future local dates**, exact physical/eligible/transferable stock distinction, commitments and confirmed arrivals only, lost unmet demand counted on its actual day (no silent carryover), hard FEFO and expiration/arrival eligibility. Do not let users drag an invalid amount through an otherwise attractive control.
3. **Hard shipment feasibility:** conserve integer units and product compatibility, protect donor site reserves, stay within receiving and joint handling/transport capacities, respect origin/destination permissions, ETA, per-lot expiration and confirmed stock. The solver and independent checker validate them. **Cost trade-offs cannot disable hard constraints.**
4. **Soft research constructs:** documented vulnerability attributes, normalized and weighted deprivation, group AP/RP flags and **soft excess penalties**. AP/RP are not absolute hard requirements that make a scarce instance infeasible. Editable thresholds, coefficients, allowed shares or policy weights require V5 **OPEN-23/24/25** decisions, validated ranges and independently tested encoding; no made-up presets.
5. **Separate supplier planning:** a **frozen simulated supplier basket budget** belongs only to the *paused* supplier proposal scope, with after-arrival coverage; it is **not** the transfer plan's budget control. No operational spending.
6. **No false location controls:** true routing distance/time, map radius, geographic `Priority Regions` and Google Maps/Routes require grounded location data and accepted ETA/route rules; do not infer them from illustrative cartographic backgrounds.
7. **States and comparison identity:** changing mode or any policy/input creates a **new scenario**; comparisons across modes are separate-scenario experiments, not a classical-vs-research method pair. Same-snapshot/feasible-region checking is required before results are labeled comparable.

### Collage 2 result panels — content specification

| Panel | Accepted visual treatment | Real data requirement / what not to claim |
| --- | --- | --- |
| **Scenario Results** | Compact horizontal KPI cards across central result workspace; examples of *types* of cards: `Projected Service Coverage`, `Unmet Units` (product-specific), `Estimated Cost` (if defined), `AP/RP Deprivation` (research result). | A mockup's `People Served`, `Total Cost $1.1M`, `Equity Score +24%`, and arbitrary `-62% Stockouts` are not current source facts. Household counts and a synthetic overall equity score are **not accepted derived measures**. Only display saved denominators, units and validated deltas. |
| **Projected Fill Rate by Site** | Primary **six-site** horizontal bar chart/table with selected product/unit and seven-day scope, target vs served, % coverage, and site click-through. May use neutral slate for one verified method and teal for the other on a *same-snapshot* pair; give text/table alternative. | Fill rate = served/target on each positive-demand beneficiary-product goal; for zero target show `N/A` (not 100%). Never combine meal and bottled-water unit totals or double-count arrivals as served stock; no unsupported region mapping. |
| **Comparison** | Right-rail compact bar/chart with labeled `Comparison mode: Methods` (same scenario) or `Comparison mode: Scenarios` (two separately frozen scenarios). May choose fill rate, unmet units for a chosen product, AP/RP share with denominator or correctly defined cost/waste. | **Never** compare unrelated objectives as a universal optimization score. Separate method-change conclusions from changed data/mode-policy comparisons; show method-specific errors without substitution. Saved reference IDs visible. |
| **Key Trade-offs** | Four or fewer readable bullets/rows with direction arrows, one affected institution/product, and short plain-language explanation linked to evidence. | Explain gains **and losses**, uncovered need, donor protection, expiry/transport constraints, and AP/RP implications. Distinguish a proven binding constraint from a guessed bottleneck. No invented causal per-transfer benefit (OPEN-02). |
| **Detail expansion** | Accessible drawer below/alongside comparison for per-goal table, vulnerability weights and source, actual solver status, AP/RP thresholds/flags, objective decomposition, candidate lot-level transfers and full audit. | This is required V5 evidence, not expendable decoration. Maintain exact units, dates, snapshot/policy hash, native status and independent verification. |

### Submission, animation and failure semantics

- Controls are editable **only for a presenter** and only after public API/validator decisions permit it; read-only visitors can inspect frozen runs and comparisons.
- Each numbered step indicates `Incomplete`, `Valid draft`, `Ready to submit`, or `Saved` as appropriate. Invalid input identifies its field and preserves keyboard focus; hidden defaults are prohibited. Avoid suggesting a modification to hard safeguards is a permissible optimization choice.
- Use Motion for step-to-step transitions (short slide/fade) and for **verified** changes in the Projected Fill Rate by Site or Comparison bars. On queued, running, interrupted or failed jobs, preserve the previous valid result with status/time; never animate speculative outputs. Provide reduced-motion substitutions.
- Main right-rail comparison/Key Trade-offs and center Scenario Results/Fill Rate by Site should retain stable panel geometry when changing steps and switching comparison metrics. Detailed evidence can scroll or expand deliberately, rather than causing accidental dashboard reflow.

### Scenario editing: draft versus committed

- Explicit **HUB_ONLY / HUB_AND_PANTRY** transfer mode selector; **no default**. Changing it produces an entirely new scenario, not a direct A/B model comparison.
- Scope/site/product and excluded inputs visible and justified; no missing site silently omitted.
- Select known forecast run and planning horizon inside available seven local dates; distinguish selected estimate from original provider output.
- Disruption inputs such as changed donation, demand multiplier, confirmed arrival delay, capacity or route assumptions **must be validated by a finalized server contract**; candidate fields are not permission to invent server payloads.
- Policy selector shows **accepted frozen policy version**, referenced source and prepared vulnerability attributes; permitted editable coefficients/thresholds must use validated documented ranges **only after OPEN-23/24 closure**.
- Slider changes mark **Draft changes — not computed**, never mutate a saved scenario or animate a plan as if solver output already exists. Provide numeric keyboard control and explicit `Create scenario` / `Compare methods` actions.
- Submissions use durable jobs; show `Queued`, `Running`, `Saved/Verified`, `Interrupted`, `Failed`, `Partially available` and manual retry when supported. Retain last valid result during new computation, visibly timestamped.
- A pair uses one method-comparison job on the same saved snapshot. Do not show result B for snapshot Y next to result A for snapshot X.

### Required Decision Studio evidence

For **every beneficiary × product with positive target**:

- `target` (forecast-derived rounded integer units), `served`, `unmet`, `service ratio`.
- Normalized shortfall `δ = unmet/target`; zero target has null service ratio and is excluded from AP/RP denominators.
- Prepared institution-level vulnerability attributes, raw/source/provenance, coefficient versions and weight `v`.
- Weighted normalized shortfall `z`, AP and RP flags / thresholds, supported group/denominator definition; distinguish per-product groups and network aggregate explicitly.
- Shared constraints, candidate shipments, eligible lots/FEFO, available capacity, donor reserve, arrival window, cost/time/waste definitions.
- Solver native status, independent verification status, time and meaningful objective breakdown. `FEASIBLE` is not `OPTIMAL`; `UNKNOWN` or `MODEL_INVALID` is not a computed allocation.
- Changes in allocations and consequences: a site may benefit while another loses served coverage; do not claim Pareto improvement.

**Research logic summary (explanatory, not executable specification):**

```text
r[i,p]   = forecast-derived integer target
f[i,p]   = feasible service (0 <= f <= r)
u[i,p]   = r - f
δ[i,p]   = u/r for positive r
v[i]     = 1 + λ × Σ (attribute_coefficient[k] × prepared_attribute[i,k])
z[i,p]   = v[i] × δ[i,p]
W        = Σ z[i,p] across positive-target beneficiary-product goals
Z        = max z[i,p] across those goals
B        = β×W + (1−β)×Z
AP flag  = weighted shortfall strictly above absolute threshold
RP flag  = weighted shortfall − same-product group mean strictly above relative threshold
```

The concept also carries **soft excess-deprivation penalties** and declared normalized cost/waste terms. **Full coefficients, integer encoding, equality boundaries, classical comparator and methodology validation remain gated in V5**; never hardcode arbitrary numerical defaults in the product or claim that the bounded adaptation reproduces the paper exactly. The solver and independent checker own these calculations; the frontend only presents documented backend values.

### Comparison components (including the newly selected Collage 2 panels)

| Component | Purpose | Guard |
| --- | --- | --- |
| `MethodPairHeader` | Same scenario, transfer mode and two method statuses | Compare only identical frozen inputs |
| `GuidedScenarioStepper` | Numbered Col. 1 steps: context/goals, constraints/disruptions, freeze/submit, inspect | Hard constraints cannot become optional weight sliders |
| `ScenarioResultsSummary` | Collage 2 compact result cards with typed values/denominators | No synthetic equity score/households or unsupported cost |
| `ProjectedFillRateBySite` | Collage 2 per-beneficiary per-product service ratio bars with `N/A` for zero target | Six beneficiaries; explicit unit, product, window and valid plan |
| `ComparisonRail` | Collage 2 fixed rail comparing same-scenario methods **or** two separately frozen scenarios | Label comparison type; show method failures independently |
| `KeyTradeoffs` | Collage 2 concise evidence-linked gains/losses and remaining need | No invented per-transfer benefit or guaranteed universal improvement |
| `ServiceComparisonBars` | Per-site/product target vs served; click difference to drill down | Units/product clearly separated |
| `AllocationDiffTable` | Lot/source/destination/quantity changes between methods | No invented differences for failed solve |
| `FairnessBreakdown` | AP/RP, weighted/unweighted shortfalls, vulnerability attributes | Exact denominator/normalization and provenance |
| `ObjectiveBreakdown` | Disclosed weighted/Chebyshev/excess/cost/waste terms | Never compare unrelated objective scales as a universal score |
| `ConstraintInspector` | Hard constraint and known binding reasons | Differentiate proven binding constraint vs inferred bottleneck |
| `BeforeAfterScenario` | Compare old and new fully frozen scenarios | Label *scenario change* separately from *method change* |
| `MethodologyDrawer` | Paper DOI, local adaptation differences, limits | Attribution always available |
| `ReviewBar` | `Mark reviewed — simulation` on saved plan | No inventory, payment or dispatch effect |

### Research demonstration acceptance

A deterministic fixture must show an interpretable change in at least one assignment caused by active vulnerability/AP or RP logic, with **independently checked** feasibility and counterexample/ablation evidence. Animation should follow the validated completion event, not the user's uncommitted slider input. Research attribution/limitations should be visible near the primary comparison.

## 7. Methodology & Audit (required supporting destination)

This is accessible from the global navigation and via contextual links on every major result. It is not a substitute for brief local explanations on the Overview and Scenario Lab.

Sections:

- **Data/provenance:** historical vs simulated/proxy, sources/coverage, site-local timezone, lot ledger, revisions, immutable source versions.
- **Forecast methodology:** actual provider and model revision, fallback/reuse, missing observations vs true zero, cutoff, seven dates, evaluation samples/metrics and uncertainty limitations.
- **Allocation methodology:** classical vs research method, operational constraints, scaling, explicit AP/RP measures, institutional vulnerability attributes and policy version.
- **Research attribution:** Rampazo et al., *An extended goal programming framework incorporating poverty measures: application to food bank logistics*, first online September 11, 2026, [DOI 10.1111/itor.70252](https://doi.org/10.1111/itor.70252); describe the project as an **EGP-PI-inspired bounded adaptation**, not exact reproduction or proof of real-world fairness improvement.
- **Event/audit viewer:** identity/version/actor/timestamp for mutation, scenario, forecast, solve attempts, review/reset and corrections. Protect sensitive values and technical logs.
- **Limitations:** simulated operational and vulnerability data; no live partner donations, real dispatch, food-safety guarantee, calibrated stockout probabilities by default, or purchases.

## 8. Global interaction and recommendation-to-scenario journey

```text
Open Overview
  → find at-risk site in Network Atlas
  → click site → Data Explorer: Site Detail / Seven-Day Pulse
  → inspect forecast and inventory evidence
  → open Recommendations: review feasible suggestions and uncovered needs
  → open Scenario Lab: compare CLASSICAL_GP vs EGP_PI_INSPIRED
  → modify assumption/policy in DRAFT → create NEW frozen scenario
  → submit durable paired comparison → await saved verified results
  → inspect changed allocations, AP/RP, cost/waste and failures
  → mark reviewed (simulation only) / examine audit / replay demo
```

A visitor follows the same reading flow up to inspection of saved data, but cannot change stock, submit new scenarios, review or reset.

### Deep link / context preservation

- Cross-page links carry **site, product, selected future local date, snapshot/scenario ID and method** if applicable.
- Never silently replace an archived snapshot with the newest operational data when linking to a historical plan.
- The URL and on-screen context must agree. Surface a clear “Archived scenario; current data has changed” warning where appropriate.
- Changing resource filters does not change a completed plan's original frozen inputs; incompatible filter choices display a clear no-data/out-of-scope state.

## 9. Design system — manager-oriented neutral palette

These are **proposed visual tokens**, subject to accessible rendered contrast review and acceptance. Colors encode state only after text/shape semantics are established.

| Token | Hex | Intended use |
| --- | --- | --- |
| `--pp-canvas` | `#F5F4F0` | Cool/warm-neutral app backdrop |
| `--pp-surface` | `#FFFFFF` | Cards, menus, panels |
| `--pp-surface-muted` | `#ECEFEB` | Secondary grouped surfaces |
| `--pp-ink` | `#26343A` | Primary text / headings |
| `--pp-ink-muted` | `#52636A` | Secondary text |
| `--pp-border` | `#D9DFD9` | Dividers and outlines |
| `--pp-teal` | `#416F68` | Primary button, focus-adjacent interactions |
| `--pp-teal-soft` | `#DCEAE4` | Selected/supported status background |
| `--pp-forecast` | `#567A91` | Forecast marker/line (in addition to line style) |
| `--pp-warning` | `#A7773B` | Caution/at-risk text/icon with verified contrast |
| `--pp-danger` | `#A65B50` | High projected deficit/error semantic, contrast-checked |
| `--pp-neutral` | `#7A898C` | Undetermined/pending visual label |

**Color rules:** Only a single high-emphasis primary action per view. Risk is signaled with a readable textual label, distinctive icon/shape or pattern, not alone by changing node colors. Do not imply mathematical probability with a red gradient. Use neutral grays for pending or unknown, never green for unknown.

### Typography, spacing, density

- Prefer **IBM Plex Sans** for operational UI; system sans fallback. IBM Plex Sans Condensed is optional for discreet labels (matches existing art-direction proposal), not necessary for readability.
- Numbers use `font-variant-numeric: tabular-nums`; consistent unit and date formatting per site locale/timezone.
- Type hierarchy: 22–28px page title, 15–17px panel heading, 13–14px body, 11–12px supporting metadata; never shrink crucial chart labels beyond readable size to fit extra panels.
- Spacing system: 4px base (4/8/12/16/24/32). Borders 1px, radii ~6/12/18px. One low-contrast shadow at most, otherwise rely on grouping/dividers.
- Dense data tables are appropriate **inside Data Explorer or expanded inspector**, not Overview.

## 10. Component library and animation strategy

### Already accepted in the repository — use these first

| Library / foundation | Role | Implementation notes |
| --- | --- | --- |
| [Next.js](https://nextjs.org/) 16.4.3 + React 19.3.0 + TypeScript | App Router / server shell and narrow client islands | Do not replace current package/lock structure |
| [Tailwind CSS](https://tailwindcss.com/) 4.3.x | Tokens, spacing, responsive composition | Reuse existing token/config foundation; no parallel visual theme |
| [shadcn/ui](https://ui.shadcn.com/) + [Radix](https://www.radix-ui.com/) primitives | Tabs, dialog, sheet, tooltip, select, button, forms, badges, sidebar, tables | Source-owned accessible primitives; audit keyboard/focus behavior after customization |
| [Recharts](https://recharts.org/) 3.10.1 | Forecast lines, area/bands when real, bars, grouped method comparisons | All derived quantities must come from validated API; retain data-table alternatives |
| [Motion](https://motion.dev/) 14.6.0 | SVG/node transitions, selected-site inspector, scenario result differences, staggered list updates | Central JS motion library; `MotionConfig reducedMotion="user"` plus explicit alternatives |
| [Lucide React](https://lucide.dev/) 1.61.0 | Consistent line icons | Semantic and restrained, not large decorative art |
| `tw-animate-css` 1.4.0 | Small primitive CSS transitions | Complements, does not compete with, Motion |
| [Watermelon UI](https://ui.watermelon.sh/home) | Approved source for selected dashboard blocks / interactive primitives | Copy only specific vetted components; restyle to PantryPulse tokens; check dependencies and licensing |
| [Kokonut UI](https://kokonutui.com/) | Approved source for selected accessible component patterns and interactions | Same source-copy and style normalization rule |

**Version accuracy:** The versions above reflect inspected `apps/web/package.json` at design-authoring time, not a promise that they will remain unchanged. Respect root `package-lock.json` as dependency authority.

### Additional user-supplied references — selection boundaries

| Source | Decision | Rationale |
| --- | --- | --- |
| [Three.js](https://github.com/mrdoob/three.js/) | **Use only optional `/design-lab` 3D prototype** per ADR 0004 | Not necessary for 6-beneficiary production network; GPU/performance/keyboard burden. Lazy load, 2D fallback, accessible site selector |
| [React Spring](https://www.react-spring.dev/) | **Do not add** | Redundant animation runtime; Motion is accepted |
| [Bklit](https://bklit.com/) | **Do not add** | Recharts is the accepted quantitative chart library |
| [Variant](https://variant.com/) | Design inspiration only | No approved runtime dependency; review visual patterns, not proprietary asset copying |
| [Godly](https://godly.design/) | Design inspiration only | Reference editorial quality/motion restraint, not a component dependency |
| [Aceternity UI](https://ui.aceternity.com/components) | Candidate reference / individual pieces only after review | Avoid animated backgrounds/glowing borders/marketing effects in the manager dashboard; new dependencies need ADR review |
| [Refero](https://styles.refero.design/?q=animated+data+dashboard) | Mood-board reference | Inspiration for density/hierarchy; no runtime dependency |
| Other libraries | Proposal only | Need explicit approval for runtime additions beyond the accepted stack |

### Recommended component-to-library mapping

| UI element | Recommended approach |
| --- | --- |
| Network Atlas | Cartographic-style responsive **SVG**/CSS backdrop with accessible marker/site list; Motion for selection and popup; `NetworkMap` renderer interface to allow future verified Google Maps adapter without changing domain/view-model contracts |
| Main Data Explorer dashboard | 4 fixed-position KPI cards + Recharts Network Demand Forecast line chart + fixed-footprint analytics flip panel + full-width Site Performance table; CSS Grid; shadcn cards/tables and Motion controlled 3D flip |
| Risk KPI flip | shadcn Card with two accessible faces (`Items at Risk` / `Sites at Risk`), independent controlled face state, fixed dimensions, Motion rotateY and reduced-motion instant switch |
| Analytics flip | shadcn Card + Recharts region bar chart / compact Item Risk table; isolated fixed grid cell, independent face state, no chart/table reflow |
| Seven-Day Pulse | Secondary tab: semantic HTML/CSS grid or table with per-cell detail buttons; Motion only for selected date highlight (no continuous sweep) |
| Operations Board | shadcn `Card` / `Tabs` / `Sheet` and lightweight Motion focus transition |
| Inventory & history | shadcn Data Table pattern (optionally TanStack Table if already approved/added via component recipe), sortable/filterable tables, `ScrollArea` |
| Forecasts | Recharts lines/areas, chart tooltip, legend, controlled site/product selector and accessible data table |
| Recommendations — Collage 2 selected | shadcn `Tabs`, `Data Table`, `Sheet`, `Badge`, `Alert`, `Collapsible`; action-queue/list beside fixed contextual Impact Preview. No Resource River as main visualization |
| Scenario builder | Numbered, labeled `GuidedScenarioStepper` using shadcn `Form`, `Select`, `Input`, `RadioGroup`, `AlertDialog`; `Slider` **only for V5-finalized editable bounds**, never for an invented budget/distance/objective weight |
| Scenario Lab result/compare | Collage 2 `ScenarioResultsSummary`, `ProjectedFillRateBySite`, `ComparisonRail`, `KeyTradeoffs` over Recharts grouped bars + shadcn table/drawer; per-product and same-snapshot checks |
| Async jobs and failures | shadcn `Skeleton`, `Alert`, accessible status row, explicit retry control; stable UI, not speculative loading animations |

No component is accepted solely because it looks attractive on a library marketing page. Verify license, interaction semantics, keyboard access, visual fit, performance and reduced-motion support before copying it.

### Animation vocabulary

| Event | Motion guideline | Reduced-motion substitute |
| --- | --- | --- |
| Select a network site | 160–220ms focus/scale/panel transition | Immediate selection + visible outline |
| Reveal a verified route | One ~500–800ms directed reveal | Static arrow/line and textual description |
| Open details / tabs | ~160–220ms subtle content transition; Collage 2 left sidebar selected-state remains stable | Instant layout, optional small opacity |
| Recommendation selection | ~160–220ms row focus and stable right Impact Preview content swap | Immediate inspector replacement, explicit new heading |
| Scenario wizard step | ~160–220ms numbered-state/step transition; preserves scenario context and constraints | Immediate step content; current step announced |
| Flip risk summary KPI | ~250–350ms isolated card face rotation; fixed footprint | Instant swap with correct focus/announcement |
| Flip region-vs-item analytics | ~300–450ms isolated card face rotation; **zero layout shift** | Instant swap with correct focus/announcement |
| Changed scenario result | ~250–400ms after **committed** result, one animation | Immediately show exact new values and delta labels |
| Load or queue job | Stable progress/state label; no fake percentage | Same static state and text |
| Change a draft input | Immediate unsaved/dirty state, **not** method-result animation | Same label |

Always disable continuous motion under `prefers-reduced-motion`; no flashing/high-frequency pulses. Announce a finalized meaningful change once to assistive technology, not every intermediate animation frame.

## 11. Frontend technical boundaries and data interfaces

**Target architecture:** browser → Next.js UI and thin **same-origin Next.js proxy** → FastAPI versioned backend → PostgreSQL/immutable saved results; long-running forecasting/optimization occurs in **durable supervised jobs**. This is the V5 target, not evidence that corresponding API/client code already exists.

- **Frontend owns:** view state, selection, accessible interactions, presentation/formatting of server-computed results, local **draft** edits and navigation.
- **Backend owns:** stock truth, lots, FEFO, forecast generation/validation, missingness, frozen scenarios, solver hard constraints/objectives, AP/RP metrics, independent solution checking, version/status semantics, audit and permissions.
- **API schemas:** generated from finalized FastAPI/Pydantic OpenAPI into TypeScript. No independent hand-authored public DTOs that drift from V5. Existing candidate API routes in older drafts are **not proof of implemented endpoints**.
- **FastAPI authorization:** presenter-only mutations enforced server-side even behind Next proxy. Never expose secrets in `NEXT_PUBLIC_*`, client hydration or logs.
- **Safe reads:** changing a day/product/tab/site is a saved-result read/filter; no implicit inference or optimization on GET.
- **Data keys / identity:** use immutable `scenario_id`, `snapshot_id/hash`, `forecast_run_id`, `plan_id`, `policy_version`, `product_id`, `site_id`, source revision, actual provider/fallback state and local dates where finalized. Exact field names/types remain subject to authoritative contract completion.
- **Result publication:** a `202 accepted` submission is **not** a verified result. Show wait/queued state until separately saved and validated. Keep partial method failure explicit.
- **Staleness:** stock version, updated source data or new assumptions may make old recommendations outdated, but archived scenarios remain accessible and reproducible.
- **Retry:** manual retry when permitted and supported; no silent automatic retry or invented completion.
- **Consistency:** both methods must have identical snapshot/feasibility/solver-setting identity before showing an A/B comparison. Document any excluded beneficiaries/products.

### Illustrative view-model contracts (not final API schemas)

```ts
// Frontend adapter types only. All names/types must be reconciled with
// generated OpenAPI before shipping. Do NOT expose these as public API truth.
type PlanningContext = {
  scenarioId: string;
  snapshotId: string;
  policyVersion: string;
  transferMode: "HUB_ONLY" | "HUB_AND_PANTRY";
  productId: string;
  unit: string;
  localDay: string;          // YYYY-MM-DD in site's timezone
  simulated: true;
  resultTimestamp: string | null;
};

type PlanPresentation = {
  planId: string;
  method: "CLASSICAL_GP" | "EGP_PI_INSPIRED";
  nativeStatus: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN" | "MODEL_INVALID" | null;
  independentlyVerified: boolean;
  stale: boolean;
  goals: Array<{
    siteId: string; productId: string; unit: string;
    target: number; served: number; unmet: number;
    serviceRatio: number | null;
    weightedShortfall: number | null;
    apFlag: boolean | null; rpFlag: boolean | null;
  }>;
};
```

Do not infer that `independentlyVerified: false` means an invalid plan was returned; it could mean not evaluated/pending. Actual server status and verification details need explicit classification, not a single production boolean.

## 12. Honest state inventory and screen behavior

| State | Overview | Data Explorer | Recommendations | Scenario Lab |
| --- | --- | --- | --- | --- |
| Saved verified result | Display frozen risk/route status | Full reproducible projection | Enabled reviewable suggestions | Valid method results with metrics |
| No selected scenario | Network context and prompt, not green success | Latest saved observations with source | Explain need for scenario | Required mode/scope selection |
| Insufficient/missing data | Node labeled unknown | Missingness and no forecast, no fabricated zero | No unsupported plan | Block unsupported solve and explain scope |
| Baseline or proxy forecast | Clear data-quality tag | Provenance/fallback and absent intervals | Qualified rationale | Exact provider choice frozen |
| Queued/running | Stable prior saved data, pending marker | Reads remain usable | Do not present a new successful plan | Show job state; prevent duplicate submits |
| One method failed | No synthetic route for failed method | Keep underlying data | Suggestions only from verified available result | Explicit partial comparison with separate method status |
| Solver `UNKNOWN` / `MODEL_INVALID` | No fake solved allocation | Data still visible | No plan claims | Status and diagnostics; never inspect nonexistent vector |
| Shortage but feasible zero-transfer | Show deficit, no transfer | Residual unmet | Explain no feasible action with current resources | Valid feasible plan with unmet demand |
| Stale plan / 409 conflict | Timestamp + stale signal | Current data vs archived | Review not promoted as current | Explicit create-new-scenario path |
| Worker unavailable / network error | Preserve saved reads | Read-only data still useful | Mark compute unavailable | Explain 503/retry boundary, no fake completion |
| Visitor mode | Read-only saved results | Read-only tables | Saved suggestions only | Inspect saved comparisons; no controls requiring authorization |

**Never conflate:** stock shortage vs solver infeasibility; `FEASIBLE` vs `OPTIMAL`; raw received donations vs future predicted donations; route permission vs shipment feasibility; saved successful plan vs in-flight/pending job; risk label vs calibrated probability; simulated review vs real fulfillment.

## 13. Responsive and accessible UX

### Required viewports for visual acceptance

| Viewport | Behavior |
| --- | --- |
| **1440×900** desktop | Map-dominant Overview with floating inspector; Data Explorer has four aligned KPIs, wide line chart + fixed-width flip panel, full-width site table visible or partially below fold |
| **1280×720** laptop | Preserve map-first composition; Data Explorer keeps 4 KPI row where readable, chart + fixed-width flip slot and table below; scrolling is acceptable for lower analytics, never caused by flips |
| **390×844** mobile | Overview uses map plus accessible selected-site sheet/list; Data Explorer stacks summary cards and chart/flip card/table predictably, with fixed card height within each mobile slot, tap-to-flip controls, reduced motion, and intentional horizontal scroll for Site Performance |

### Accessibility requirements

- All SVG nodes/routes interactive through buttons or keyboard-focusable elements with accessible site/route names, not hover-only circles. Provide parallel site list and route table.
- Charts have textual summary and accessible tabular alternate; all date/product/unit labels explicit.
- Radix/shadcn dialogs and sheets manage focus, restore it to trigger, avoid trapping focus in nonmodal areas.
- Visible focus outline, distinct selected/hover/error states, appropriate contrast, minimum usable touch targets and readable mobile labels.
- Status uses icon/text/pattern + color; avoid green/orange/red-only encoding and ensure screen-reader announcements for completed job outcome.
- Keyboard can navigate shell, filters, site selection, forecast details, recommendations, scenario editor, final comparison and audit.
- `prefers-reduced-motion`: disable streaming routes, parallax, camera movement, looping reveal; preserve all content and interpretation.

## 14. Suggested implementation sequence (not a change to V5 backend gates)

1. **Design tokens + shell**: update agreed neutral styling, responsive nav, status/provenance vocabulary and route skeleton; source packages stay in existing lock.
2. **Atlas prototype**: Collage 1 map-centric SVG/CSS backdrop, at least six beneficiaries/one hub, selected-marker popover, status legend, map controls and keyboard site list. Keep a renderer boundary for future Google Maps integration; mock geography must be labeled illustrative.
3. **Data Explorer**: implement the locked Collage 2 4-card KPI row, independently flipping Risk card, Network Demand Forecast line graph, independently flipping Region/Item analytics card in its fixed slot, and full-width Site Performance table. Retain Seven-Day Pulse, Operations Board and site drilldown as additional subviews. Validate missing households/regions/waste records without fake values.
4. **Scenario Lab structure**: method-pair composition, frozen context banner, draft/committed editor, method status states and AP/RP evidence placeholders that say unavailable until backend produces them.
5. **Recommendations evaluation**: prototype two/three alternate visual patterns with the same saved data; choose only after manager comprehension check; no Resource River default.
6. **Integrate finalized APIs**: typed FastAPI/OpenAPI → Next same-origin proxy, auth, durable jobs, saved plan projections, staleness and presenter rights. **Do not run inference or solver in frontend.**
7. **Test truthfulness and QA**: full 6×2 research fixture, both modes/methods, no hallucinated metrics, zero demand/stock, partial failures, keyboard, mobile, contrast, reduced motion and the complete demo journey.

The ordering is a **frontend work plan**; backend mathematical/research gates, unresolved policy contracts, paused procurement and runtime restrictions take precedence. A pretty static demo is not accepted as an implemented allocation engine.

## 15. Screen-specific acceptance checklist

### Overview / Network Atlas

- [ ] Follows Collage 1 map-centric composition: atmospheric neutral map surface, site pins, floating legend, zoom/fit, and selected-site popover; no giant KPI grid.
- [ ] Shows six beneficiaries + one or two hubs with stable 2D positions and explicit simulation/illustrative-geography label.
- [ ] Product and day navigation display site-specific units and correct saved snapshot context.
- [ ] Site selection works via pointer and keyboard; side inspector shows first deficit and uncertainty truthfully.
- [ ] Potential routes and actual *proposed plan* edges are visually distinct; mode respected.
- [ ] No dense tables or a competing four-card KPI row on Overview; the four selected cards appear on Data Explorer.
- [ ] `NetworkMap` abstraction keeps future Google Maps API integration possible without adding an unapproved runtime or fabricating coordinates, addresses, routes or travel time.
- [ ] Every animation degrades to an understandable static presentation with reduced motion.

### Data Explorer

- [ ] Default composition matches Collage 2: Households Served, Predicted Fill Rate, flip Risk card and Food Waste Rate in one four-card row; Network Demand Forecast line chart and beside it one fixed-size flip card; Site Performance table underneath.
- [ ] Risk KPI flips independently **Items at Risk ↔ Sites at Risk**, preserving all surrounding card geometry and selected filters.
- [ ] Analytics panel flips independently **Fill Rate by Region ↔ Item Risk Overview** without chart/table reflow, remount or layout shift.
- [ ] Both flips use accessible visible control, hidden-face inertness, reasonable focus management and reduced-motion static alternative.
- [ ] Households Served, fill rate and waste have explicit source/basis and denominator where applicable; unavailable fields are never fabricated.
- [ ] Forecast chart is a persistent line chart with properly distinguished historical/forecast segments, seven-day dates, units, provider and valid bands only.
- [ ] Persistent Site Performance table exposes site-specific fill/risks and grounded household/region fields; all six beneficiary sites are included.
- [ ] Seven distinct future local days displayed in the secondary Seven-Day Pulse; missing source vs observed zero differentiated.
- [ ] Demand and donation outlooks both represented; confirmed arrivals not confused with predictions.
- [ ] Operations Board covers all beneficiaries and both separately unit-labeled products.
- [ ] Exact lot eligibility, FEFO/expiry, reserve, service/unmet and provider provenance are accessible.
- [ ] Every visual chart has a labeled table and fallback/limitations if intervals unavailable.

### Recommendations

- [ ] **Collage 2 Recommendations selected:** global sidebar, Action Plan / Site Recommendations / Network Optimization / Impact & Fairness tabs, queue and contextual Impact Preview.
- [ ] Proposed actions derive from saved independently validated plans, not arbitrary generated recommendations.
- [ ] Source, destination, product, quantity, dates, donor protection and residual need are inspectable.
- [ ] No unsupported per-transfer numeric benefit, vendor quote, priority score or autonomous purchase claim.
- [ ] Simulated review has no real stock/payment/shipping effect; supplier draft scope is transparently paused until built.
- [ ] No `Implement Selected`, `Take Action` or other operational execution CTA in P0; use `Inspect`, `Compare`, `Mark reviewed — simulation` appropriately.
- [ ] Selected Impact Preview states whether numbers represent whole-plan/site effects, not unapproved single-transfer attribution.

### Scenario Lab

- [ ] **Collage 1 numbered setup** steps visible and accessible; **Collage 2** Scenario Results, Projected Fill Rate by Site, Comparison, and Key Trade-offs panels present.
- [ ] Mode required with no default; both modes and both methods supported by eventual backend.
- [ ] Constraint UI is derived only from accepted, validated V5 controls; hard lot/expiry/donor/transport rules not adjustable as preference sliders.
- [ ] No generic transfer `Total Budget`, unsupported `Max Distance`, hidden `Priority Regions`, or four arbitrary goal-weight sliders; supplier draft budget remains separate and paused.
- [ ] `Projected Fill Rate by Site` includes all six beneficiaries, explicit selected product/unit and 7-day window; zero-target is `N/A`.
- [ ] Scenario Results and Key Trade-offs are tied to saved verified outcomes, including gains/losses, residual shortfalls and AP/RP/solver explanations.
- [ ] Method pair uses identical immutable snapshot/candidate feasible region; archived comparison stays reproducible.
- [ ] Draft changes are visibly unapplied; new computation requires saved new scenario and explicit submission.
- [ ] Per-site/product targets, served, unmet, service ratios, AP/RP, vulnerability sources, method status and objective limitations accessible.
- [ ] Missing or failed method is not silently replaced with a successful result or fake animation.
- [ ] Real research demonstration proves a method-dependent feasible allocation difference with independent evidence.

### Shared navigation consistency (final visual lock)

- [ ] Top navigation is visually and structurally the **same as Collage 2** across all four main pages: search left, seven-day selector right, compact utility icons.
- [ ] **No avatar/profile icon in top navigation** and **no duplicate account identity**. An authenticated presenter's identity, if available, appears once in the lower left sidebar.
- [ ] Left sidebar matches Collage 2's ordering, branding, active highlight and Settings/account footer; no extra sidebars or duplicated header controls on individual pages.
- [ ] Overview preserves Collage 1's map, risk legend, overlay card and selected-site inspector **within** the Collage 2 navigation shell.
- [ ] Mockup numerics and invented user identities are not copied into the live app as factual data or accounts.

### Trust, security, and release

- [ ] Source DOI/date and bounded methodological claims visible; all example operational/vulnerability data labeled simulated.
- [ ] Presenter actions server-protected, visitor results read-only, dedicated demo reset isolated.
- [ ] No frontend secrets, direct browser FastAPI calls, implicit GET computation or incompatible handwritten DTOs.
- [ ] Screenshot and keyboard/reduced-motion review at 1440×900, 1280×720 and 390×844.
- [ ] End-to-end demo from saved data through forecasts, shortage, two-method comparison, disruption and simulated review/reset works against real backend outputs before claiming completion.

## 16. Suggested 90-second demo narrative

| Time | View / action | Message |
| --- | --- | --- |
| 0–10s | Overview: select at-risk pantry in Network Atlas | The network has a dated, explainable projected shortage |
| 10–25s | Jump to saved Scenario Lab comparison | On the same resources, vulnerability-aware allocation can change who gets served |
| 25–40s | Inspect one highlighted institution/product difference | Show requested, served, unmet and AP/RP trade-off, not a generic 'AI fairness' badge |
| 40–55s | Data Explorer: Network Demand Forecast line chart, flip from Region to Item Risk or Items to Sites, open Site Performance detail | Predicted shortages, operational risk and underlying evidence are visible without rearranging the dashboard |
| 55–70s | Recommendations: inspect reviewable corrective action | Suggested intervention is feasible/simulated; remaining need and limits remain explicit |
| 70–85s | Scenario Lab: introduce one disruption; submit new frozen comparison (pre-rehearsed live path) | Explain recomputation, versioning and changed allocations, or show truthful queued state |
| 85–90s | Methodology/provenance and limitations | Name research source, adaptation boundaries and simulation-only status |

**V5 demo constraint:** the research method/date and a real difference should be shown **within approximately the first 30 seconds**, where event length permits. If a live compute step exceeds the demo, disclose saved/replayed results rather than pretending real-time completion.

## 17. Open design decisions and change-control log

| Question | Present answer | Next decision required |
| --- | --- | --- |
| Recommendation central visualization | **SELECTED (2026-10-25): Collage 2 Action Plan with reviewable queue + contextual Impact Preview**; Resource River rejected as primary | Fine-tune exact list density, copy and responsive inspector placement after review; core pattern no longer open |
| Exact neutral theme/token approval | Proposed palette, visually consistent with V5/ART-DIRECTION | Human visual/contrast acceptance on real screens |
| Atlas map presentation | **Selected:** Collage 1 cartographic-style map-first canvas with pins, popover, legend and controls; schematic SVG until valid geodata exists | Approve true basemap adapter, coordinates/provider, mobile detail behavior later; no fake geolocation |
| Severity labels | Use documented deficit facts first | Agree display-only legend without inventing algorithmic priority |
| Policy sliders/threshold controls | Only validated server parameters; no preset unapproved values | Backend research OPEN-23/24 and API schema closure |
| Per-transfer quantitative benefit | **Do not fabricate** | V5 OPEN-02 selects counterfactual or plan/site-level approach |
| Supplier proposal UX | Scoped but paused; mark as unavailable | Explicit OPEN-26–28 resolution/resumption |
| Future Google Maps integration | **Forward-compatible interface only**, not an approved/implemented service | Future integration decision for provider, API key protection, location provenance, costs, terms, a11y and fallback |
| Production 3D / Three.js | Still **not selected** (prototype only in `/design-lab`) | Explicit later architecture decision if ever needed |
| Data Explorer layout | **Locked 2026-10-25:** 4 KPIs; main line chart; side flip card; persistent Site Performance table | Implement responsive geometry and verify with visual QA |
| Risk KPI flip faces | **Locked:** Items at Risk ↔ Sites at Risk | Agree domain count criteria and dataset support; no fake counts |
| Analytics flip faces | **Locked:** Fill Rate by Region ↔ Item Risk Overview | Ground region grouping and shortage evidence; missing-data fallback |
| Card flip behavior | **Locked:** independently controlled, fixed slot/height, reduced-motion instant swap | Tune animation timing only after keyboard/mobile tests |
| Representative component-source choices | shadcn/Radix + audited Watermelon/Kokonut copy | Select exact components and verify licenses/behavior before inclusion |
| Sidebar layout | **SELECTED:** Collage 2 sidebar for all main tabs | Finalize compact/mobile behavior and placement of Methodology/Audit utility link |
| Guided Scenario Lab flow | **SELECTED:** numbered Collage 1 wizard with safe accepted controls only | OPEN-19/21–25/29/31 must close before enabling dependent writes/sliders |
| Scenario Lab results | **SELECTED:** Collage 2 result cards, projected fill by site, comparison and key trade-offs | Align exact data mappings, denominators, grouping, statuses and source identities to generated API contracts |

### Dated design decisions (2026-10-25)

| Decision | Newly confirmed preference | Scope of change |
| --- | --- | --- |
| DD-2026-10-25-01 | Overview adopts the **Network Atlas of Collage 1**, including map-centric aesthetics and future Google Maps readiness | Overview only; no current Google Maps/real geography approval |
| DD-2026-10-25-02 | Data Explorer retains **Households Served** from Collage 1, and **Predicted Fill Rate**, **Food Waste Rate**, **Network Demand Forecast** line chart and **Site Performance** from Collage 2 | Data Explorer only |
| DD-2026-10-25-03 | Third KPI slot **flips Items at Risk ↔ Sites at Risk** | Same card footprint; independent state |
| DD-2026-10-25-04 | Right analytical card **flips Fill Rate by Region ↔ Item Risk Overview** | Same slot; other components never shift |
| DD-2026-10-25-05 | Both flip controls use a **card flip animation** with accessible reduced-motion alternative | Motion behavior; no product/solver policy adoption |
| DD-2026-10-25-06 | Recommendations, Scenario Lab, Methodology/Audit choices remained unchanged **in revision 1.1 only** | Superseded for Recommendations and Scenario Lab by DD-07–10 below; Methodology/Audit remains unchanged |
| DD-2026-10-25-07 | **Collage 2 desktop left navigation** retained for main tabs | Consistent sidebar shell and active-tab highlight |
| DD-2026-10-25-08 | **Collage 2 Recommendations** adopted: in-page tabs, Action Plan list, and contextual Impact Preview | Replaces visual-pattern OPEN; no live execution or unapproved impact metrics |
| DD-2026-10-25-09 | **Collage 1 Scenario Lab numbered setup steps** retained | Guided UX only; no adoption of the mockup’s arbitrary sliders, defaults, transport budget or map distance |
| DD-2026-10-25-10 | **Collage 2 Scenario Results, Comparison, Key Trade-offs and Projected Fill Rate by Site** retained | Verified V5 output panels; definitions and outcome identity mandated |
| DD-2026-10-25-11 | **Freeze exact Collage 2 shared navigation chrome** on all tabs: search + horizon + utility icons above; branding/four nav links/Settings plus sole account identity in sidebar; **no top-right profile avatar** | Reverses unintended duplicate profile in later isolated image render; do not alter page-specific core layouts |

**Reference mockups:** **Navigation and four-tab composition are anchored to the user-confirmed four-panel collage on October 25, 2026** (`image(20261025-052223).png`, and the refined four-panel render `pantrypulse_food_bank_dashboard_mockup.png`); the shared navigation has **no top-right profile avatar**. “Collage 1” = first generated four-tab collage (`a_clean_modern_ui_mockup_collage_of_a_dashboard_a.png`); “Collage 2” = second generated collage (`a_clean_modern_dashboard_ui_mockup_collage_image.png`). These are style references only; their fabricated map data, location counts, household totals, regional names, and purported outcomes are **not implementation data or approved metrics**.

### Design changes vs product authority

This blueprint records the user's explicit design preferences, but the **repository V5 specification remains authoritative for product, backend and accepted-stack behavior**. Where this companion changes the recommended composition (e.g., Overview centered on Network Atlas instead of the older timeline-first art-direction proposal), the team should update the design guidance / relevant decision record deliberately, not assume conflicting older prose silently disappeared. No existing V5 source files were modified by creating this standalone Markdown document.

## 18. References

### Primary project references

- [PantryPulse V5 project specification (authoritative)](https://github.com/gbw30/PantryPulse/blob/main/docs/pantrypulse/SPEC-V5.md): particularly §§2, 8–14, 16–20.
- [Existing PantryPulse art direction](https://github.com/gbw30/PantryPulse/blob/main/docs/pantrypulse/ART-DIRECTION.md): tokens, density, accessibility, motion, screenshot acceptance.
- [ADR 0002 — accepted frontend stack](https://github.com/gbw30/PantryPulse/blob/main/docs/architecture/0002-ui-stack.md).
- [ADR 0004 — Three.js allowed only in isolated design lab](https://github.com/gbw30/PantryPulse/blob/main/docs/architecture/0004-design-lab-3d-exception.md).
- [Frontend package manifest](https://github.com/gbw30/PantryPulse/blob/main/apps/web/package.json).
- [V5 Google Doc reading copy](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit).

### Library/documentation references

- [shadcn/ui — components and data table](https://ui.shadcn.com/docs/components/data-table) and [charts](https://ui.shadcn.com/docs/components/chart).
- [Motion — layout animation](https://motion.dev/docs/react-layout-animations) and [reduced motion](https://motion.dev/docs/react-use-reduced-motion).
- [Watermelon UI component and dashboard catalog](https://ui.watermelon.sh/home).
- [Kokonut UI component catalog](https://kokonutui.com/).
- [Aceternity UI (visual reference, not approved dependency)](https://ui.aceternity.com/components).
- [Three.js (isolated lab only)](https://github.com/mrdoob/three.js/).
- [Variant](https://variant.com/), [Godly](https://godly.design/), [Refero](https://styles.refero.design/?q=animated+data+dashboard): inspiration; do not infer runtime approval.

---

**Bottom line:** All four main tabs use the **identical Collage 2 top navigation and left sidebar**, with the account identity only in the sidebar footer, **never duplicated in the top bar**. The Overview uses **Collage 1’s cartographic-style Network Atlas**, architected for potential future Google Maps. Data Explorer uses **Collage 2’s stable dashboard**: Households Served, Predicted Fill Rate, a flip-enabled Items/Sites at Risk KPI, Food Waste Rate, a persistent Network Demand Forecast line graph, a fixed-slot Fill Rate by Region/Item Risk Overview flip panel, and a persistent Site Performance table. Seven-Day Pulse and Operations Board remain deeper explorer views. **Recommendations uses the selected Collage 2 Action Plan/queue plus Impact Preview** (not Resource River), and **Scenario Lab combines the Collage 1 numbered guide with Collage 2 results, Projected Fill Rate by Site, Comparison and Key Trade-offs**, constrained by V5's immutable scenarios and verified allocation policies. All results remain accurately labeled, provenance-backed, simulation-only and accessible.
