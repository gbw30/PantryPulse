# Wave 5a — lane `w5a-web`: the new look and the Overview redesign

> **For agentic workers:** the lead dispatches one `frontend-engineer` builder per task (superpowers:subagent-driven-development), in order. Steps use checkbox (`- [ ]`) syntax. A task's builder sees this file, the spec and the lane prompt.

**Goal:** every page wears the "Pantry Ledger with Market Fresh accents" look, and the Overview becomes a maps-app screen: a site list beside a large bundled map, with a story-plus-chart panel per site.

**Architecture:** two stages on one lane branch, each its own PR.
1. **Stage 1 (look):** design tokens, fonts and the shell change app-wide; the fixture atlas is removed.
2. **Stage 2 (Overview):** pure model functions (list rows, story, clustering, projection) under unit tests, then the map, list, panel and frame components over the existing `networkApi` calls. No API or contract change.

**Tech stack:** Next.js 16, React 19, Tailwind 4 tokens in `apps/web/src/app/globals.css`, `motion` 14.6, `recharts` 3.10, plus `d3-geo`, `topojson-client` and `us-atlas` (added by the lead in W5A-L01). Vitest unit tests, Playwright e2e (mocked by default; connected with `PP_RUN_CONNECTED=1`).

**Spec:** [docs/superpowers/specs/2026-11-15-overview-atlas-design.md](../../superpowers/specs/2026-11-15-overview-atlas-design.md), approved by Gabriel on 2026-11-16. Read §4 and §7 before any task. The clickable look reference is `docs/superpowers/specs/2026-11-15-overview-atlas/ui-directions/LedgerFresh.dc.html` (its `<style>` block has the values).

**Base:** `v1-local` `51dab11` plus the design and plan commits on `lane/w5a-web`. **Mode:** B. Same rules as wave 1 ([ORCHESTRATION.md §8](ORCHESTRATION.md#8-rules-every-lane-in-every-wave)).

## Global Constraints

- **No request leaves the app's origin** (V1-A03). Fonts come through `next/font/google` (downloaded at build, served by us), as in `app/layout.tsx:8-9`. The basemap and city names are bundled files.
- **Contracts are frozen.** Use `Schema["DangerRanking"]`, `["DangerRow"]`, `["LocationList"]`, `["LocationSummary"]`, `["LocationProjection"]`, `["ProductProjection"]`, `["RouteList"]`, `["RouteEntry"]` from `packages/contracts` through `lib/network-api.ts`. A missing field is a CR, not a workaround.
- **Lead-only:** `package.json`, lockfiles, `packages/contracts`, `apps/api`, `.github/`, `docs/pantrypulse/ART-DIRECTION.md`.
- **Product truth:** quantities keep their unit and are never summed across products; a null day or a null `first_deficit_date` is never shown as 0; the `sales` basis label stays; forecasts are called projections.
- **Band = shape + text + color**, never color alone. Green never means "OK" by itself.
- **Motion:** finite, 160–220 ms for panel changes, instant under `prefers-reduced-motion`. Nothing loops unless "Animate all supply routes" is on, and then "Pause link animation" (fixed name, `aria-pressed`) is shown.
- **Names tests rely on stay:** `<nav aria-label="Primary">`, `<nav aria-label="Reference">`, the "Open navigation" button below 768 px, the "Presenter sign in" control.
- **Light and dark:** both themes get the new tokens; text contrast is at least 4.5:1 (3:1 for 24 px+).
- New e2e titles carry `@V1-A13` or `@V1-A20`; new test modules start with `// covers: V1-Axx`.
- TDD per task: failing test, see it fail for the right reason, implement, see it pass, one commit per task. Two materially different failed fixes: stop and report.

## Review Focus

Each line is pinned by a test in the task named.
1. **About 100 sites in one metro area:** at the default view no two single markers overlap by more than half their size, and every site is reachable from the list (W5A-04, W5A-05).
2. **A site with no coordinates:** it is in the list with "Not on the map"; picking it opens its panel and doesn't move the map (W5A-05, W5A-06).
3. **Nulls:** `first_deficit_date: null` and null day values render as "no shortfall in the next 7 days" or a gap labelled "no data", never 0 (W5A-05, W5A-06).
4. **No forecast run, or a failed ranking request:** the screen shows "No forecast yet" or an error with Retry, not an empty map (W5A-08).
5. **One site, or two sites at the same point:** the projection fit doesn't divide by zero and the map still renders (W5A-04).

## Corrections from the code survey (2026-11-16)

The spec's §4.14 records these; they bind this plan.
- **Signed out (Gabriel):** listing networks needs a signed-in presenter, so a signed-out Overview shows "Sign in to see your networks" with the existing "Presenter sign in" control. This replaces the §4.13 link.
- **"See what to do" (lead call):** v1 actions live at `/decisions?comparison_id=&method=`; `/recommendations` is the pre-v1 screen. The link goes to Decisions for the comparison last opened for this network in this browser, else to `/scenarios` labelled "Plan transfers in Scenario Lab".
- **Run forecast (lead call):** keep `forecast-run.tsx`'s states, labels and `aria-disabled` behavior; only its place changes.
- **The date label (lead call):** runs carry no forecast date, so the bar reads "Forecast run <recorded_at date> · next <n> days", where n is `ProductProjection.dates.length`.
- **Dark theme (lead call):** kept; the new tokens get a dark set.
- **Search (lead call):** matches site names and product codes; v1 has no product names.

---

## Lead — W5A-L01: dependencies, basemap data, art direction · S · before the lane starts

- [x] **Step 1:** add `d3-geo`, `topojson-client`, `us-atlas` and their `@types` to `apps/web/package.json`; update the root lockfile. Record versions and licenses (ISC/BSD) in the status file.
- [x] **Step 2:** add `apps/web/src/data/us-cities.json`: US places with population ≥ 100,000 from Natural Earth populated places (public domain), as `{ name, state, lat, lon, pop }[]`, with `apps/web/src/data/README.md` naming the source, date and filter. Add `scripts/data/build-us-cities.mjs`, which rebuilds it from a downloaded source file.
- [x] **Step 3:** amend `docs/pantrypulse/ART-DIRECTION.md` "Composition and identity" with spec §4.10 (paper tones, leaf-green action, tomato danger, IBM Plex Serif for titles and stories, top menu, pill buttons, ruled sections).
- [x] **Step 4:** `npm run check` in the worktree passes; commit.

## Lane `w5a-web`

**Agent role:** `frontend-engineer`. **Skills:** superpowers:test-driven-development, verification-before-completion, systematic-debugging; `visual-review` for evidence; context7 for `d3-geo` and Tailwind 4 questions.

### Stage 1 — the look (PR 1)

### W5A-01: Tokens, fonts and shared primitives · M · depends on: W5A-L01 · V1-A20

**Files:** modify `apps/web/src/app/globals.css`, `apps/web/src/app/layout.tsx`, `apps/web/src/app/design-lab/layout.tsx`, `apps/web/src/components/ui/{button,badge,card}.tsx`; tests `apps/web/tests/e2e/theme.spec.ts`, `scaffold.spec.ts`, new `apps/web/tests/unit/tokens.test.ts`.

**Produces:** tokens `--pp-action`, `--pp-action-soft`, `--pp-tint`, `--pp-rule`, `--pp-danger-soft`, `--pp-warning-soft`, `--font-serif`; Tailwind utilities `font-serif`, `bg-pp-tint`, `text-pp-action`.

- [ ] **Step 1:** rename `--pp-teal` → `--pp-action` and `--pp-teal-soft` → `--pp-action-soft` everywhere (tokens, `@theme`, class names such as `pp-teal`), with no value change. `npm run check` passes. Commit this mechanical rename alone.
- [ ] **Step 2:** write the failing tests:
  - `tokens.test.ts`: parses `globals.css` and asserts the light values `--pp-canvas: #f3f1ea`, `--pp-surface: #fbfaf6`, `--pp-ink: #1b2a41`, `--pp-ink-muted: #566072`, `--pp-border: #dcd8cb`, `--pp-action: #2c6a3c`, `--pp-tint: #e6efdb`, `--pp-danger: #b03a26`; that every one of those names also has a `.dark` value; and that each text token on its background passes 4.5:1 in both themes (compute contrast in the test).
  - `scaffold.spec.ts`: the `h1` computes a font family matching `/IBM Plex Serif/`; body text still matches `/IBM Plex Sans/`.
  - `theme.spec.ts`: replace the asserted dark background with the new dark canvas value.
- [ ] **Step 3:** implement. Light values are the ones above plus `--pp-rule: var(--pp-ink)`, `--pp-danger-soft: #fbe6e0`, `--pp-warning` text `#7d5a12`, `--pp-warning-soft: #fbeecb`; the medium marker fill is `#d99a1c`. Derive the dark set (same roles; canvas near `#10171f`). Load `IBM_Plex_Serif` (400, 500, 600) as `--font-serif`. Buttons and badges become pills (`rounded-full`); the neutral badge uses `--pp-tint`; `Card` becomes a ruled section (top rule in `--pp-rule`, no box, no shadow). Page `h1`s use the serif at 500.
- [ ] **Step 4:** unit and the two e2e specs pass; `npm run check` passes. Commit.

### W5A-02: The menu moves to the top · M · depends on: W5A-01 · V1-A20

**Files:** create `apps/web/src/components/shell/app-top-nav.tsx`; modify `app-shell.tsx`, `top-bar.tsx`, `app-sidebar.tsx` (kept only as the below-768 px drawer), `network-switcher.tsx`, `presenter-footer.tsx`; tests `v1-shell.spec.ts`, `v1-a11y.spec.ts`, `presenter-session.spec.ts`, `tests/unit/shell-labels.test.tsx`.

**Produces:** `AppTopNav`: at ≥ 768 px one header with two rows. Row 1: brand, `<nav aria-label="Primary">` (the `NAV` array, unchanged), `<nav aria-label="Reference">` ("Methodology & audit"), Settings, the presenter control. Row 2 (the context bar): `NetworkSwitcher`, the data-label pills, the snapshot date, a slot `data-slot="page-actions"` that pages fill through a `PageActions` portal component, and `ThemeToggle`. The current page's menu item has `aria-current="page"` and a 3 px underline in `--pp-action`.

- [ ] **Step 1:** write the failing e2e tests in `v1-shell.spec.ts`:
  - at 1280×720 no element with the sidebar's role is visible, and `nav[aria-label="Primary"]` sits inside `header`;
  - the five primary links and "Methodology & audit" are reachable by Tab in order, and the current one has `aria-current="page"`;
  - at 390×844 "Open navigation" still opens the drawer with the same links, and the page has no horizontal scroll;
  - the main content's left edge is within 40 px of the viewport's left edge at 1280 (no left column).
- [ ] **Step 2:** implement `AppTopNav` and `PageActions`; keep the Sheet drawer below 768 px.
- [ ] **Step 3:** the shell, a11y and presenter specs pass at all three viewports; axe has no violations. Commit.

### W5A-03: One Overview: remove the fixture atlas · M · depends on: W5A-02 · V1-A13, A20

**Files:** modify `components/overview/network-atlas.tsx`, `app/overview/page.tsx`; move `formatUnits` and `pluralize` to `apps/web/src/lib/units.ts` (update the importers: trust-panel, action-card, `scenario-lab/results`, danger-ranking); delete `schematic-map.tsx`, `site-inspector.tsx`, `site-list.tsx`, `selection-card.tsx`, `panel-grip.tsx`, `atlas-geometry.ts`, `atlas-layout.ts`, `layout-store.ts`, `sources.ts`, `static-fixture.ts`, `live-source.ts`, `live-notice.tsx`, `notice-copy.ts`, `demand-outlook-chart.tsx` and their unit tests, once nothing imports them (keep `risk-legend`, `status-glyph`, `forecast-method`, `provenance-pill`, `lib/overview-api`, `supply-flow.css`, `atlas-motion.ts`); rewrite or delete `overview.spec.ts`, `overview-layout.spec.ts`, `overview-live.spec.ts`, the fixture parts of `theme.spec.ts` and `v1-motion.spec.ts`, `scaffold.spec.ts:7`, `data-label.spec.ts:11`.

**Produces:** `NetworkAtlas` renders one of: `OverviewSignedOut`, `OverviewNoNetwork`, or the existing v1 `NetworkOverview` (replaced in stage 2).

- [ ] **Step 1:** write the failing tests:
  - e2e `overview-states.spec.ts` `@V1-A20`: signed out, `/overview` shows the heading "Sign in to see your networks" and a "Presenter sign in" button that opens the sign-in dialog; no map is rendered;
  - signed in with no network chosen: heading "Choose or import a network", the network picker and an "Import data" link to `/import`;
  - unit: `lib/units.test.ts` moves the existing `formatUnits`/`pluralize` cases unchanged.
- [ ] **Step 2:** implement the two states; delete the orphans; run `npx knip` or `tsc` plus a grep to prove no import of a deleted file remains.
- [ ] **Step 3:** unit suite, the rewritten e2e specs and `npm run check` pass. Commit.
- [ ] **Stage 1 gate:** `node scripts/quality/run.cjs full` with `.env.lane` and `PP19_TEST_SCHEMA_ISOLATION=1`; screenshots of every page at 1440×900 and 390×844, light and dark, into `docs/pantrypulse/visual-evidence/v1-w5a-look/`; hand back for the verifier and the ux-critic.

### Stage 2 — the Overview (PR 2)

### W5A-04: The map: basemap, projection, pan/zoom, markers, clusters · L · depends on: W5A-03 · V1-A13, A20

**Files:** create in `apps/web/src/components/overview/`: `map-projection.ts`, `basemap.ts`, `cluster.ts`, `use-pan-zoom.ts`, `atlas-map.tsx`; unit tests `map-projection.test.ts`, `cluster.test.ts`, `use-pan-zoom.test.ts`; replace `location-map.tsx` and its test once `atlas-map` covers it.

**Produces:**
```ts
// map-projection.ts
export type Placed = { locationId: string; x: number; y: number };
export function fitSites(sites: { locationId: string; lat: number; lon: number }[], size: { width: number; height: number }, padding: number): { projection: GeoProjection; placed: Placed[] };
// basemap.ts  (lazy: dynamic import of us-atlas/counties-10m.json and data/us-cities.json)
export function loadBasemap(): Promise<{ states: FeatureCollection; counties: FeatureCollection; cities: City[] }>;
export function citiesForZoom(cities: City[], k: number): City[]; // fewer names when zoomed out
// cluster.ts
export type Band = "high" | "medium" | "low" | null;
export type Cluster = { ids: string[]; x: number; y: number; worst: Band };
export function clusterMarkers(points: { id: string; x: number; y: number; band: Band }[], thresholdPx: number): Cluster[];
// use-pan-zoom.ts
export function usePanZoom(opts: { minK: number; maxK: number }): { transform: { x: number; y: number; k: number }; bind: PointerAndWheelHandlers; zoomBy(f: number): void; fitAll(): void; flyTo(p: { x: number; y: number }, k?: number): void };
// atlas-map.tsx
export function AtlasMap(props: { sites: MapSite[]; selectedId: string | null; onSelect(id: string): void; routes: MapRoute[]; showAllRoutes: boolean; animateRoutes: boolean }): JSX.Element;
```

- [ ] **Step 1:** write the failing unit tests:
  - `fitSites`: three sites land inside the padded box; **one site** and **two sites at the same point** return finite coordinates at the box centre (Review Focus 5);
  - `clusterMarkers`: two points 4 px apart with threshold 16 give one cluster of 2 whose `worst` is the higher band (`high` > `medium` > `low` > `null`); points 40 px apart stay separate; **100 points inside a 60 px square** give clusters such that no two cluster centres are closer than the threshold (Review Focus 1); output order is stable for the same input;
  - `usePanZoom`: `zoomBy` clamps to `[minK, maxK]`; `flyTo` under reduced motion sets the transform in one step.
- [ ] **Step 2:** implement the four modules. Pan/zoom is ours (pointer drag, wheel, pinch), after `app/design-lab/page.tsx:124-170`; no map library draws tiles.
- [ ] **Step 3:** write the failing e2e tests in `atlas-map.spec.ts` `@V1-A20`:
  - the map region has an accessible name and ＋, −, "Fit all" and "Layers" buttons;
  - with the map focused, arrow keys pan and `+`/`-` zoom; "Fit all" restores the first view;
  - a single-site marker is a button named "<site name>, <band label>"; a cluster is a button named "<n> sites, worst: <band label>" and activating it zooms until it splits;
  - no request goes to another origin while the map loads (assert on `page.on("request")`).
- [ ] **Step 4:** implement `AtlasMap`: states outline, county lines, city names by zoom that never overlap a marker (markers win), band shapes (diamond, triangle, circle; square for not ranked; a "DC"/"Hub" text label on ranked hubs), clusters, selected ring. Initial view fits all placed sites.
- [ ] **Step 5:** unit and e2e pass. Commit.

### W5A-05: The list: groups, rows, sort, search · M · depends on: W5A-04 · V1-A13

**Files:** create `components/overview/site-rows.ts`, `site-list-panel.tsx`; tests `site-rows.test.ts`, e2e `atlas-list.spec.ts`.

**Produces:**
```ts
export type SiteGroup = "attention" | "watch" | "ok" | "not_ranked";
export type SiteSort = "danger" | "soonest" | "name";
export type SiteRow = { locationId: string; name: string; group: SiteGroup; band: Band; rank: number | null; subtitle: string; productCode: string | null; firstDate: string | null; onMap: boolean };
export function rowSubtitle(row: Schema["DangerRow"]): string;
export function notRankedReason(loc: Schema["LocationSummary"], hasForecast: boolean): "Hub: no demand of its own" | "No forecast yet" | "Not scored";
export function buildSiteRows(input: { locations: Schema["LocationSummary"][]; ranking: Schema["DangerRow"][] | null; hasForecast: boolean }): SiteRow[];
export function arrangeSites(rows: SiteRow[], opts: { sort: SiteSort; query: string }): Record<SiteGroup, SiteRow[]>;
export function summaryLine(rows: SiteRow[]): { headline: string; note: string | null };
```
Sort memory: localStorage `pp-overview-sort`.

- [ ] **Step 1:** write the failing unit tests:
  - `rowSubtitle`: unmet → `"ICECRM · 18 each short from Nov 15"`; expiry → `"BEEF-GR · 595 lbs expiring by Nov 15"`; **`first_deficit_date: null`** → `"ICECRM · no shortfall in the next 7 days"` (Review Focus 3); quantities go through `formatUnits`;
  - `buildSiteRows`: high → `attention`, medium → `watch`, low → `ok`; a location with no ranking row → `not_ranked` with the reason by role and `hasForecast`; a location with null coordinates has `onMap: false` (Review Focus 2);
  - `arrangeSites`: `danger` keeps `rank` order; `soonest` orders by `firstDate` with nulls last; `name` is A–Z; the query matches site name or product code, case-insensitive, and never matches across groups it empties;
  - `summaryLine`: `"3 sites need attention"`, `"1 site needs attention"`, `"No sites need attention"`; the note is `"2 sites have no forecast"` only when a non-hub site is not ranked for lack of a forecast.
- [ ] **Step 2:** implement `site-rows.ts`.
- [ ] **Step 3:** write the failing e2e tests `@V1-A13`:
  - the list shows the groups "Needs attention" (open), "Watch", "OK" and "Not ranked" (collapsed, each a button with `aria-expanded` and a count);
  - the order of "Needs attention" equals the API's `rank` order;
  - typing a product code in "Search sites or product codes" filters the list and dims non-matching markers;
  - a site without coordinates shows "Not on the map";
  - every location of the network is reachable from the list (expand all groups, count = locations).
- [ ] **Step 4:** implement `SiteListPanel` (summary, search, "Sort" menu, groups, rows as buttons with the band shape and its text for screen readers).
- [ ] **Step 5:** tests pass. Commit.

### W5A-06: The site panel · M · depends on: W5A-05 · V1-A13, A20

**Files:** create `components/overview/site-story.ts`, `site-panel.tsx`, `lib/last-comparison.ts`; modify `components/scenario-lab/results.tsx` and `components/decisions/decisions-view.tsx` (one call each to remember the comparison); reuse `location-inspector.tsx` for "Site details"; tests `site-story.test.ts`, `last-comparison.test.ts`, e2e `atlas-panel.spec.ts`.

**Produces:**
```ts
export function siteStory(row: Schema["DangerRow"], siteName: string): string;
// "595 lbs of BEEF-GR will expire unsold by Nov 15." | "Haines City will be 18 each short of ICECRM from Nov 15."
export function drivingSeries(row: Schema["DangerRow"], projection: Schema["LocationProjection"]): { dates: string[]; values: (number | null)[]; unit: string; kind: "short" | "expiring"; basis: "demand" | "sales" | null } | null;
export function otherAtRisk(row: Schema["DangerRow"], projection: Schema["LocationProjection"]): { productCode: string; line: string }[];
// lib/last-comparison.ts — localStorage key "pantrypulse.last-comparison"
export function rememberComparison(networkId: string, c: { comparisonId: string; method: string }): void;
export function lastComparison(networkId: string): { comparisonId: string; method: string } | null;
```

- [ ] **Step 1:** write the failing unit tests: both `siteStory` sentences above, exactly; `drivingSeries` picks `unmet` for `reason: "unmet"` and `expiring_unsold` for `"expiry"`, keeps nulls as null, and returns null when the product is missing; `otherAtRisk` lists only products with a positive unmet or expiring total, each in its own unit, never summed; `lastComparison` returns null for another network or malformed storage.
- [ ] **Step 2:** implement the three modules.
- [ ] **Step 3:** write the failing e2e tests:
  - activating a row replaces the list with the panel: "Back to list", the site name as a heading, the band as shape plus text, the story sentence, a chart with a caption naming the product, unit and "projection", and "Show as table", which swaps the chart for a table with the same seven values;
  - **a null day** shows "no data" in the table and a gap in the chart, not 0 (Review Focus 3);
  - a `sales`-basis row shows the sales label;
  - Prev/Next move through the sites in the current sort order and the map follows; Escape or "Back to list" returns to the list with focus on the row left;
  - a not-ranked site shows its reason in place of the story and chart;
  - "See what to do" links to `/decisions?comparison_id=…&method=…` when a comparison is remembered for this network, else to `/scenarios` with the label "Plan transfers in Scenario Lab";
  - under reduced motion the panel appears without a transform animation.
- [ ] **Step 4:** implement `SitePanel` (200 ms slide on the existing curve; the Retail DC note on DC panels; "N more products" and "Site details" open the existing per-product table).
- [ ] **Step 5:** tests pass. Commit.

### W5A-07: Routes, Layers and the animation setting · M · depends on: W5A-06 · V1-A20

**Files:** modify `atlas-map.tsx`, `atlas-motion.ts`, `supply-flow.css`, `components/enrichment/settings-view.tsx`; tests `atlas-motion.test.ts`, e2e `atlas-routes.spec.ts`, `v1-motion.spec.ts`.

**Produces:** in `atlas-motion.ts`, `ROUTES_ANIMATE_KEY = "pp-atlas-routes-animate"`, `setRoutesAnimated(on: boolean)`, `useRoutesAnimated(): boolean`, beside the existing pause store. Route label: `"<road_miles> mi · <n> day(s)"`, or `"<n> day(s)"` when `road_miles` is null; disabled routes are not drawn.

- [ ] **Step 1:** write the failing tests:
  - unit: the animate store defaults to false, persists "1", and notifies subscribers;
  - e2e: with nothing selected no route line exists; selecting a site draws only routes that touch it, each with its label; "Layers" → "All supply routes" draws every enabled route, static; with default settings `document.getAnimations()` has no infinite animation;
  - Settings has a "Map" section with the checkbox "Animate all supply routes" (off by default); when on, the map shows "Pause link animation" with `aria-pressed`, and pausing stops the animation; under reduced motion nothing animates even when on.
- [ ] **Step 2:** implement; fetch routes with `networkApi.routes` once per network.
- [ ] **Step 3:** tests pass. Commit.

### W5A-08: The frame: summary, Run forecast, and the empty and error states · M · depends on: W5A-07 · V1-A20

**Files:** create `components/overview/overview-screen.tsx` (composes list, panel and map; replaces `DangerRankingSection` in `network-atlas.tsx`); modify `components/forecast/forecast-run.tsx` (placement only), `danger-ranking.tsx` (delete what the new screen replaces; keep exports others import); tests e2e `atlas-frame.spec.ts`, `atlas-ranking.spec.ts`, `v1-full-journey.spec.ts`, `v1-connected-import.spec.ts`.

- [ ] **Step 1:** write the failing e2e tests:
  - the context bar shows "Forecast run <date> · next 7 days" and, for a presenter, the Run forecast control with its existing labels; it keeps focus while busy (`aria-disabled`);
  - **no forecast run:** the list area shows "No forecast yet" with the Run forecast control, and the map still shows the sites as not ranked (Review Focus 4);
  - **the ranking request fails:** an error message with "Retry" is shown, and Retry refetches (Review Focus 4);
  - when a forecast finishes, the list and map refresh without a reload;
  - at 1440×900 and 1280×720 the first row and the whole map are visible without scrolling; at 390×844 the list comes first, then the map, with no horizontal scroll.
- [ ] **Step 2:** implement `OverviewScreen`; mount Run forecast through `PageActions`.
- [ ] **Step 3:** update the journey and import specs for the new region names. Tests pass. Commit.

### W5A-09: Accessibility sweep and evidence · M · depends on: W5A-08 · V1-A13, A20

- [ ] **Step 1:** rewrite the atlas parts of `v1-a11y.spec.ts`: keyboard path (search → sort → groups → rows → panel → map controls → Layers), axe with no violations, and reduced motion, at 1440×900, 1280×720 and 390×844, in light and dark.
- [ ] **Step 2:** an e2e test loads a mocked 100-site network in one metro area and asserts the Review Focus 1 overlap rule on rendered marker boxes and that the list count equals 100.
- [ ] **Step 3:** screenshots (list, panel, routes, all-routes layer, no forecast, signed out) at the three viewports, light and dark, into `docs/pantrypulse/visual-evidence/v1-w5a-overview/`.
- [ ] **Step 4:** lane done: `node scripts/quality/run.cjs full` with `.env.lane` and PP19 isolation, the connected e2e run, `/devkit:ship-check`; hand back for the verifier and the ux-critic. The lead opens PR 2 after Gabriel's OK.
