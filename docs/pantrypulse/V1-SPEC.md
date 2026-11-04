# PantryPulse v1 — bring-your-own-network, runs locally

**Status:** APPROVED by the user on 2026-11-04 (decisions V1-D01–D18; builder check done) · **Date:** 2026-11-04 · **Base:** `v1-local` at `c3ec1ed`
**Authority:** this document records explicit user decisions made on 2026-11-04. Under [SPEC-V5](SPEC-V5.md) §1 precedence rule 1, it overrides V5 wherever they conflict. V5 still governs everything this document does not change. Gap evidence: [GAP-REPORT](../GAP-REPORT.md).

Labels used below:

- **(user)** marks a decision the user made in the 2026-11-04 brainstorm.
- **(lead call)** marks a choice the lead made that the user can overturn while reviewing.
- **Builder** marks details left to the implementer.

---

## 1. Intent

PantryPulse was a hackathon demo: one presenter, a fictional six-pantry network, and seeded data. v1 makes it a tool that **a stranger can install on their own machine and use with their own network**. That network is either a food-pantry network or a supermarket chain's stores. In both cases the coordinator has locations, current inventory with expiry dates, and daily demand or sales history.

The stranger's ten-minute success (user):

1. Install locally from a README, with clear hardware requirements, using one start command.
2. Import their own data easily, with the UI explaining where each piece goes, in what format, and what each constraint or option does.
3. Forecast demand for their locations, and see on the atlas which locations will run short and which are in the most danger.
4. Open an allocation section and compare several allocation methods and their effects on each location.
5. Open a decisions section that suggests corrective actions in the form **"this is the action, this is why, this is the effect"**, and export the chosen ones as a plan.
6. Trust the forecast *to an extent*. It explains itself, and plans account for expiry and travel distance.

## 2. Goals, non-goals, anti-goals

**Goals**

- A user's own network at regional scale (§5.1) imported through templates, in two network modes: Pantry and Retail.
- Several allocation methods per mode, compared on identical frozen inputs.
- Explained transfer suggestions with a per-action effect, exported as a plan.
- One-command local install on Windows 11 and Linux, with no paid keys required.

**Non-goals for v1** (deferred; see §11)

- Supplier ordering, markdowns or discounts, and full-state 60,000-SKU scale.
- Changing stock inside the app: approval, reservations and dispatch.
- Arbitrary file formats or a column-mapping wizard.
- Hosted or multi-user deployment.

**Anti-goals.** Any of these would make v1 a failure even if it technically works:

- The app silently changes, invents or zero-fills a user's numbers. Missing history stays missing, and a sales-based forecast is labeled as such.
- Results look precise when they aren't. Examples: quantiles shown as calibrated intervals, per-action effects added up as if they were additive, or different units summed into one total.
- Install fails on a clean Windows 11 or Linux machine, or needs a paid account to finish the core journey.
- A user's data, address lookups or keys leave the machine without the user knowing. The only outbound calls are the explicit, labeled Census lookups and Google Maps calls the user opted into.

## 3. Decisions made by the user (2026-11-04)

| ID | Decision |
|---|---|
| V1-D01 | Target user brings their own dataset of locations (pantries/hubs or stores/distribution centers) with inventories and **daily demand or sales history** |
| V1-D02 | Accepted actions produce an **exported plan**. The app never changes its own stock; users act in their own inventory systems |
| V1-D03 | Two network modes. **Pantry**: help the most people, weighted by neighborhood poverty. **Retail**: distribute inventory so items sell before they expire. Allocation methods are expanded so coordinators can compare them |
| V1-D04 | In Pantry mode, neighborhood poverty is **looked up from the address using free public data**, not supplied by the user |
| V1-D05 | v1 scale is regional: **~100 locations, ~500 products, 90 days of daily history**. Full-state / 60,000-SKU scale is the **next milestone** after v1 (testing region: Florida) |
| V1-D06 | Users fill in **our CSV templates**; no column mapping of arbitrary files |
| V1-D07 | Corrective actions are **transfers between locations only**. Supplier ordering and markdowns are v2 |
| V1-D08 | Retail mode can judge plans by **units saved from expiry and by dollar value**; the template carries the optional price |
| V1-D09 | Users **must provide expiry dates** for inventory batches. A batch can be explicitly declared non-expiring (V5 BD-43) |
| V1-D10 | Include a **bring-your-own-key Google Maps** hookup for road distance/time. It is off unless the user supplies a key; straight-line distance is the default |
| V1-D11 | Trust signal: forecasts show method, fallback and real uncertainty, plus a **backtest on the user's own history** |
| V1-D12 | Requirements from the request: one start command; local Postgres in Docker (Neon/Vercel optional); no paid keys; seed data; a README quickstart (OS scope narrowed by V1-D16) |
| V1-D13 | Add an optional **`inbound.csv`** of scheduled incoming deliveries |
| V1-D14 | Add **donation history** and forecast donations |
| V1-D15 | If the optimizer doesn't fit the envelope: **(1) optimize only at-risk products, then (2) lower the envelope, and only then (3) raise run-time ceilings, with evidence** |
| V1-D16 | v1 supports **Windows 11 and Linux**. macOS is out of v1 (no test hardware) |
| V1-D17 | **No target date.** Delivery follows dependency order |
| V1-D18 | Install images use **option C**: `compose.yaml` names published images and keeps the build recipe. Strangers pull prebuilt images; contributors use `--build`. Publishing turns on once, before the first public release, and only with the user's go-ahead |

## 4. Preserved from SPEC-V5

These remain binding in v1:

- **Hard FEFO** (first-expiry, first-out) and lot-level expiry semantics. BD-43/44: usable through the expiry day; unknown expiry is unavailable.
- **Daily lost-sales projection** (BD-48).
- **Explicit transfer mode with no default** (BD-41). The labels change per network mode (§6.2).
- **Frozen, hashed scenarios** (BD-09/10) and **durable jobs** with 202 acceptance, queue limits and manual retry (BD-11/12/34–38, ADR 0005).
- **Same-origin Next.js proxy**, with FastAPI authoritative and presenter authentication enforced in the backend (BD-13/14).
- **Independent verification** of every published method result, and native solver status handling (V5 §10.5).
- **Provenance:** actual provider and fallback per series; null demand preserved; no future leakage; and no summing of different units into an unlabeled total.
- **Research claims:** EGP_PI_INSPIRED stays a bounded adaptation of Rampazo et al. (DOI 10.1111/itor.70252). The V5 §10.4 research gate still applies to it. Run `research-claims-check` on every new UI string or doc that mentions the research.

**V5 items this document changes:**

| V5 item | Change |
|---|---|
| §2.1 population (fictional six beneficiaries) | Replaced by user-imported networks; the sample networks (§8) keep the fictional fixture role |
| §11 supplier proposals (accepted, paused) | **Scope amendment:** moved to v2 by V1-D07 |
| V5 §20 ("no-action/greedy supplemental") | Simple baselines become first-class compared methods (V1-D03); classical vs research remains the primary Pantry comparison |
| §12.3 visitor reads | Not needed for a single local user; kept in code, not in the v1 journey |
| §15 "no startup migrations" | **(lead call)** Amended for the local stack only: a one-shot `migrate` service upgrades the install's own local database. Hosted/shared databases keep the deliberate-migration rule |
| OPEN-02 per-transfer benefit | **(lead call)** Resolved for v1 as a labeled remove-one-transfer counterfactual (§6.5) |

## 5. Scope of v1

### 5.1 Scale envelope (V1-D05)

| Dimension | v1 target | Note |
|---|---|---|
| Locations per network | ≤ 100 (hubs/DCs + pantries/stores) | Today the scenario schema caps at 14 (`schemas/or_inputs.py:304`) |
| Products per network | ≤ 500 | Today capped at 8 (`or_inputs.py:305`) |
| History | ≤ 90 days daily per location × product; ≥ 14 days to forecast | ≤ 4.5 M history rows |
| Inventory batches | ≤ 200,000 rows | Builder may adjust after measurement |
| Forecast series per run | ≤ 50,000 (seven days each) | Baseline methods only by default |

Anything over the envelope is rejected at import with a clear message and the limit. It is never truncated silently.

### 5.2 In v1

1. **One start command** with Docker as the only prerequisite (§7).
2. **Templates and import** with row-level validation (§6.1).
3. **Location enrichment:** Census geocoding, poverty attributes and distance (§6.3).
4. **Network modes** (Pantry and Retail) and expanded methods (§6.2).
5. **Forecasts** with explanation and backtest (§6.4).
6. **Atlas danger ranking** (§6.6).
7. **Method comparison** (existing Recommendations/Scenario Lab, extended).
8. **Decisions:** explained transfer suggestions and plan export (§6.5).
9. **Two fictional Florida sample networks**, one per mode, that work offline (§8).
10. **README quickstart** with hardware requirements, verified on Windows 11 and Linux (§9).
11. **Test kit** decisions for backup groups A and B (§10).
12. Carry-over: cherry-pick `647f6a8`, which widens the Scenario Lab builder panel, with a visual check.

## 6. Behavior

### 6.1 Templates and import (V1-D06, V1-D09)

Templates are UTF-8 CSV files. Each has a header row, a downloadable blank copy, a filled example, and an in-app guide explaining every column, its unit, and what it changes in the plan. Optional columns are marked; leaving one blank never becomes zero.

| Template | Required columns | Optional columns |
|---|---|---|
| `locations.csv` | `location_id`, `name`, `type` (`hub`/`pantry` in Pantry mode; `distribution_center`/`store` in Retail mode), `street`, `city`, `state`, `zip` | `latitude`, `longitude` (skip geocoding), `receiving_capacity_per_day` (handling units), `poverty_rate`, `snap_rate` (manual override of the lookup) |
| `products.csv` | `product_id`, `name`, `unit` (e.g. case, each, lb) | `unit_value_usd` (Retail $ results), `handling_units_per_unit` (default 1, shown as an assumption) |
| `inventory.csv` | `location_id`, `product_id`, `batch_id`, `quantity` (nonnegative integer, in the product unit), `expiry_date` **or** `non_expiring=true` | `received_date` |
| `demand_history.csv` | `location_id`, `product_id`, `date`, `quantity`, `basis` (`demand` or `sales`) | blank `quantity` = unknown day (kept as missing, never zero) |
| `routes.csv` (optional file) | `from_location_id`, `to_location_id` | `travel_days`, `cost_per_handling_unit`, `capacity_per_batch`, `disabled=true` |
| `inbound.csv` (optional file, V1-D13) | `location_id`, `product_id`, `quantity`, `arrival_date`, `expiry_date` **or** `non_expiring=true` | `source` (`dc_delivery`, `supplier`, `donation`, `other`), `reference` |
| `donation_history.csv` (optional file, V1-D14) | `location_id` (receiving location), `product_id`, `date`, `quantity` | `donor` (free text, kept separate from the receiving location) |

Inbound and donation rules:

- **`inbound.csv`** rows are **confirmed** arrivals. They enter the projection and planning on their arrival date, under the BD-48 daily order (arrivals first). Arrival dates must fall inside the seven forecast days after `as_of_date`; later rows are kept and listed as "outside horizon". Each arrival enters the network's stock only once: it is never counted as on-hand as well (V5 §5.3).
- **`donation_history.csv`** works like demand history, but for received donations, summed per receiving location × product × day (V5 §5.2).
  - A row with quantity `0` means "reported, nothing received". A missing day stays **unknown**, never zero. This keeps V5's coverage distinction without a separate coverage file.
  - It is available in both modes; it's expected mainly in Pantry mode.
- **Forecast donations** (lead call, following BD-07: the baseline counts only confirmed resources):
  - Donation forecasts are shown in the Overview/forecast views, and in each location's "why" text as "expected donations (forecast, not confirmed): X".
  - They are **not** counted as arrivals in any allocation method or in the danger score.
  - Counting forecast donations as supply is deferred (§11). It would need its own labeled scenario option and review.
- If a network has no `inbound.csv`, the atlas, forecasts and every plan export show **"no scheduled deliveries provided"**.

Import rules:

- A network is created by one import of the four required files, **in one chosen network mode**. The mode is fixed for that network.
- **Network settings entered at import** (lead call):
  - **One network timezone** (BD-50 requires one planning timezone per scenario; `or_inputs.py:337-341` rejects mixed zones). Per-location timezones are not supported in v1, and the guide says so. Florida's Central-time panhandle plans on the network's day boundaries.
  - **`as_of_date`**, the date the inventory snapshot describes. It defaults to the day after the last history date and is editable. It is the scenario's `snapshot_as_of`, and planning starts the day after it. History dated after `as_of_date` is rejected (no future leakage).
- **Inputs the templates don't carry** (lead call):
  - A blank capacity (receiving, route, dispatch, storage, global handling) means **no limit**. The scenario and every plan export show "capacity not provided — no limit assumed".
  - Reserve floors default to **0**, editable per scenario in the existing Scenario Lab builder, and shown as an assumption.
  - The cost budget is off unless the user sets one.
- Validation is all-or-nothing per network import. Every error is reported with file, line, column and reason; the checker reports up to the first 1,000 errors. Nothing is saved until all files pass. *(lead call. V5 allows partial demand imports; for a first-time import, all-or-nothing is easier to understand. Builder may revisit for later re-imports.)*
- Sales history is labeled **"sales (undercounts demand when shelves were empty)"** everywhere it shows up. This follows BD-06's explicit-proxy rule: choosing `basis=sales` is the opt-in.
- Import never "posts" stock through the receipt ledger UI. Imported batches become the network's opening snapshot, recorded as one audited import event.
- Re-import: a user can import a newer snapshot into an existing network. It is a new dataset version; earlier scenarios and results keep the version they used.
- Large files: the current 64 KB request limit (`main.py:71`) cannot carry 4.5 M rows. **Builder** designs a bulk upload path (e.g. streamed upload into staging tables plus PostgreSQL `COPY`), run as a durable job with progress, within the size envelope.

### 6.2 Network modes and methods (V1-D03, V1-D08)

| | Pantry mode | Retail mode |
|---|---|---|
| Purpose | Help the most people; poverty-weighted priority | Sell stock before it expires; avoid lost sales |
| Location roles | `hub`, `pantry` | `distribution_center`, `store` |
| Transfer modes (explicit, no default) | `HUB_ONLY` = "Hub → pantries only"; `HUB_AND_PANTRY` = "Hub and pantries → pantries" | Same enums, labeled "DC → stores only" and "DC and stores → stores" |
| Measure | Unmet need (units per product), service ratio, poverty-weighted shortfall | Units expiring unsold and lost sales, in **units or USD** (user picks per scenario; USD needs `unit_value_usd` for every included product, otherwise USD is unavailable with the reason shown) |
| Methods compared | 1. No transfers · 2. Equal share · 3. Most-urgent-first · 4. CLASSICAL_GP · 5. EGP_PI_INSPIRED | 1. No transfers · 2. Soonest-expiry-first · 3. Optimized (minimize expired + lost sales) |

Method notes:

- **All methods in a comparison share one frozen scenario and one feasible region**, and each result goes through the independent verifier before it's published. Heuristics (equal share, most-urgent-first, soonest-expiry-first) are deterministic, with declared tie-breaks.
- **Retail "Optimized"** is a new CP-SAT objective: minimize `w_exp × expired + w_lost × lost_sales` over the allocation window, in units or USD.
  - (lead call) Defaults are `w_exp = 1`, `w_lost = 1`. They are shown in the scenario and editable. These are disclosed v1 defaults, not a research claim.
  - It needs its own small hand-derived oracle fixtures before integration, mirroring V5 §10.4 steps 3–4.
- **EGP_PI_INSPIRED** vulnerability attributes come from Census (§6.3). There are two attributes, poverty rate and SNAP-household rate, which satisfies V5 §10.2's "at least two documented attributes".
  - Coefficients and λ/β keep the values already used by the connected flow, shown and editable as today.
  - Locations with unknown attributes are listed. The user must enter values or explicitly exclude those locations before an EGP scenario can be frozen; there is no silent exclusion (BD-08).
- Hubs/DCs never receive. In Retail mode a store sends only surplus beyond its own protected seven-day sales forecast plus reserve. This is BD-49 applied to stores.
- **Retail horizon** (lead call, following V1-D03's "sell before it expires"):
  - The batch is still dispatched once, on the first planning day (BD-50).
  - Retail measures expiry and lost sales over the **full seven forecast days**, not the 1–3-day window.
  - **BD-51 is relaxed for Retail only:** a transferred unit must be projected to sell at the receiver before both its expiry and the end of the seven-day horizon. It no longer has to sell inside the 1–3-day window.
  - Pantry mode keeps BD-51 unchanged.
  - Each comparison is single-mode, so "one frozen scenario, one feasible region per comparison" still holds.
  - The Retail oracle fixtures (§12 item 2) must include a day-5 expiry case.

### 6.3 Location enrichment (V1-D04, V1-D10)

- **Geocoding:** US Census Geocoder batch endpoint (free, no key). It returns coordinates and the census tract. Unmatched addresses are listed; the user fixes the address or enters coordinates.
- **Poverty attributes:** American Community Survey 5-year estimates by tract (poverty rate and SNAP-household share; Census Data API, free, key optional at low volume). Fetch by county, so 100 locations is a handful of calls. Store the source table, year and fetch time; show "Source: ACS 5-year YYYY, tract NNNN".
- **Travel distance and time:**
  - Default: straight-line distance × 1.3 road factor (lead call), at an assumed 45 mph average (lead call). Converted to whole `travel_days` (BD-50).
  - Candidate routes are each receiver's k = 10 nearest senders within 150 miles (lead call; editable).
  - **Optional Google Maps:** if the user pastes their own key in Settings, compute road distance and time for candidate routes, cache the results, and label each route with its method ("straight-line estimate" or "Google road distance, fetched DATE").
  - The key is stored only in the local database or env, never logged, and never sent to the browser.
  - **Builder** confirms which current Google endpoint to use (Routes API route matrix vs legacy Distance Matrix) and its limits at build time.
  - `routes.csv` overrides any computed value.
- **Offline behavior:** if Census or Google is unreachable, import still succeeds. Affected fields are marked unknown with a retry button, and EGP stays blocked for locations with unknown attributes (§6.2). The sample networks ship with pre-filled values and never call out.
- Census is US-only. v1 testing is Florida; non-US addresses are rejected with a clear message.

### 6.4 Forecasts and trust (V1-D11)

- Methods: the existing weekly seasonal-naive, then moving-average fallback, with actual provider and fallback per series. **Chronos is off by default** (lead call): it failed its own 99% availability gate (V5 §6.5), and it adds a multi-GB download. It's an opt-in Docker profile, labeled experimental.
- Each forecast view shows the method used, the fallback reason, missing-day count, `sales` basis label, and quantile bands **only** when the provider produced them.
- **Backtest:** for each location × product, and rolled up per location, show rolling-origin accuracy over the last 4 weekly origins on the user's own history. Display WAPE as a percentage and bias as over/under-forecast, computed on the same scored set (V5 §7 formulas).
  - It needs ≥ 35 days of history; otherwise the view says "accuracy not evaluated: needs 35+ days".
  - Wording is "on your last 4 weeks, this forecast was off by about X%". There is no claim about future accuracy.
- Forecasts run as durable jobs. At max scale (50,000 series) the forecast job must finish inside the existing 300 s ceiling, or the measured limit is raised with evidence and disclosed.

### 6.5 Decisions: suggested actions and export (V1-D02, V1-D07)

- The Decisions section starts from one chosen method result on one scenario. Each suggested action is one transfer, shown as three parts:
  1. **Action:** "Move 40 cases of Bottled water from Hub North to Pantry 12, ship on Nov 6, arrives Nov 7."
  2. **Why:** derived from the frozen inputs, for example "Pantry 12 runs out on Nov 8 (projected unmet 55 cases over 3 days); Hub North has 120 cases beyond its protected need; 30 of them expire Nov 12." Distinguish a proven binding constraint from an inferred reason, as V5 §14.1 requires.
  3. **Effect:** a **remove-one-transfer counterfactual** (lead call; resolves OPEN-02 for v1). Re-project the plan with this one transfer removed, without re-optimizing, and show the difference at the sender and receiver: unmet units, expired units, USD in Retail mode when available.
- Effects are labeled **"effect of this action given the rest of the plan; effects don't add up across actions"**.
- The user selects actions and **exports a plan**: CSV plus a print-friendly page (lead call). Each row carries the scenario ID and hash, method, network mode, units, the why/effect text, and "simulated plan; no stock was reserved or moved".
- No in-app approval, reservation or stock change. The existing "Mark reviewed — simulation" stays as-is.

### 6.6 Atlas danger ranking

- Locations are placed by real coordinates. Basemap: **Builder**, but it must need no paid key. A schematic coordinate projection like today's (`network-atlas.tsx:174`) is acceptable; any tile provider must be free and keyless and must respect its usage policy.
- **Danger score** (lead call), per location, for the forecast horizon:
  - Pantry mode: the worst product's **share of 7-day demand projected unmet**, a unitless ratio. Ties are broken by the earliest first-deficit day.
  - Retail mode: the same, plus the share of stock projected to expire unsold. The higher of the two is shown, with its reason.
  - Units are never summed across products. The ranked list shows the driving product and its units.
- Atlas color/shape encodes the danger band, with a text label and accessible table (V5 §14.2). Selecting a location opens the existing site inspector.

## 7. Local runtime and the one start command

- **Supported OSes (V1-D16):** Windows 11 and Linux (reference: Ubuntu 24.04). macOS is untested and out of v1.
- **Prerequisites:** Docker Desktop with the WSL 2 backend (Windows 11), or Docker Engine with the Compose plugin (Linux), plus git. Node, Python and uv are **not** required to run the app; they stay contributor-only.
- **Start command:** `docker compose up` from the repository root (lead call). The default `compose.yaml` becomes the full local stack. It starts these in order:
  1. `postgres`: data in a named volume, **not published to the host**.
  2. `migrate`: one-shot Alembic upgrade of the local DB.
  3. `seed`: one-shot; loads the two sample networks only if absent; never resets.
  4. `api`: not published.
  5. `worker`: Linux containment works inside the container on every OS.
  6. `web`: Next.js production build, published on `127.0.0.1:${PP_WEB_PORT:-3000}`.

  Only the web port is published. That avoids the 5432/8000 collisions seen on the dev machine.
- **Images (V1-D18, option C):**
  - Each app service (`migrate`/`seed`/`api`/`worker` share one API image; `web` has its own) declares both `image: ghcr.io/gbw30/pantrypulse-<name>:<version>` and a `build:` recipe.
  - `docker compose up` pulls the published images. `docker compose up --build` builds locally from the lock files (`npm ci`, `uv sync --frozen`).
  - A release workflow builds `linux/amd64` images on a version tag and pushes them to GitHub Container Registry as public packages. macOS/arm64 is not built (V1-D16).
  - **Until the user authorizes the first publish**, there are no published images: everyone uses `--build`, and the README says so.
  - Creating a tag, publishing images, and making packages public are outward-facing release actions. Each needs the user's explicit go-ahead.
  - The README's version pin and the compose image tag must match. **Builder** adds a check for this.
- The existing dev compose services and profiles (`--profile api`, `compose.compute.yaml`, `compose.forecast.yaml`) are kept for contributors under new names or files. **Builder** chooses the names and updates `INSTALLATION.md`.
- **Login:** keep presenter authentication in the backend, with no bypass (lead call).
  - On first start, the stack generates a random local password. It stores the password's hash in the database, and stores the password itself only in a gitignored file, `./.pantrypulse/local-login.txt`.
  - It prints `Open http://127.0.0.1:3000 — username: local — password: see .pantrypulse/local-login.txt` on startup.
  - The proxy token is generated the same way.
  - The scrypt-hash `$` gotcha must not be reproducible: values are never passed through shell `eval`.
- **Neon / Vercel / Fly / Cloudflare:** optional and documented as before. None is needed for any v1 acceptance criterion.
- **Start over:** `docker compose down -v` deletes all local data. It's documented with a warning. This is the v1 "reset". A scoped in-app reset is deferred.
- Windows: add `.gitattributes` so shell scripts and Docker entrypoints keep LF line endings (CRLF breaks Linux containers).

## 8. Seed data (sample networks)

Two **fictional** Florida networks are seeded on first start. Both are labeled "Sample data — fictional" everywhere:

| Sample | Size | Notes |
|---|---|---|
| Pantry sample | 1 hub + 8 pantries, ~6 products, 90 days | Extends the existing `data/demo/forecasting-v1.json` fixture style; poverty/SNAP values pre-filled and labeled "sample values" |
| Retail sample | 1 DC + 20 stores, ~50 products with `unit_value_usd`, 90 days, batches with varied expiry | Fictional chain name; **no real brand names** (anti-impersonation) |

Both use city-level coordinates in the `latitude`/`longitude` columns, with no street addresses of real buildings, so seeding never calls Census or Google. The template example files are generated from the same data, so the examples and the sample always match.

**Sample dates** (lead call): history, expiry and `as_of_date` are generated relative to the day the seed runs, as `load_optimization_demo.py` already does. A sample older than 7 days would show only expired batches. So on each start, the `seed` service adds a **new, freshly dated sample version** when the newest one is more than 7 days old. Older versions and their results stay intact; nothing is reset.

**Existing stock-changing screens** (lead call): receipts, posting, adjustments and lot declarations (`routers/operations.py:86-175`, `routers/inventory.py:29`, `app/data/operations`, `app/data/inventory`) are **removed from v1 navigation**, but their API and code stay. In v1 a user corrects stock by re-importing a newer snapshot (§6.1). This keeps V1-D02's "the app never changes its own stock" true from the user's point of view.

## 9. README quickstart and hardware

- `README.md` gets a quickstart at the top: prerequisites, `git clone`, `docker compose up`, the login line, a first-run time estimate, "try the sample", "import your own data" (link to template guide), "start over", and troubleshooting (port in use, Docker memory setting, WSL 2 backend).
- **Hardware requirements** are stated from measurement, not guessed. Measure first-run build/pull time, idle RAM, and peak RAM/CPU during a maximum-scale forecast and comparison on a reference laptop. Provisional, to confirm: 4 CPU cores, 8 GB RAM available to Docker (16 GB recommended), 15 GB free disk; Chronos profile +10 GB disk.
- The worker's 6-CPU / 8 GiB ceilings stay; the README explains that Docker Desktop's memory setting must allow them.

## 10. Backup branch test groups A and B (decision)

`wip/overview-intake-backup` (`b54ec7c`) branches from the old main `a4573b5`, so every file must be re-checked against current main before it's adopted.

**Group A: Vitest unit tests. ADOPT, partially.**

- Adopt Vitest, Testing Library and jsdom with the versions pinned on the backup (`vitest.config.mts`, `tests/unit/setup.ts`) as a lead-owned lockfile change.
- Port the tests whose components still exist: `atlas-layout`, `network-atlas`, `site-inspector`, `static-fixture`, `status`.
- **Drop** `outlook.test.ts` and `outlook-chart.test.tsx`; their components no longer exist on main.
- Keep the existing `forecast-proxy.test.mjs`, either moved under Vitest or kept as `node --test`. `test:unit` must run both.
- Add v1 unit tests for import-error messages, danger ranking, action why/effect text and the USD-unavailable state.
- `@vitest/coverage-v8` may come along. **No global coverage target** (ACCEPTANCE-MATRIX quality rule).
- Why: V5/ACCEPTANCE-MATRIX already call for Vitest coverage of UI state, and main has none (GAP-REPORT §4).

**Group B: testing tooling. ADOPT two pieces, DROP the rest.**

| Piece | Decision | Why |
|---|---|---|
| `compose.test.yaml` + `scripts/testing/docker-tests.cjs` | **Adopt**, update the mounts for the current tree, expose as `npm run test:docker` | Lets Windows/macOS contributors run the full backend suite against real PostgreSQL in Linux containers, with `--require-no-skips` |
| `docs/testing/user-stories.json` + `scripts/testing/story-coverage.cjs` (+ test) | **Adopt the mechanism, rewrite the content** for v1 stories mapped to V1-A IDs | Gives a checked map from each acceptance criterion to the tests that cover it |
| `@story` tag convention in e2e titles | **Adopt** | Needed by the story-coverage script |
| `user-stories.spec.ts`, `controls.spec.ts`, `api.spec.ts` | **Drop** | They assert the old static-fixture and "unimplemented" states that main has since replaced; the v1 journey spec replaces them |
| `scripts/testing/diagnostics.cjs` (+ test), `docs/testing/BRANCH-DIAGNOSTICS-2026-10-25.md` | **Drop** | Dated snapshot of an old branch |
| `.github/workflows/tests.yml` | **Drop** | Duplicates `pantrypulse-ci.yml`; fold any useful step into it |
| `docs/testing/README.md` | **Rewrite** as the v1 testing guide | Old content describes the old branch |

## 11. Deferred

| Item | Target |
|---|---|
| Full-state scale, ~60,000 SKUs per store, 6 months history | **Next milestone after v1.** Proposed design: forecast everything cheaply, then optimize only at-risk location × product pairs, using columnar/batch storage |
| Supplier ordering/proposals (V5 §11), markdowns/discounts | v2 |
| In-app approval, reservations, dispatch, stock changes (P1) | v2 or later |
| Self-hosted OSRM road routing | v2 |
| Column-mapping import, Excel files | v2 |
| Multi-user/hosted deployment, roles beyond presenter, visitor journey | later |
| Calibrated intervals, Chronos by default, automatic model selection (D09) | later; needs qualification |
| Scoped in-app reset/delete-network | later (`down -v` covers v1) |
| Non-US addresses / non-Census poverty sources | later |
| macOS support (V1-D16) | later; needs test hardware |
| Counting forecast donations as supply in a labeled scenario option | later |

## 12. Riskiest unknowns, with the spike that settles each

Ordered by risk. Each spike is time-boxed, its code is throwaway, and its finding is recorded before the dependent work is planned.

1. **Optimizer at 100 × 500.**
   - Can CP-SAT produce verified Pantry (EGP with RP group means over up to ~100 receivers per product) and Retail results within the existing 300 s search / 690 s comparison ceilings?
   - Spike: build a synthetic 100 × 500 scenario and test decomposition by product, k-nearest routes, and optimizing only at-risk products.
   - If it doesn't fit, apply V1-D15 in order: optimize only at-risk products first, then lower the envelope. Raise ceilings only as a last resort, with evidence.
2. **Retail objective correctness.** A new objective has no oracle yet. Hand-derive 3–4 tiny fixtures (expiry-driven transfer, lost-sales-vs-waste trade-off, USD vs units flip, nothing worth moving) before building it.
3. **Cross-platform Docker.**
   - Windows CRLF, first-run time, and Docker Desktop memory defaults on Windows 11.
   - Spike: build and run the stack on Windows 11 and Ubuntu before README work.
4. **Bulk import at 4.5 M rows.** Upload size, validation speed and PostgreSQL load on a laptop. Spike: generate a max-size file and time staging + `COPY` + validation.
5. **Census API behavior.** Batch geocoder match rates on real Florida addresses, tract-level ACS availability, rate limits without a key, outage behavior.
6. **Google endpoint choice/cost.** Confirm the current API, request shape, quota and per-element billing before writing the client. The user pays, so the UI must show how many lookups an action will make.
7. **Forecast and backtest volume.** 50,000 series × 7 points per run plus 4 backtest origins. Measure storage and time against the 300 s ceiling.

## 13. Acceptance criteria

PASS needs evidence for the exact commit and environment: command, timestamp, artifacts. A skipped, mocked or fixture-only check is not a pass (CLAUDE.md). IDs are V1-A**nn**; the matching rows are in [ACCEPTANCE-MATRIX](ACCEPTANCE-MATRIX.md).

| ID | Criterion | Evidence |
|---|---|---|
| V1-A01 | Clean install: on a clean Windows 11 and Ubuntu 24.04 machine with only Docker and git, `git clone` + `docker compose up` reaches a working login page with no other step | Recorded run per OS: commit, Docker version, elapsed time, screenshot |
| V1-A02 | Only the web port is published; changing `PP_WEB_PORT` works; restarting keeps data; a second `up` doesn't duplicate the seed | Compose inspection + restart test |
| V1-A03 | No paid keys: after install (image pull or build), the full journey (A07–A16) completes with no keys configured and no outbound calls except Census lookups for user-imported addresses | Journey run with egress logged |
| V1-A24 | Images: `docker compose up --build` works from a clean clone. After the user-authorized release, plain `docker compose up` on a clean Windows 11 and Ubuntu machine pulls the published images and needs no local build. First-run time is recorded for both paths in the README | Release workflow run + clean-machine runs for both paths |
| V1-A04 | Local login: generated credentials work; the password never appears in logs, Git or the browser bundle; backend auth and CSRF stay enforced | Log/bundle grep test + existing auth tests |
| V1-A05 | Seed: both sample networks load on first start, are labeled fictional, contain no real brand names, and need no network access | Offline first start |
| V1-A06 | Templates: each template has a blank copy, an example generated from the sample data, and an in-app guide for every column | e2e + example files validate clean |
| V1-A07 | Import validation: malformed, duplicate, negative, fractional, unknown-ID, missing-expiry and over-envelope rows are each rejected with file/line/column/reason, and nothing is saved | API + e2e tests per error class |
| V1-A08 | Import truth: blank demand stays missing (never zero); `basis=sales` is labeled wherever it's shown; batch quantities and expiry round-trip exactly | Round-trip test |
| V1-A09 | Bulk import: a maximum-envelope dataset (100 × 500 × 90 days) imports as a durable job with progress, within a measured time recorded in the README | Timed run on reference hardware |
| V1-A10 | Enrichment: geocoding and ACS attributes are stored with source/year; unmatched addresses and outages are reported with retry; EGP stays blocked until unknown attributes are resolved or explicitly excluded | Tests with recorded Census responses + one live run |
| V1-A11 | Distance: the straight-line default produces labeled routes; with a user key, Google distances are cached and labeled, and the key never reaches logs or the browser; `routes.csv` overrides both | Tests with a recorded Google response + one live keyed run |
| V1-A12 | Forecast: every eligible series gets seven dated points with actual provider/fallback; the backtest shows WAPE/bias on the same scored set, or "accuracy not evaluated" under 35 days | API + e2e |
| V1-A13 | Atlas: the danger ranking matches an independent calculation on a fixture; never sums units across products; has a text/table alternative | Unit + e2e + axe |
| V1-A14 | Pantry comparison: all five methods run on one frozen scenario in both transfer modes; every published result passes the independent verifier; method failures show honestly | Integration + e2e |
| V1-A15 | Retail comparison: all three methods run in units and USD (USD unavailable with reason when prices are missing); the optimized method matches the hand-derived oracle fixtures | Oracle + integration + e2e |
| V1-A16 | Decisions: each action shows action/why/effect; the effect equals an independent remove-one re-projection; the non-additive label is visible; export CSV/print contains the scenario hash and "simulated plan" text; no stock changes | Unit + e2e + DB unchanged check |
| V1-A17 | Scale: a 100 × 500 forecast and a full comparison per mode finish within the ceilings in force (or the documented raised ceilings), with peak RAM/CPU recorded | Benchmark artifact |
| V1-A18 | README: a person who has never seen the repo follows only the README on Windows 11 and on Linux and completes install → sample → import own template (including `inbound.csv` and `donation_history.csv`) → forecast → compare → export | Observed run notes per OS |
| V1-A23 | Inbound and donations: confirmed `inbound.csv` arrivals enter the projection once on their date; out-of-horizon rows are listed; donation history keeps 0 vs missing distinct; donation forecasts are shown labeled "not confirmed" and change no allocation or danger score | API + projection golden test + e2e |
| V1-A19 | Hardware: README requirements come from the measured runs in A09/A17 | Measurement artifact linked from README |
| V1-A20 | Accessibility: the new import, decisions and atlas-ranking screens pass keyboard, axe and reduced-motion checks at 1440×900, 1280×720 and 390×844 | e2e |
| V1-A21 | Test kit: Vitest unit tests (group A) and `npm run test:docker` (group B) run in CI; story-coverage maps every V1-A ID to at least one test | CI run |
| V1-A22 | Regression: the existing backend, config, full and connected e2e gates stay green, with zero skips | CI run |

## 14. Left to the builder

These details don't change what gets built:

- Bulk-upload mechanics, staging schema and job contract name.
- Compose file and service names for the contributor setups.
- Basemap choice, within the keyless rule.
- Exact layout of the import, decisions and settings screens, within ART-DIRECTION and ADR 0002.
- Error-cap and progress-reporting details.
- Heuristic tie-break order (it must be declared and tested).
- Whether the network switcher is a header control or a page.
- Migration layout for the new tables.

## 15. Suggested delivery order

1. Spikes 1–3 (§12).
2. Local stack and one start command, with login.
3. Templates and import (including bulk).
4. Enrichment and distance.
5. Retail objective and baselines, with oracles first.
6. Forecast backtest.
7. Atlas ranking.
8. Decisions and export.
9. Sample networks.
10. Test kit A/B.
11. README and hardware measurement.
12. Three-OS acceptance runs.

The plan (`superpowers:writing-plans`) turns this into PP-NN packets.
