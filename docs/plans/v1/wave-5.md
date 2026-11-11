# Wave 5 — lanes `w5-polish`, `w5-screens`, `w5-packaging`, `w5-data`

**Base:** the `v1-local` head after W4 plus the lead's contract CR W5-L01 (`{{BASE_SHA}}`). **Mode:** B for all four lanes. Same rules as wave 1 ([ORCHESTRATION.md §8](ORCHESTRATION.md#8-rules-every-lane-inherits)).

**Order inside the wave:**
1. The lead lands W5-L01, and its merge is the base for all four lanes.
2. `w5-data` merges W5-D01 as soon as it passes review, with Gabriel's OK.
3. `w5-polish` then merges `origin/v1-local` and does W5-UI04.
4. `w5-screens` merges when its PR passes review, with Gabriel's OK. `w5-polish` merges `origin/v1-local` again before W5-UI03 Step 3, so its after-screenshots include those screens.

The other tasks run in parallel. Gabriel added `w5-data` on 2026-11-11 for the W4 carry-ins ([decisions/W4-change-requests.md](decisions/W4-change-requests.md) §10), and the same day split the web work into `w5-polish` and `w5-screens` so the ux-critic fixes run in parallel (§11).

---

## Lead — W5-L01: the contract change for the W4 carry-ins · S · before the lanes start · V1-A08, A12, A16, A23

Lead-owned: schemas, regenerated OpenAPI/TypeScript in `packages/contracts`, and fixtures only where generation requires it. There is no migration, because scenarios and runs store JSON.
- [ ] **Step 1:** write the failing contract tests:
  - `ORInputV3` carries `donations`: per location × product, the seven central values with provider and fallback. It is display-only and never supply.
  - The danger ranking rows and the projection rows carry `basis` (`demand` | `sales`).
  - A backtest location score can be `not_evaluated` with a `reason`.
  - The validators refuse donations without provenance.
- [ ] **Step 2:** add the fields with defaults that keep current scenarios valid, regenerate the contract (`npm run contracts:check` must pass), then the full gate. Make it a PR with Gabriel's OK. Its merge is the W5 base.

---

## Lane `w5-data` — the W4 carry-ins on the API side

Agent role: `solver-engineer`. Owned paths and rules are in [prompts/w5-data.md](prompts/w5-data.md).

### W5-D01: Donation forecasts and the demand basis · M · depends on: W5-L01 · V1-A08, A16, A23

- [ ] **Step 1:** write the failing tests:
  - `test_scenario_freezes_donation_forecasts_with_provenance`: `_demand` keeps each available DONATION series's points, which are never counted as supply.
  - `test_why_text_lists_expected_donations`: each location's why reads "expected donations (forecast, not confirmed): X <unit>", or says plainly that there is no donation forecast.
  - `test_danger_and_projection_rows_carry_basis`.
  - `test_donation_order_does_not_change_the_scenario_hash`: the same forecasts given in any order freeze the same scenario. `donations` is not in `canonical.py`'s `_UNORDERED`, so emit them sorted by location and product (W5-L01 verifier).
  - `test_per_product_scenario_keeps_only_its_donations`: `only_product` (`verify.py:285-292`) and `actions.py:83-89` drop other products' donations, so the cut-down scenario validates again (today it fails with `UNKNOWN_REFERENCE`).
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS). Regenerate the golden scenario and the or-v3 fixtures through their scripts. Commit, and tell the orchestrator that D01 is ready.

### W5-D02: Hubs and distribution centres carry no demand history · S · depends on: none · V1-A07, A08

- [ ] **Step 1:** write the failing test: a `demand_history` row for a hub or DC is refused at import, with its file and line and a fix. An all-blank hub history can then never reach the scenario as "no forecast" while the hub still sends (W4 #144 limit).
- [ ] **Step 2:** run it (FAIL), implement, run it (PASS). Update the template guide's column text. Commit.

### W5-D03: A backtest that can't be scored says why · S · depends on: W5-L01 · V1-A12

- [ ] **Step 1:** write the failing test: an all-zero denominator gives `not_evaluated` with a reason, never "evaluated" with null WAPE and bias (`backtest.py:101-111`).
- [ ] **Step 2:** run it (FAIL), implement, run it (PASS). Commit.

### W5-D04: A commit on a finished import is refused · S · depends on: none · V1-A07

- [ ] **Step 1:** write the failing test: a commit on a `done` or `failed` run returns 409 `IMPORT_ALREADY_FINISHED`, leaves the phase unchanged and admits no job (`imports/api.py:88-95,127`). The W4-03 adversarial reviewer saw the phase go back to `staging`.
- [ ] **Step 2:** run it (FAIL), implement, run it (PASS). Commit.
- [ ] **Step 3:** lane done. Run `full`, then `/devkit:ship-check`, then open the PR `lane/w5-data → v1-local`.

---

## Lane `w5-screens` — the Data Explorer, Scenario Lab and Decisions fixes

Agent role: `frontend-engineer`. Gabriel split the web polish into two lanes on 2026-11-11, so the screen fixes run beside the Overview polish. This lane owns only its three screens' folders (see [prompts/w5-screens.md](prompts/w5-screens.md)); the tokens in `globals.css`, the shell and `components/ui/**` stay with `w5-polish`. **Skills:** `/jmo-workflow:better-ui` (method only; ART-DIRECTION.md and ADR 0002 decide) and `visual-review`.

Findings from W4-03 step 2 ([decisions/W4-change-requests.md](decisions/W4-change-requests.md) §11). For each one: write the e2e or unit test that pins the repair, run it and see it fail, fix it, run it and see it pass, and commit.

- [ ] **W5-UI02.1 Data Explorer shows only the selected network.** With a v1 network selected, `/data` doesn't render the legacy summary block (`data-explorer.tsx:201`). Test: with the Pantry sample selected, `/data` contains no "Riverbend", "Gator" or "bottles" at all three viewports.
- [ ] **W5-UI02.2 Scenario Lab comparison fits.** One method card per row, the transfer count beside "Open suggested actions", and the rows behind a "Show rows" disclosure. Test: at 1280×720 every column header of a card's table is visible without horizontal scrolling, and each card's action link is in its first 200 px.
- [ ] **W5-UI02.3 Decisions names the period.** Every effect line names its dates and window length, and the plan says "Plan covers <dates> only; unmet need after <date> is not planned". Test: each quantity on `/decisions` shows its date range.
- [ ] **W5-SC01: follow-ups on these screens.** Write the failing tests, then fix:
  - `tests/unit/decisions-view.test.tsx:69` (700 selected actions) has an explicit timeout. It takes about 1 s alone but exceeded the 5 s default once under full-gate load on `977f7c6`.
  - `pluralize` (`data-explorer/format.ts:18-22`) writes "boxes", not "boxs" (also "-ch", "-sh", "-x" units). The Overview inspector uses it too.
  - Printing from one tab is unaffected by another tab's Decisions: the selection is saved only when the print link is used (W4 decisions §6).
- [ ] **W5-SC02: evidence and finish.** Take screenshots of `/data`, the Scenario Lab comparison and `/decisions` at 1440×900, 1280×720 and 390×844 into `docs/pantrypulse/visual-evidence/w5-screens/`. Run `full`, then `/devkit:ship-check`, then open the PR `lane/w5-screens → v1-local`. It merges mid-wave with Gabriel's OK, before `w5-polish` takes its after-screenshots.

---

## Lane `w5-polish` — UI polish with devkit stack-web

Agent role: `frontend-engineer`. **Required skills:** `/jmo-workflow:better-ui` (surfaces, icons, alignment), `/jmo-workflow:animate` (purposeful motion only) and the project skill `visual-review`. These come from the devkit `stack-web` bundle. If they don't load in this session, **stop and report** (Gabriel's 2026-11-04 decision). ART-DIRECTION.md and ADR 0002 decide the direction; these skills are method only (CLAUDE.md). This lane owns the tokens in `globals.css` for this wave.

### W5-UI01: Visual baseline · S · depends on: none · V1-A20

- [ ] **Step 1:** use `visual-review` to take screenshots of the import, settings, atlas ranking, forecast trust, comparison, decisions and print screens at 1440×900, 1280×720 and 390×844, in light and dark, into `docs/pantrypulse/visual-evidence/v1-before/`. Commit.

### W5-UI02: Fix the Overview's ux-critic findings · M · depends on: W5-UI01 · V1-A20

For each finding: write the e2e or unit test that pins the repair as the acceptance check (e.g. "CTA visible without scrolling at 390×844", "quantity not clipped", "band meaning has a text label"), run it and see it fail, then fix it with `/jmo-workflow:better-ui`, run it and see it pass, and commit.

Findings 4 and 5 from W4-03 step 2 ([decisions/W4-change-requests.md](decisions/W4-change-requests.md) §11); findings 1–3 belong to `w5-screens`:
- [ ] **W5-UI02.4 Retail expiry reads as expiry.** In Retail mode the legend says "projected short or expiring unsold" (`risk-legend.tsx:55-58`); an expiry-driven row says "first expiry <date>", not "first deficit" (`danger-ranking.tsx:77`); a DC row says "A DC has no sales; stock it doesn't send out counts as expiring". No contract change: `DangerRow.reason` already says `unmet` or `expiry`, and for an expiry row `first_deficit_date` is the first day stock expires unsold (`services/danger/ranking.py:56-69`). Test: on the Retail Overview no expiry-driven row says "deficit", and the legend mentions expiry.
- [ ] **W5-UI02.5 The Overview's first view.** Ranks #1–#3 show without scrolling at 1440×900 and 1280×720 (cap the map height); "Run forecast" moves out of the ranking region, labeled for presenters; the inspector lists the driving product first and marks it; a focused marker shows its site name; Escape closes the live inspector and returns focus to its opener. Tests: one per item.

### W5-UI03: Motion and the final evidence · S–M · depends on: W5-UI02 · V1-A20

- [ ] **Step 1:** write the failing test `apps/web/tests/e2e/v1-motion.spec.ts`: `@V1-A20 every animation is finite, ≤ 1s, and absent under prefers-reduced-motion`. Reuse the finite-animation helper from PR #100.
- [ ] **Step 2:** add or adjust motion only where `/jmo-workflow:animate` finds a purpose. Run the test (PASS).
- [ ] **Step 3:** merge `origin/v1-local` once `w5-screens` has merged, then take the `v1-after/` screenshots and run `v1-a11y.spec.ts` and `v1-full-journey.spec.ts` (PASS). `v1-a11y.spec.ts` covers what the W4 review couldn't: axe at all three viewports on import, Decisions and the atlas ranking; keyboard walkthroughs of import and Decisions; reduced motion at 1280 and 390; marker touch targets at 390×844.
- [ ] **Step 4:** fix the known flaky `overview-layout.spec.ts:216` (the drag-and-drop clamp) by finding its root cause (`superpowers:systematic-debugging`). It must pass 10 isolated runs in a row.
- [ ] **Step 5:** lane done (after W5-UI04 and W5-UI05). Run `full`, then `/devkit:ship-check`, then open the PR `lane/w5-polish → v1-local`.

### W5-UI04: Sales and donation labels in the web · S · depends on: W5-D01 merged · V1-A08, A13

- [ ] **Step 1:** merge `origin/v1-local`. Write the failing tests:
  - The danger ranking and the site inspector show "sales (undercounts demand when shelves were empty)" for a row whose `basis` is `sales`, and nothing for `demand` or null.
  - A location's why text with the donations line renders unchanged.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS). Restore the import guide's "everywhere" promise (`templates.py` is w5-data's file; ask the orchestrator). Commit.

### W5-UI05: W4 web follow-ups · S · depends on: none · V1-A20, A22

- [ ] **Step 1:** write the failing tests:
  - With the Overview card open, choosing a product in the product picker (Radix Select) keeps the new state, under the late-timer delay used in `overview.spec.ts`. That delay shows the same late focus return that #143 fixed for cards.
  - `run-e2e.sh` exits with a clear message when its Playwright port is already in use.
  - Connected runs never reuse an existing server (`playwright.config.ts`), because a leftover server serves a stale build.
  - The sidebar network selector stays inside the sidebar and never covers the page title at 1440 and 1280 (truncate the trigger; keep the full name in its accessible name).
  - Import step 1's column guides start collapsed, and the routes and inbound hints say "Optional." once.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS). Commit.

---

## Lane `w5-packaging` — test kit B, egress, measurement, README

Agent role: `solver-engineer` ("solver/data"), with Docker. It owns README.md and INSTALLATION.md for this wave. **`compose.yaml` is lead-only.** A change needed for a fresh machine is a CR, which the orchestrator lands.

### W5-PK01: `npm run test:docker` (group B) · M · depends on: none · V1-A21

**Files:** create `compose.test.yaml`, adapted from `b54ec7c` with mounts updated for the current tree; replace the W0-09 placeholder `scripts/testing/docker-tests.cjs`; test `scripts/testing/tests/docker-tests.test.cjs`.

- [ ] **Step 1:** write the failing tests:
  - `test_command_includes_require_no_skips`.
  - `test_compose_test_mounts_exist_in_tree`: every mount source path exists.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS).
- [ ] **Step 3:** run `npm run test:docker`. The full backend suite runs against PostgreSQL in Linux containers with 0 skipped. Commit.

### W5-PK02: Enforce story coverage · S · depends on: none · V1-A21

**Files:** modify `docs/testing/user-stories.json`, `scripts/testing/story-coverage.cjs`; create `docs/testing/README.md` (the v1 testing guide).

- [ ] **Step 1:** run `node scripts/testing/story-coverage.cjs --enforce` on the current tree. Expected: FAIL (exit 1), listing the IDs not yet mapped. Then fill in `user-stories.json` with every V1-A ID mapped to its tests, from the `@V1-Axx` and `covers:` tags.
- [ ] **Step 2:** run `node scripts/testing/story-coverage.cjs --enforce`. Expected: exit 0. For any ID that only has a human or manual run (A01, A18, A24 pull path), map it to its recorded-evidence check in `docs/testing/README.md`. That check must be an executable artifact check, not a skip.
- [ ] **Step 3:** commit.

### W5-PK03: Egress-logged journey and the secret checks · M · depends on: none · V1-A03, A04

**Files:** create `scripts/testing/egress-journey.cjs`, `scripts/testing/tests/egress-journey.test.cjs`.

- [ ] **Step 1:** write the failing tests: the harness's parser flags any destination outside the allowlist (`geocoding.geo.census.gov`, and `routes.googleapis.com` only when a key is set; ACS rates come from the bundled table, so `api.census.gov` is never called). It also flags the generated password, the proxy token or the Google key appearing in compose logs, in `.next` static output, or anywhere in the Git tree.
- [ ] **Step 2:** run them (FAIL). Implement: run the stack with outbound traffic captured (e.g. through a logging HTTP(S) proxy service in a `compose.test.yaml` profile), drive the A07–A16 journey on the samples plus one import of user addresses, and write `artifacts/egress/report.json`.
- [ ] **Step 3:** run them (PASS). Commit.

### W5-PK04: Measurements (hardware, bulk import, scale) · M · depends on: none · V1-A09, A17, A19

**Files:** create `scripts/bench/run-all.cjs`, `docs/pantrypulse/HARDWARE.md`.

- [ ] **Step 1:** write the failing test `scripts/testing/tests/bench-report.test.cjs`: `HARDWARE.md` contains measured first-run build time, idle RAM, peak RAM/CPU during the max-scale forecast and during each comparison mode, and the A09 import time. Each is tied to a commit and a timestamp and linked to its JSON artifact.
- [ ] **Step 2:** run `run-all.cjs` on the reference laptop. It runs `bench_import.py`, `bench_forecast.py` and `scripts/or/bench_v1.py`, plus `docker stats` sampling. Write HARDWARE.md from the results. Requirements come from measurement; the spec's provisional 4 cores / 8 GB / 15 GB get confirmed or corrected.
- [ ] **Step 3:** run the test (PASS). Commit.

### W5-PK05: README quickstart and the version pin check · M · depends on: W5-PK04 · V1-A18 (prep), A19, A24

**Files:** modify `README.md` (the quickstart at the top), `INSTALLATION.md` (contributor setups); create `scripts/testing/check-version-pin.cjs` and its test.

- [ ] **Step 1:** write the failing test `check-version-pin.test.cjs`: the README's version pin equals the `ghcr.io/gbw30/pantrypulse-*:<version>` tags in `compose.yaml`, and a mismatch exits 1.
- [ ] **Step 2:** write the README. It covers:
  - prerequisites: Docker Desktop with WSL 2 on Windows 11, or Docker Engine + Compose on Ubuntu 24.04, plus git;
  - `git clone`, then `docker compose up`. Until the first authorized release it is `docker compose up --build`, and the README says so;
  - the login line;
  - a first-run time from HARDWARE.md;
  - try the sample;
  - import your own data (link to the in-app template guide);
  - start over with `docker compose down -v`, plus a warning;
  - troubleshooting: port in use / `PP_WEB_PORT`, Docker memory for the 6-CPU / 8 GiB worker, the WSL 2 backend;
  - a link to HARDWARE.md. macOS is untested.
  - known limits from W2-06 ([decisions/W2-06-change-requests.md](decisions/W2-06-change-requests.md) §5): ids over 64 characters or containing `/` show as hashed batch ids; no abort or cleanup for abandoned imports; one worker; no live row count in import progress; no publish retry backoff.
  - Run `research-claims-check` on the README.
- [ ] **Step 3:** run the tests (PASS). Commit.
- [ ] **Step 4:** lane done. Run `full`, then `/devkit:ship-check`, then open the PR `lane/w5-packaging → v1-local`.
