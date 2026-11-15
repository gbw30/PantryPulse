# W5 change requests and decisions

W5 ran four lanes in parallel: `w5-polish`, `w5-screens`, `w5-packaging` and `w5-data`. The base was v1-local `81c551b`, after the W5-L01 contract #147.

Each lane ran as a separate CLI session in `~/code/PantryPulse-<lane>` on `lane/w5-<lane>`. Before merging, every lane PR got an independent verifier pass, a green CI with 0 skipped tests, and a merge pinned with `--match-head-commit`. Gabriel decided every item below and approved every push and merge.

## 1. Merges

| PR | What | Merge |
|---|---|---|
| #149 | W5-L02 (lead): the plan window and effect period on `DecisionActions` (from CR-w5-screens-3) | `372a3cb` |
| #150 | W5-D01, merged ahead of its lane from lead branch `w5/data-d01`, with the lane's fix cherry-picked (`e2a3000`) | `a6d08a1` |
| #152 | w5-screens: UI02.1–.3, SC01, SC02 and the D03 web copy | `b660a83` |
| #151 | w5-data: D02–D04, CR-w5-data-1 (revised) and the D02 follow-up | `3a7d4f9` |
| #153 | w5-screens follow-up: verifier findings F1–F3, multi-word units, plural from the shown number | `2a42698` |
| #154 | Lead: the module supervisor heartbeat in the import-job and comparison suites (ESC-w5-packaging-1) | `8b4fff9` |
| #155 | w5-polish: UI01–UI05, CR-w5-data-2, CR-w5-screens-4 and the wave-end ux-critic batch | `eb21003` |
| #156 | w5-packaging: PK01–PK05, CR-w5-packaging-1–3, the quiet W5-PK04 re-measure at `d92021b`, and the code-review fixes (the 6-CPU requirement, repo-relative bench paths, the memory wording) | `cadd138` |
| #157 | w5-packaging follow-up: code-review items 2, 4 and 7 (egress staleness inputs, broken checkers fail `--enforce`, the version pin in V1-A24's checks) | `d751453` |
| pending | Lead: this close-out | |

## 2. Cross-lane change requests (Gabriel, 2026-11-12)

The rule: when one lane's change breaks a file another lane owns, the lane that caused it makes exactly the approved edit, as its own commit, and the owner leaves that file alone until the merge. That way the cause and its fix ship in one PR, and each PR's CI passes on its own. Contract changes stay with the lead.

| CR | Change | Done in |
|---|---|---|
| CR-w5-screens-1 | `data-label.spec.ts` stops expecting the legacy block that UI02.1 removed | screens `0790cf1` |
| CR-w5-screens-2 | The connected journey reads the collapsed effects rows | screens `5448824` |
| CR-w5-screens-3 | Decisions names the plan window and the effect period. Dates go in the response only, not in the CSV export | lead W5-L02 (#149) |
| CR-w5-screens-4 | The Overview reuses `data-explorer/format`'s pluralize instead of its own copy | polish `6657198`, after the screens merge |
| CR-w5-screens-5 | `action-card.test.tsx` gets UI02.3's new prop | screens. Polish confirmed it on the merged tree |
| CR-w5-packaging-1 | `HARDWARE.md` is added to the docs-only `TEST_READ` list | packaging `0286cc0` |
| CR-w5-packaging-2 | `package.json` `test:config` also runs `scripts/testing/tests/*.test.cjs`, so the packaging checkers run in the quick gate and in CI (verifier finding F1) | packaging `5907f53` |
| CR-w5-packaging-3 | CI's `verify` job checks out the full history (`fetch-depth: 0`), so `bench-report.test.cjs` can confirm that the bench commit `d92021b` exists. With a depth-1 checkout, 70 of 71 tests passed. Gabriel rejected skipping the check in shallow clones, because a skipped check isn't evidence | packaging `7af6359` |
| CR-w5-data-1 | `bench_import.py` stops writing hub demand, which D02 refuses. First approved as 1 hub (4,455,000 rows), then revised: validation doesn't require a hub, so the bench writes 100 pantries and no hub, back to 4,500,000 rows | data `09b6aba` |
| CR-w5-data-2 | The import page reads the run when a commit answers 409 `IMPORT_ALREADY_FINISHED` | polish `43df904` |

## 3. Product decisions (2026-11-12)

- **Supply links (PP-52 #4 against WCAG 2.2.2):**
  - The Overview's always-on link flow stays, and the map controls gain a "Pause link animation" toggle. Its name is fixed, `aria-pressed` shows whether it's paused, and the choice is saved in `localStorage` per browser.
  - `v1-motion.spec.ts` exempts only `.pp-supply-flow`. Every other animation stays finite and at most 1 s.
- **D03 copy:** the web tells "not evaluated, zero actual demand" apart from "needs 35+ days". Screens did this in W5-UI02.1b.
- **Sales label:** the import guide names the three places the label shows: "the Forecast trust panels, the danger ranking and the site inspector" (data `8691c72`). It never says "everywhere", because Scenario Lab and Decisions don't show the label.
  - Gabriel accepted that v1-local briefly names labels that polish adds later. The W6 candidate is chosen after polish merges.
- **PR #151 review:**
  - Items 5 and 6 fixed in `3bd1cde`: the hub/DC refusal names "pantries" or "stores" from the network's mode, and validation uses one shared `HUB_ROLES`.
  - Item 7: stored backtests are not backfilled. The lead's close-out corrects the `BacktestScore` docstring (`6dde14d`).

## 4. Decisions on 2026-11-14

- **#152 merged before its verifier notes were fixed;** the fixes followed in #153:
  - F1: "Open in new tab" from the Print link's context menu saves the selection.
  - F2/F3: free-text units are pluralized only when they are plain words. Abbreviations, all-caps codes and "fl oz" stay as typed.
  - Then a second round: a multi-word unit is pluralized on its last word, and singular or plural follows the number as shown ("1 box" for 1.04).
- **The Overview follows the shared plural rule** (polish `d779608`): singular when the number shown is "1", and "lb" becomes "lbs" everywhere.
- **The Retail first view (UI02.5) is fixed in polish** (`8f93079`). The legend moved beside the map at lg, the List/Table toggle moved into the heading row, and the "Not on the map" list moved after the ranking.
- **ESC-w5-packaging-1:**
  - The cause: `test_import_job.py` and `test_comparison_v3_postgres.py` stamped their module supervisor's heartbeat only once. After 15 s, admission refused new jobs, so under load the quick gate failed.
  - The lead fixed it with a background heartbeat (#154). The intermediate per-test refresh was caught by the verifier: a long test body still failed.
- **The W5-PK04 bench was re-run on a quiet machine** at `d92021b`. Build 60 s, first start 24 s, the 4.5 M-row import 53 s, Pantry comparison 3 min 25 s. The loaded run (`d1d9800`) is superseded.
- **The packaging verifier failed `9366474`.** Gabriel approved every fix:
  - Truthful docs:
    - F3, the blocker: the README claimed Linux was "tested on Ubuntu 24.04", which never happened.
    - F2: the hardware figures now name the artifact they came from.
    - F4: `HARDWARE.md` claims only what was measured.
  - Stronger checks:
    - F6: the version pin no longer accepts `latest`.
    - F7: story coverage runs its evidence checks instead of only checking that a path exists.
    - F8: the time format no longer prints "1 min 60 s".
    - F9: `compose.test.yaml` names its project.
  - Egress, F5: the scan covers more secrets, response bodies and IPv6. It captures only the project bridge and was re-run (`47de1bb`, `30037e5`, evidence `8b04600`).
  - F1 became CR-w5-packaging-2 (§2).
  - Fixes in `5907f53`, `5226a6c`, `47de1bb` and `30037e5`.
- **The wave-end ux-critic findings:**
  - Fixed in polish: the legend layout (it was clipped while the inspector is open at 1440, and bottom-aligned at 1440; a margin under rank #3 was added). The Settings screen now hides the poverty/SNAP fields and "Exclude from EGP" for Retail networks.
  - "each" stays as the user's own unit. Everything else becomes a known limitation (§5).

## 4a. Decisions on 2026-11-15

- **CR-w5-packaging-3** (§2): CI's `verify` job needs the full history. Gabriel chose it over skipping the check in shallow clones.
- **Polish (#155):** the verifier found PASS WITH NOTES at `5680626`, with no code defects.
  - Its own full gate stopped at the web build: Turbopack won't follow the verify worktree's symlinked `node_modules`. The build, contract drift and migrations were proven by the PR's CI `full` job instead (2269 backend tests with no skips, 264 e2e).
  - The ux-critic confirmed both legend fixes, and Retail #3 ends 27–31 px above the fold.
  - Its Medium finding: at 1280×720 the Retail map shrinks to about 225×127 px with about 20 overlapping markers. Gabriel folded it into the atlas redesign below rather than a quick fix.
- **Packaging (#156):** the round-2 re-verify gave PASS WITH NOTES. F1–F9 and CR-3 are fixed.
  - The lane's local `/code-review` found 10 items. Gabriel's calls:
    - Fixed in #156:
      - Item 1: the README said 4 CPU cores were enough, but the worker's `cpus: 6` can't start on fewer. Docker refuses a CPU limit above what it has; the lane reproduced this. The README and HARDWARE.md now say 6 CPUs, generated from `compose.yaml`.
      - Item 9: the bench JSON in this public repo stored absolute home-directory paths. The commands are now relative, re-rendered with no measured value changed.
      - The memory row no longer claims the worker reaches its 8 GiB ceiling when Docker has exactly 8 GiB.
    - A follow-up PR before W6: items 2, 4 and 7.
    - Known limitations: items 3, 5, 6, 8 and 10 (§5).
  - The lead also replaced two home-directory paths in `spikes/S3-docker.md`. Git history keeps them.
- **4-CPU machines (W6):** W6 measures a run capped at 4 CPUs. If it stays within the solver and forecast ceilings, the lead adds an optional worker CPU setting, default 6.
- **The atlas redesign (Gabriel, 2026-11-15):** the Overview must not overload a first-time user. The atlas becomes a map with the pantries or stores plotted, where the user can move straight from one location to the next or pan around the map. The design is being agreed with Gabriel; it lands before the W6 candidate is chosen.

## 5. Known limitations carried into W6

- **Imports and forecasts:**
  - A cancelled or stopped import can be committed again (N3, by design).
  - A series with 35+ days but no scoreable actuals reads "needs 35+ days".
- **Units:** "bag of rice" reads "bag of rices", because only the last word is pluralized.
- **Print selection:** a long-press on iPhone or iPad may not save the Print selection. It's unverified: iOS isn't documented to fire `contextmenu`.
- **Network selector:** it cuts the end of long network names, including "(sample)".
- **Screenshot coverage:**
  - The comparison screenshots were captured scrolled, so Scenario Lab's first view at 1280×720 is visually unverified.
  - The sales label on Forecast trust and the site inspector was not captured for Retail.
  - The `v1-after` Settings captures show Retail (Heronfield Market) with the Pantry-only fields hidden. No Pantry Settings capture exists, so Pantry Settings has unit-test evidence only.
- **Phone width (390 px):**
  - Retail's danger ranking sits below the map.
  - Forecast trust is very long, with its summary at the bottom.
  - The routes table is cut off with no scroll hint.
- **Copy:**
  - The import guide repeats one sentence.
  - The Retail basis label repeats on every row.
- **Load-sensitive tests, not reproduced alone:**
  - `decisions-view.test.tsx:111` (storage-full);
  - `overview-layout.spec.ts:216` and `:259` (the grip-handle resize takes 14–17 s alone);
  - `test_actions_equal_the_full_network_replay[bench-retail…]`.
- **Overview (ux-critic, 2026-11-15):**
  - With the inspector open at 1440, the map stops short of the legend's right edge.
  - The WATER table has no "Expiring unsold" column, so its columns don't line up with the other tables.
  - The selected site isn't marked on the map or in the list.
  - In full-page captures the sidebar background stops at the fold. Check this in a live browser.
  - The geometry tests don't assert directly that the legend sits under the map, that the toggle is in the heading row, or the list order.
- **Packaging, for W6:**
  - Egress evidence never fails a gate: a failed or stale artifact only reads `pending`. W6 re-runs the egress journey on the candidate.
  - A01, A18 and A24 stay pending until W6's recorded runs.
  - The CPU requirement is V1-SPEC's provisional figure plus the compose limit, measured on one Windows 11 machine. Ubuntu and macOS are not measured.
  - `INSTALLATION.md:13` says "Docker only (any OS…)", which isn't measured.
  - A `--depth 1` clone fails 1 of 83 config tests.
  - The hand-typed-figure guard misses spellings such as "120 seconds" or "1,454 MB".
  - The sniffer skips ICMP and IPv4 UDP packets with fewer than 6 payload bytes.
  - Code-review items:
    - 3: the A24/A01 recorded-run path rules;
    - 5: A10 accepts an enrichment that ended `failed`;
    - 6: a stale local `report.json` is left behind after an early failure;
    - 8: recorded runs never go stale;
    - 10: the duplicated shell helpers have drifted.
  - Delta notes:
    - N1: the `renderSummary` docstring;
    - N2: "8 GiB" is hard-coded beside the generated `mem_limit`;
    - N3: `relativeCommands` leaves `--out=/abs` absolute.
- **Packaging follow-up (#157, verifier PASS WITH NOTES):**
  - A negative or fractional `PP_STORY_CHECK_TIMEOUT_MS` throws a RangeError (it fails safe).
  - Egress staleness ignores uncommitted changes, and the egress harness files themselves aren't stale triggers.
  - Wording nits, such as "1 stack sources".
  - On v1-local, A03 and A04 now read pending, because polish changed `apps/` after the egress run at `9541f6f`.
- **Research claims:** `GET /api/v1/allocation-methodology` returns no DOI, date or adapted constructs (`planning.py:37-50`). W6 runs `research-claims-check` on it.
- **Post-v1 cleanup:**
  - `scenario.py:45`, `forecasting/network.py:58` and `enrichment/distance.py:13` hardcode their own sender role sets instead of using `HUB_ROLES`.
  - `test_forecast_api_postgres.py`, `test_job_queue.py:57` and `test_supervisor.py:393` keep their own heartbeat helpers.
  - `heartbeating` doesn't assert that its thread joined.

## 6. Process findings

- **The PP19 flag was missing:**
  - `.env.lane` lacked `PP19_TEST_SCHEMA_ISOLATION=1`, so three PostgreSQL integration modules skipped silently, and the gates print no counts.
  - Packaging's first gates at `0daecf8` ran without it; it re-ran them.
  - The README's isolation section now lists the flag. Count skips with `pytest -rs`.
- **Merging one task ahead of its lane:** pin a lead branch at that task's commit and cherry-pick its fix with `-x`. The lane's later merge of v1-local was clean (`abe117d`).
- **Attribution:** Gabriel's rule is no attribution lines in commits or PR bodies. Lane harness reminders added "Generated with" to #151 and #152; both were removed with `gh api -X PATCH`, because `gh pr edit` fails on this repo with a classic-projects GraphQL error.
- **No CI on v1-local:** CI runs on PRs only, not on pushes to v1-local. The lead runs the full gate on the merged candidate at wave close.
- **`ruff format`:** don't run it on a whole existing file. The project enforces `ruff check` only, and formatting rewrote 56 unrelated lines in W5-L02.
