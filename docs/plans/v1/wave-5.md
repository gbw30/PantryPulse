# Wave 5 — lanes `w5-polish`, `w5-packaging`

**Base:** the `v1-local` head after W4 (`{{BASE_SHA}}`). **Mode:** B for both lanes. Same rules as wave 1 ([ORCHESTRATION.md §8](ORCHESTRATION.md#8-rules-every-lane-inherits)).

---

## Lane `w5-polish` — UI polish with devkit stack-web

Agent role: `frontend-engineer`. **Required skills:** `/jmo-workflow:better-ui` (surfaces, icons, alignment), `/jmo-workflow:animate` (purposeful motion only) and the project skill `visual-review`. These come from the devkit `stack-web` bundle. If they don't load in this session, **stop and report** (Gabriel's 2026-11-04 decision). ART-DIRECTION.md and ADR 0002 decide the direction; these skills are method only (CLAUDE.md). This lane owns the tokens in `globals.css` for this wave.

### W5-UI01: Visual baseline · S · depends on: none · V1-A20

- [ ] **Step 1:** use `visual-review` to take screenshots of the import, settings, atlas ranking, forecast trust, comparison, decisions and print screens at 1440×900, 1280×720 and 390×844, in light and dark, into `docs/pantrypulse/visual-evidence/v1-before/`. Commit.

### W5-UI02: Fix the ux-critic findings (list filled in at W4-04) · M · depends on: W5-UI01 · V1-A20

For each finding: write the e2e or unit test that pins the repair as the acceptance check (e.g. "CTA visible without scrolling at 390×844", "quantity not clipped", "band meaning has a text label"), run it and see it fail, then fix it with `/jmo-workflow:better-ui`, run it and see it pass, and commit.

- [ ] W5-UI02.1 … (filled at W4-04)

### W5-UI03: Motion and the final evidence · S–M · depends on: W5-UI02 · V1-A20

- [ ] **Step 1:** write the failing test `apps/web/tests/e2e/v1-motion.spec.ts`: `@V1-A20 every animation is finite, ≤ 1s, and absent under prefers-reduced-motion`. Reuse the finite-animation helper from PR #100.
- [ ] **Step 2:** add or adjust motion only where `/jmo-workflow:animate` finds a purpose. Run the test (PASS).
- [ ] **Step 3:** take the `v1-after/` screenshots and run `v1-a11y.spec.ts` and `v1-full-journey.spec.ts` (PASS).
- [ ] **Step 4:** fix the known flaky `overview-layout.spec.ts:216` (the drag-and-drop clamp) by finding its root cause (`superpowers:systematic-debugging`). It must pass 10 isolated runs in a row.
- [ ] **Step 5:** lane done. Run `full`, then `/devkit:ship-check`, then open the PR `lane/w5-polish → v1-local`.

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
  - Run `research-claims-check` on the README.
- [ ] **Step 3:** run the tests (PASS). Commit.
- [ ] **Step 4:** lane done. Run `full`, then `/devkit:ship-check`, then open the PR `lane/w5-packaging → v1-local`.
