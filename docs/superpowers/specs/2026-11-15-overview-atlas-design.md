# Overview and atlas redesign: design

**Status:** draft for Gabriel's approval (2026-11-16; decisions through §4.13). **Base:** v1-local `51dab11` (W5 closed).
**Decided by:** Gabriel, in a brainstorming session with browser mockups; the mockups are in [2026-11-15-overview-atlas/](2026-11-15-overview-atlas/), and the look prototypes in its `ui-directions/` folder (`LedgerFresh.dc.html` is the chosen one).
**Lands:** before the W6 release candidate is chosen (release freeze, CLAUDE.md).

Items marked **(lead call)** are the orchestrator's choices, not Gabriel's. Check them while reading.

## 1. Intent and why

The W5 Overview shows too much at once:
- a small schematic dot map;
- a long ranking of ~21 cards, each with several lines of text;
- a per-product 7-day table for every product in the inspector.

At 1280×720 the Retail map shrank to about 225×127 px, and about 20 markers piled up (ux-critic, W5).

Gabriel's direction: too many options and too much information at once cause decision paralysis. The Overview becomes a **familiar maps-app screen**: a sidebar list beside a large map, where the user can move from one location to another or move around the map.

**Success:** a first-time coordinator opening their own imported network can, without help:
1. see which sites need attention this week;
2. open the most urgent one and read what is wrong, how much and when;
3. reach the suggested action.

This keeps ART-DIRECTION's ten-second goal of at-risk site, first deficit and action. It's a usability goal to check in review, not a measured result.

## 2. Goals, non-goals, anti-goals

**Goals**
- A Google Maps–style layout: a sidebar list on the left and a large, pannable and zoomable map on the right.
- Less to read at once: grouped, collapsed lists, one idea per row, and detail on demand.
- Jump from site to site (list, marker, Prev/Next), or explore the map freely.
- Designed and polished for desktop, at 1440×900 and 1280×720.

**Non-goals**
- A phone-optimized layout. At 390 px the screen only has to work: a simple stack, list then map. It still has to pass V1-A20's keyboard, axe and reduced-motion checks.
- Road-following routes.
- Online map tiles, or any map service or key.
- Changes to the danger score, its bands, or the API, unless §6 says otherwise.

**Anti-goals** (this fails even if it "works" when)
- Markers overlap so that sites can't be told apart or clicked.
- Anything moves continuously by default.
- Quantities are summed across products, or shown without their unit.
- Color alone carries the danger band.
- The map is the only way to reach a site: the list is the accessible alternative (V1-A13).

## 3. Constraints (binding)

- **V1-SPEC §6.6:**
  - locations are placed by real coordinates;
  - the basemap needs no paid key, and any provider must be keyless and policy-compliant;
  - the danger band is encoded by color *and* shape, with a text label and an accessible table;
  - selecting a location opens its per-product 7-day projection.
- **Egress (V1-A03/A04):** the only allowed outbound destinations are the Census geocoder and Google Routes with a key. So the basemap is **bundled data**, served by our own app.
- **V1-A13:** the ranking matches an independent calculation, never sums units across products, and has a text/table alternative.
- **V1-A20:** keyboard, axe and reduced-motion checks pass at 1440×900, 1280×720 and 390×844.
- **ART-DIRECTION**, as amended by §4.10:
  - the calm operations-desk intent;
  - the motion contract: purposeful and finite, with reduced motion respected;
  - risk semantics stay stable across views; shape and text always accompany color.
- **Product truth (CLAUDE.md):**
  - forecasts are labeled projections;
  - the sales basis label stays;
  - quantiles appear only when the provider produced them;
  - no future leakage, and missing demand is never shown as zero.
- **Existing decision kept:** [supply-link pause control](../../plans/v1/decisions/W5-change-requests.md) (WCAG 2.2.2). Any always-on animation keeps a fixed-name "Pause link animation" toggle with `aria-pressed`, saved per browser.

## 4. Decisions (Gabriel, 2026-11-15)

### 4.1 Layout: a sidebar list beside a big map (option C)
- The screen is a slim top bar, then a sidebar list on the left and a large map filling the rest.
- Picking a site, either a list row or a marker, flies the map to it and highlights it. Other markers stay visible but fade **(lead call)**.

### 4.2 Picking a site: the site replaces the list (C1, Google Maps style)
- The sidebar slides from the list to that site's panel.
- **← Back to list** returns to the list at the same scroll position, with focus on the row you came from **(lead call)**.
- **‹ Prev / Next ›** step through the sites in the current sort order without returning to the list, and the map follows **(lead call)**.
- **Escape** returns to the list and restores focus. This is the existing W5 rule.

### 4.3 The site panel: story + small chart (P3)
From top to bottom:
1. ← Back to list.
2. The site name, and its danger band as shape plus text.
3. **One sentence:** the driving product, its quantity in its own unit, the problem (short / expiring unsold) and the date. Example: "595 lbs of BEEF-GR will expire unsold by Nov 15."
4. **A 7-day bar chart for the driving product:**
   - per-day projected unmet (or expiring unsold), with day labels and the unit;
   - a "show as table" alternative;
   - uncertainty only when the provider produced it;
   - the sales-basis label when the basis is `sales`.
5. **See what to do →**
6. The other at-risk products, one line each, in their own units **(lead call: kept from P2 so a second problem at the site isn't hidden)**.
7. "N more products" collapsed. **Site details** opens today's full per-product projection table **(lead call)**.
8. ‹ Prev · *i of N* · Next ›.

The Retail DC note ("A DC has no sales; stock it doesn't send out counts as expiring") stays on DC panels.

### 4.4 List rows: name + one-line subtitle (L2), sorted by danger score
- **Row line 1:** the band shape and site name.
- **Row line 2:** "<driving product> · <qty> <unit> <short|expiring> <from|by> <date>". Example: "ICECRM · 18 each short from Nov 15".
- The score itself isn't printed on the row; it's shown in the site panel **(lead call)**.
- **Groups:**
  - **Needs attention** = band high, open by default.
  - **Watch** = medium, collapsed with a count.
  - **OK** = low, collapsed with a count.
  - **Not ranked** = sites the ranking gives no row (see §4.12), collapsed, at the bottom.

  These are today's bands (`services/danger/ranking.py:37-44`: high ≥ 0.50, medium ≥ 0.20) **(lead call: group = band)**.
- **Default sort:** danger score, highest first, within each group. That's today's ranking order.
- A "Sort ▾" control also offers **Soonest problem** and **Name A–Z**, remembered per browser **(lead call)**.
- A **search box** at the top filters the list and the map together, by site or product name **(lead call)**.
- Sites the map can't place (no coordinates) stay in the list with a "not on the map" note **(lead call; today's "Not on the map" list folds into the rows)**.

### 4.5 Supply routes: R3 by default, R1 in Settings
- **Default:** no route lines until a site is picked. Then that site's routes appear, static, labeled with distance and travel days.
- **Layers control** on the map, the Google Maps pattern: "All supply routes" draws the whole network, static.
- **R1 (today's always-on animated flow) stays available**, as an option in the Settings menu ("Animate all supply routes"), saved per browser. Today that flow exists only on the legacy fixture atlas, which §4.11 removes, so the lane re-applies it (`supply-flow.css`) to the new map's route lines. When it's on, the "Pause link animation" control and the `v1-motion.spec.ts` exemption apply as in W5.

### 4.6 Frame: summary at the top of the list (T3), Run forecast in the top bar (A)
- **Top bar:** network picker · "Forecast <date> · next 7 days" · **[Run forecast]**, always visible. No large page title or description line. The brand and the page menu sit in the app's top menu (§4.10).
- **Signed out (§4.13):** the same spot shows a "Sign in to run a forecast" link.
- **While running:** "Forecasting…", the button is disabled against double submission, and the list and map refresh when it finishes. This keeps today's job behavior.
- **No forecast yet**, as on a fresh import: the sidebar shows "No forecast yet" with a large Run forecast button.
- **The sidebar opens with one line:** "3 sites need attention · next 7 days".
- The "Sample data — fictional" pill stays for sample networks.

### 4.7 Basemap: land outline + faint county lines + a few city names (B2)
- Bundled, public-domain US boundary data (e.g. US Census cartographic boundaries via a TopoJSON package), with major city names (e.g. Natural Earth populated places) that appear by zoom level.
- No roads.
- Labels must not cover markers; markers win.
- **Exact sources, licenses and the file size are the builder's to propose.** Any new npm dependency changes the lockfile, which is lead-owned, so it comes back as a CR.

### 4.8 Markers and crowding
- Marker shapes per band are unchanged: the high diamond, the medium triangle and the low circle. The square keeps today's meaning, **not ranked** **(lead call)**. A DC or hub that is ranked shows its band shape with a small "DC" or "Hub" text label.
- **Clustering (lead call):** when zoomed out, markers closer than a pixel threshold merge into a numbered bubble outlined in the worst band's shape and color. It splits as you zoom in, or on click. Acceptance: at every default view, no two individual markers overlap by more than half their size.
- Initial view: fit all placed sites with padding. A **Fit all** button returns to it.
- The map supports drag, wheel/pinch zoom, ＋/− buttons, and keyboard pan/zoom when focused.

### 4.9 Desktop first
1440×900 and 1280×720 are the designed sizes. At 390×844, a plain stack (top bar, then list, then map at a fixed height) that passes the V1-A20 checks.

### 4.10 Look: Pantry Ledger with Market Fresh accents (Gabriel, 2026-11-16)
Chosen from five clickable directions covering all seven pages (`ui-directions/`).
- **From Pantry Ledger:**
  - paper tones (`#f3f1ea` ground, `#fbfaf6` surface), navy ink;
  - IBM Plex Serif for page titles, site names, the summary and the story sentence; IBM Plex Sans for everything else;
  - ruled lines instead of boxed cards;
  - **the app menu runs across the top**, not down the left. So the Overview has one left column, its own list.
- **From Market Fresh** *(the lead's reading of "4's accents"; Gabriel to confirm on the prototype)*:
  - a leaf-green action color (`#2c6a3c`) in place of teal;
  - sage tint (`#e6efdb`) for hover, the network picker and neutral badges;
  - pill-shaped buttons and badges;
  - tomato red (`#b03a26`) for danger; green land on the map.
- **Rule (lead call):** green never means "OK" by itself. OK is a neutral badge with its text.
- **Scope:** this amends ART-DIRECTION (colors, the serif, the top menu), so it is app-wide: tokens, fonts and the shell change for every page. Fonts are self-hosted (no runtime font request; egress V1-A03). The hex values above are the prototype's; the builder checks contrast (4.5:1 text) and may adjust shades.
- **Staging (lead call):** (1) tokens, fonts and the top-menu shell for all pages, with every existing e2e and axe check re-run; (2) the Overview rebuild. Both land before the W6 candidate.

### 4.11 One Overview: the legacy fixture atlas is removed (Gabriel, 2026-11-16)
- Today `network-atlas.tsx` renders two Overviews: `DangerRankingSection` for a chosen v1 network, and the fixture atlas (`SchematicMapRenderer`, static fixture) when no network is chosen.
- The fixture atlas is removed. With no network chosen, the Overview shows "Choose or import a network", with the sample networks one click away.
- Its tests are removed or rewritten for the new screen; `v1-motion.spec.ts` follows the animated-routes option (§4.5).

### 4.12 Sites that can't be ranked (Gabriel, 2026-11-16)
- `danger_ranking` gives no row to a location it can't score (unknown is never zero). Usually a hub with no demand of its own, or a site with no forecast.
- They go in a fourth list group, **Not ranked**, collapsed, at the bottom. Each row says why ("Hub: no demand of its own" / "No forecast yet").
- They can be opened; the panel shows the reason in place of the story and chart, and "Site details" still works. Prev/Next reach them after the ranked sites **(lead call)**.
- The summary mentions them only when a non-hub site has no forecast ("… · 2 sites have no forecast").

### 4.13 Who sees Run forecast (Gabriel, 2026-11-16)
- Signed in: the button, as in §4.6.
- Signed out: a "Sign in to run a forecast" link in the same spot, and in the "No forecast yet" state. No disabled button.

## 5. What's left to the builder

- The map rendering approach:
  - SVG with d3-geo (or similar) plus our own pan/zoom, or a vector map library that renders bundled data with no tile server;
  - either way, no network requests outside our own origin.
- The projection, clustering algorithm and thresholds, label placement, and zoom-level rules.
- Motion: the fly-to and panel slide, within ART-DIRECTION's 160–220 ms, and immediate under reduced motion.
- Component structure: reuse `danger-ranking`, `site-inspector`, `location-map`, `atlas-motion` and `layout-store` where sensible; `schematic-map` and the static fixture go with §4.11 unless something still needs them. The W5 resizable panel grips may go away.

## 6. Lead calls to check, and what stays open

1. **"See what to do →" (lead call).** No endpoint lists comparisons, and Decisions has no site filter; both would be API changes. For v1 the link opens Recommendations for the comparison the app last opened in this browser, if there is one; otherwise it opens Scenario Lab with "Run a comparison to get suggested transfers". A per-site filter is recorded as a post-v1 item. Gabriel can overturn this; it would add a contract CR.
2. **Uncertainty on the chart (lead call).** `ProductProjection` carries no quantiles, so the chart shows none. The rule "only when the provider produced it" stays for a later contract change.
3. **No API or contract change is planned.** If planning finds the list subtitle needs a field `DangerRow` lacks, it comes back as a lead CR.
4. **To confirm on the prototype:** the reading of "4's accents" in §4.10.

## 7. Acceptance (to become tests in the plan)

- The layout matches §4.1–4.13 at 1440×900 and 1280×720 (screenshots and a ux-critic pass).
- Every page uses the §4.10 tokens, fonts and top menu; no font or other request leaves the app's origin.
- With no network chosen, the Overview shows the choose-or-import state; the fixture atlas is gone.
- Unranked sites appear under "Not ranked" with a reason and are never shown as OK.
- Signed out, the Run forecast spot shows the sign-in link.
- At the default view of both samples and a 100-site import, no two individual markers overlap by more than half their size, and every site is reachable from the list.
- Keyboard:
  - Tab reaches the search, sort, groups, rows, map controls and Layers;
  - Enter on a row opens its panel, and Prev/Next works;
  - Escape returns to the list with focus restored.
- Axe passes at all three sizes.
- Under reduced motion there's no fly animation; the views switch instantly.
- No request leaves the app's origin while using the Overview (the egress journey in W6).
- V1-A13 still holds: the ranking order, no cross-unit sums, and the list as the text alternative.
- With the default settings no animation runs. With "Animate all supply routes" on, the pause control works as in W5.
