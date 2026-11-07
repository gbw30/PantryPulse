# Wave 6 — Release and acceptance (orchestrator + Gabriel)

**Base:** `v1-local` after W5 merges (order: `w5-packaging` → `w5-polish`, mechanics as in W2). **Branch:** `w6/release`. Each outward-facing action needs **Gabriel's explicit go-ahead at that moment**: tag, image publish, making packages public (V1-D18).

### W6-01: Merge W5, then wire CI · M · depends on: W5 PRs · V1-A21, A24

**Files:** modify `.github/workflows/pantrypulse-ci.yml`; create `.github/workflows/release.yml`.

- [ ] **Step 1:** review and merge `w5-packaging`, then `w5-polish` (W2-01…W2-04 mechanics).
- [ ] **Step 2:** add to CI:
  - `npm run test:unit` (Vitest, already in `verify`);
  - `npm run test:docker`;
  - `node scripts/testing/story-coverage.cjs --enforce`;
  - `node scripts/testing/check-version-pin.cjs`.
- [ ] **Step 3:** add `release.yml`: on a version tag, build `linux/amd64` images for `pantrypulse-api` and `pantrypulse-web` and push them to GHCR. **Don't create a tag.**
- [ ] **Step 4:** open a PR. CI must be green with every new step running, not skipped. Merge with Gabriel's OK.

### W6-02: Release candidate freeze · S · depends on: W6-01 · V1-A22

- [ ] **Step 1:** choose the candidate SHA on `v1-local`. From now on only demonstrated blockers land (the CLAUDE.md release freeze).
- [ ] **Step 2:** on the candidate, run `node scripts/quality/run.cjs full`, then `PP_RUN_CONNECTED=1 PP_E2E_PRODUCTION=1 node scripts/quality/run.cjs e2e`, then `npm run test:docker`. All must PASS with 0 skipped. Record the commit, the commands and the times in ACCEPTANCE-MATRIX (V1-A22).
- [ ] **Step 3:** run the `verifier` and `adversarial-reviewer` one last time on the candidate. Both report per V1-A ID.

### W6-03: Clean-machine install, build path · M · depends on: W6-02 · V1-A01, A02, A24 (build)

- [ ] **Step 1 (Gabriel):** on a clean Windows 11 machine or VM with only Docker Desktop (WSL 2) and git: `git clone` the candidate, then `docker compose up --build`. Record the commit, the Docker version, the elapsed time to the login page, and a screenshot. Then check A02: only port 3000 is published, `PP_WEB_PORT=3555` works, a restart keeps the data, and a second `up` doesn't duplicate the seed.
- [ ] **Step 2 (orchestrator or Gabriel):** the same on a clean Ubuntu 24.04 machine or VM.
- [ ] **Step 3:** record both runs in ACCEPTANCE-MATRIX as V1-A01 and the build part of V1-A24, with links to the evidence. Put the first-run times in the README through a small PR.

### W6-04: Newcomer README runs · M · depends on: W6-03 · V1-A18

- [ ] **Step 1 (Gabriel arranges):** a person who has never seen the repo follows only the README, on Windows 11 and on Linux: install → sample → import their own template set (including `inbound.csv` and `donation_history.csv`) → forecast → compare → export. Record observed-run notes per OS: each place they got stuck, and the time.
- [ ] **Step 2:** fix README gaps through small PRs, then record V1-A18.

### W6-05: Live keyed checks · S · depends on: W6-02 · V1-A10, A11 (live parts)

- [ ] **Step 1:** one live Census run on real public-building Florida addresses (V1-A10), and one live Google run with **Gabriel's own key**, entered by Gabriel in Settings (V1-A11). Confirm the lookup-count preview, the caching, the labels, and that the key is absent from the logs and the bundle (rerun the W5-PK03 harness with the key set).

### W6-06: Authorized release, pull path · S · depends on: W6-03, explicit go-ahead · V1-A24

- [ ] **Step 1:** ask Gabriel: "Create tag `v1.0.0` on <SHA>?" Only after a yes: tag and push. `release.yml` publishes the images.
- [ ] **Step 2:** ask Gabriel: "Make the `pantrypulse-api` and `pantrypulse-web` GHCR packages public?" Only after a yes.
- [ ] **Step 3 (Gabriel):** on clean Windows 11 and Ubuntu machines, plain `docker compose up` pulls the images with no local build. Record the first-run times, and update the README so that plain `up` is the default.
- [ ] **Step 4:** final report. ACCEPTANCE-MATRIX shows V1-A01…V1-A24 with evidence, or an explicit open item. Update BOARD.md.
