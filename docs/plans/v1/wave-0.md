# Wave 0 — Foundation (orchestrator, sequential)

**Base:** `v1-local` at `71cc435`. **Branch:** `w0/foundation` (one PR into `v1-local`, merged with Gabriel's OK). **Mode:** the orchestrator works directly, except spikes S1 and S4, which run in-session (mode A) on throwaway branches. **Exit:** the re-plan gate W0-10, approved by Gabriel.

Every task follows the TDD loop in [ORCHESTRATION.md §8](ORCHESTRATION.md#8-rules-every-lane-inherits). Each check below names the failing test to write first and what it asserts.

---

### W0-01: Environment cleanup and doc truth · size S · depends on: none · V1-A22

**Goal:** a Docker daemon with no stale `pantrypulse` project, and a CLAUDE.md that tells lanes the truth.

**Files:** modify `CLAUDE.md`. Commit the already-modified `.claude/settings.json` and `.claude/agents/frontend-engineer.md` (stack-web replaces frontend-design).

- [ ] **Step 1: Check that the stale project is present.** Run `docker ps -a --filter label=com.docker.compose.project=pantrypulse --format '{{.Names}}'`. Expected: lists `pantrypulse-api-1`, `pantrypulse-worker-1`, `pantrypulse-postgres-1`.
- [ ] **Step 2: Remove the stale containers** (approved by Gabriel 2026-11-04): `docker stop` then `docker rm` on `pantrypulse-api-1`, `pantrypulse-worker-1`, `pantrypulse-postgres-1`, `pp-local-api`, `pp-local-worker`.
  - **Keep** the volumes `pantrypulse_pgdata` and `pantrypulse-chronos-model-cache` until Gabriel decides what happens to them.
  - **Keep** `pp-ci-postgres` (the shared lane test database).
  - Re-run Step 1. Expected: empty.
- [ ] **Step 3: Update CLAUDE.md** (approved 2026-11-04):
  - Migration head `ppvp_0007` (and later `ppv1_0008`, after W0-07).
  - Chronos is in the production registry behind `PP_CHRONOS_ENABLED`.
  - Drop the 10-minute council cap.
  - Replace "Feature freeze at hour 41" with "Release freeze: after the candidate SHA is chosen in W6, only demonstrated blockers land".
  - Point "Current authority" at V1-SPEC and `docs/plans/v1/`.
- [ ] **Step 4: Run the config tests.** `node --test scripts/quality/tests/*.test.cjs`. Expected: `# pass 20`, `# fail 0`.
- [ ] **Step 5: Commit** `CLAUDE.md .claude/settings.json .claude/agents/frontend-engineer.md` with the message `chore: v1 CLAUDE.md truth, stack-web replaces frontend-design`.

### W0-02: Spike S1, optimizer at 100 × 500 · size M · depends on: W0-01 · informs V1-A14, A15, A17

**Mode A:** dispatch `solver-engineer` in the background with a task packet. **Branch:** `spike/w0-s1` (never merged). **Output:** `docs/plans/v1/spikes/S1-optimizer.md`, committed by the orchestrator on `w0/foundation`.

**Packet:** "Answer V1-SPEC §12 item 1."
- Build a synthetic 100-location × 500-product scenario generator: Pantry with EGP RP group means over ~100 receivers per product, and Retail with a throwaway `w_exp × expired + w_lost × lost` objective.
- Measure three variants under `PP_` ceilings of 300 s search / 330 s method / 690 s comparison and the worker limit of 6 CPU / 8 GiB:
  - (a) monolithic CP-SAT;
  - (b) decomposed by product;
  - (c) at-risk products only;
  - each with k = 10 nearest candidate routes within 150 miles.
- For each variant, record wall time, native status, the result of the independent verifier `services/optimization/verify.py`, and peak RSS (`/usr/bin/time -v`).
- Return a table and a recommendation in V1-D15 order:
  1. at-risk only;
  2. lower the envelope (to what);
  3. raise ceilings, only with evidence.
- Cite exact commands. Don't touch `v1-local`.

- [ ] **Step 1:** dispatch. Afterwards, read the report and re-run one variant's command yourself.
- [ ] **Step 2:** the report has measured numbers for (a), (b) and (c) in both modes, plus a one-line verdict: "V1-D15 step reached: none | 1 | 2 (envelope X × Y) | 3". Commit the report.

### W0-03: Spike S4, bulk import at 4.5 M rows · size M · depends on: W0-01 · informs V1-A07, A09

**Mode A:** `solver-engineer` ("solver/data" in CLAUDE.md). **Branch:** `spike/w0-s4`. **Output:** `docs/plans/v1/spikes/S4-bulk-import.md`.

**Packet:**
- Generate a maximum-envelope `demand_history.csv`: 100 × 500 × 90 = 4.5 M rows, with about 2% blank quantities.
- Time each stage on this laptop:
  - (a) a streamed multipart upload through FastAPI. `python-multipart` is already a dependency; `main.py` limits request bodies to 64 KB.
  - (b) the Next.js same-origin proxy `apps/web/src/app/api/v1/[...path]/route.ts`: does it buffer the body, and what is its limit?
  - (c) staging through PostgreSQL `COPY`;
  - (d) set-based validation SQL for each error class in V1-SPEC §6.1;
  - (e) the all-or-nothing commit.
- Record peak RAM.
- Recommend:
  - an upload mechanism: a single streamed upload, or chunked uploads plus a final commit;
  - whether uploads bypass the proxy or the proxy streams;
  - a staging-table shape;
  - the job contract fields: phases and progress units.

- [ ] **Step 1:** dispatch. Read the report, then re-run the (c) + (d) timing command yourself.
- [ ] **Step 2:** the report gives seconds and peak MB per stage, and the recommendation feeds W0-07 and W0-08. Commit it.

### W0-04: Full local stack with one start command · size M · depends on: W0-01 · V1-A02, A24 (build path)

**Files:**
- Modify: `compose.yaml`, `apps/api/Dockerfile`, `.gitignore`, `INSTALLATION.md` (contributor section only).
- Create: `compose.dev.yaml` (the old dev postgres on 55432 plus the `api` profile), `apps/web/Dockerfile` (Next.js standalone), `.env.example`, `.gitattributes`.
- Test: `scripts/quality/tests/local-stack.test.cjs`.
- Keep `compose.compute.yaml`, `compose.forecast.yaml`, `compose.chronos.yaml` and `compose.demo.yaml`, and update their references in INSTALLATION.md.

- [ ] **Step 1: Write the failing test** `local-stack.test.cjs`. It runs `docker compose -f compose.yaml config --format json`, with and without `PP_WEB_PORT=3555`, and asserts:
  - the service set is exactly `postgres, migrate, seed, api, worker, web`;
  - only `web` has `ports`; that port has `host_ip: 127.0.0.1` and `published: "3000"`, or `"3555"` with the env var set;
  - `migrate`, `seed`, `api` and `worker` all use `image: ghcr.io/gbw30/pantrypulse-api:<version>`, and `web` uses `ghcr.io/gbw30/pantrypulse-web:<version>`. Every app service also has a `build` section;
  - `api` and `worker` `depends_on` both `migrate` and `seed` with `condition: service_completed_successfully`;
  - the postgres volume key is not `pgdata`, so the old `pantrypulse_pgdata` volume is never reused;
  - `.gitattributes` contains `*.sh text eol=lf` and covers the Docker entrypoints.
- [ ] **Step 2: Run** `node --test scripts/quality/tests/local-stack.test.cjs`. Expected: FAIL (service set mismatch).
- [ ] **Step 3: Implement** the compose stack, Dockerfiles, `.gitattributes`, `.gitignore` (`.pantrypulse/`) and `.env.example` (only `PP_WEB_PORT` and optional values; no secrets).
- [ ] **Step 4: Run** the test. Expected: PASS. Then run the stack:
  - `docker compose up --build -d --wait`, then `curl -sf http://127.0.0.1:3000/` returns 200.
  - `docker compose restart`: data survives.
  - A second `docker compose up -d` creates no duplicate seed rows; check with a row count of the organization/network tables.
- [ ] **Step 5: Commit.**

### W0-05: Generated local login and seed skeleton · size M · depends on: W0-04 · V1-A04, A05 (skeleton)

**Files:**
- Create: `apps/api/scripts/local_bootstrap.py` (run by `seed`), `apps/api/scripts/seed_local.py`, and `apps/api/app/services/samples/__init__.py`. The last one is a stub, `ensure_samples(session, today: date) -> SeedReport` returning `SeedReport(loaded=())`; it is owned by `w3-samples` in W3.
- Test: `apps/api/tests/test_local_bootstrap.py`.

- [ ] **Step 1: Write the failing tests:**
  - `test_first_run_generates_credentials_once`: writes `.pantrypulse/local-login.txt` with mode `0o600`, containing username `local` and a random password; stores only the scrypt hash in the database. A second run changes neither.
  - `test_password_never_logged`: `caplog` and `capsys` don't contain the password.
  - `test_proxy_token_generated_and_shared_without_shell`: the token reaches `web` through a file on a shared volume, never through `eval` or an env print.
  - `test_hash_with_dollar_round_trips`: the stored hash contains `$` and verifies.
  - `test_startup_line`: the stdout line is exactly `Open http://127.0.0.1:3000 — username: local — password: see .pantrypulse/local-login.txt`, with the port taken from `PP_WEB_PORT`.
  - `test_seed_calls_ensure_samples_and_never_resets`.
- [ ] **Step 2: Run** `uv run --frozen --directory apps/api pytest -q tests/test_local_bootstrap.py`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement.** Keep presenter auth and CSRF in the backend, with no bypass.
- [ ] **Step 4: Run** the tests (PASS), then `docker compose up --build -d --wait` and log in through the browser with the generated password. Then: `docker compose logs | grep -c "<password>"` → `0`, and `grep -r "<password>" apps/web/.next` (inside the image) → no match.
- [ ] **Step 5: Commit.**

### W0-06: Spike S3, cross-platform run · size S · depends on: W0-05 · pre-evidence for V1-A01, A24 (not a PASS)

**Output:** `docs/plans/v1/spikes/S3-docker.md`.

- [ ] **Step 1 (Gabriel, Windows 11 PowerShell):** `git clone` the `w0/foundation` branch to a Windows path, then run `docker compose up --build`. Record: Docker Desktop version and memory setting, whether WSL 2 is the backend, elapsed time to the login page, any CRLF error, and a screenshot.
- [ ] **Step 2 (orchestrator, WSL Ubuntu):** the same from a fresh clone in `~/tmp-s3-clone`, with `COMPOSE_PROJECT_NAME=pp-s3` and `PP_WEB_PORT=3999`.
- [ ] **Step 3:** write both runs into the report, with the commit, versions and times. Fix any CRLF or entrypoint problem in this task, then commit.

### W0-07: Schema freeze, migration `ppv1_0008` · size M · depends on: W0-03 · V1-A07, A08, A10, A11, A23 (constraints)

**Files:**
- Create: `apps/api/migrations/versions/ppv1_0008_networks.py` (+ `.sql` if that's the house style) and `apps/api/app/models/networks.py`.
- Modify: `apps/api/app/models/__init__.py`.
- Create the decision record `docs/plans/v1/decisions/W0-network-model.md`.
- Test: `apps/api/tests/integration/test_v1_schema.py`.

**Decision to record first:** how a v1 network maps to the existing `organizations` tenant. **Recommended:** one organization per network, plus the local presenter session may read every network of the install. That way `forecast.v1`, the projection, the scenario code and the dashboard keep their organization scoping unchanged.

The schema must hold (table names are decided here):
- network: mode (immutable), timezone and `as_of_date`;
- dataset version: immutable, plus one audited import event;
- location: role, address, coordinates, tract, `poverty_rate` and `snap_rate` with source table, year and `fetched_at`, plus a manual override or exclusion;
- product: unit, `unit_value_usd` and `handling_units_per_unit`;
- batch: quantity ≥ 0 integer; exactly one of `expiry_date` or `non_expiring`;
- demand/sales history: nullable quantity, `basis IN ('demand','sales')`;
- donation history: nullable quantity, with 0 kept distinct from missing;
- inbound: within the horizon or marked outside it;
- routes: `method`, `fetched_at`, an override flag and `disabled`;
- Google distance cache;
- local settings secret (the Google key): never selected by any read model;
- import staging plus import errors (file, line, column, reason), shaped by S4;
- backtest scores.

- [ ] **Step 1: Write the failing tests:**
  - `test_upgrade_head_on_fresh_database`;
  - `test_downgrade_to_ppvp_0007_and_up_again`;
  - `test_batch_quantity_nonnegative_integer`;
  - `test_expiry_xor_non_expiring`;
  - `test_demand_quantity_nullable_and_basis_checked`;
  - `test_donation_zero_distinct_from_null`;
  - `test_network_mode_immutable`;
  - `test_dataset_version_immutable`.
  - All use `PP_TEST_DATABASE_URL`, and must not skip.
- [ ] **Step 2: Run** them. Expected: FAIL (revision missing).
- [ ] **Step 3: Implement** the migration and the models.
- [ ] **Step 4: Run** the tests (PASS), then `uv run --frozen --directory apps/api pytest -q tests/test_merged_migrations.py tests/integration/test_job_migrations.py tests/integration/test_operational_postgres.py` (PASS, 0 skipped).
- [ ] **Step 5: Commit**, and update the migration head in CLAUDE.md.

### W0-08: Contract freeze · size L, done as 08a + 08b · depends on: W0-02, W0-07 · prerequisite for every lane; V1-A22

**08a: schemas, routers, caps**

**Files:**
- Create: `apps/api/app/schemas/v1_envelope.py`, `v1_networks.py`, `v1_imports.py`, `v1_enrichment.py`, `v1_planning.py`; `apps/api/app/routers/v1_networks.py`, `v1_imports.py`, `v1_settings.py`, `v1_decisions.py`; and the stub modules named in [README "Service functions"](README.md#interfaces-frozen-in-w0-08).
- Modify: `apps/api/app/main.py` (include the routers; exempt the upload route from the 64 KB body limit the way S4 recommends), `apps/api/app/schemas/or_inputs.py` (caps), `apps/api/app/routers/optimization.py` and `forecasts.py` (`methods[]`, `measure`, `network_id`).
- Test: `apps/api/tests/test_v1_contract.py`.

- [ ] **Step 1: Write the failing tests:**
  - `test_every_v1_route_in_openapi`: compares the method+path list with the README table.
  - `test_unimplemented_routes_return_501_with_task_id`: e.g. `GET /api/v1/networks` returns `{"error": {"code": "not_implemented", "task": "W1-D05"}}`.
  - `test_scenario_caps`: 100 locations and 500 products accepted; 101 or 501 rejected with a message that names the limit. [conditional on S1: use the lowered envelope if S1 reached V1-D15 step 2]
  - `test_method_sets_per_mode`: Pantry accepts exactly its five methods, Retail exactly its three; a cross-mode method returns 422.
  - `test_transfer_mode_still_required`.
- [ ] **Step 2: Run** `uv run --frozen --directory apps/api pytest -q tests/test_v1_contract.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the schemas and thin routers. Each router only parses, authorizes and calls the lane's service function.
- [ ] **Step 4: Run** the tests (PASS) plus the full backend suite: `uv run --frozen --directory apps/api pytest -q` with 0 skipped, which keeps the existing v2 flow green.
- [ ] **Step 5: Commit.**

**08b: job registrations, examples, generated contract**

**Files:**
- Modify: `apps/api/app/workers/production.py` (register `import.v1`, `enrichment.v1`, `routes-google.v1`, `or-comparison.v3`, with handlers in the lane-owned modules raising `NotImplementedV1`), `scripts/quality/check-contracts.cjs` (also validate the examples), `packages/contracts/openapi.json`, `packages/contracts/src/schema.d.ts`, `packages/contracts/README.md`.
- Create: `packages/contracts/examples/v1/*.json` (one per response schema) and `apps/api/scripts/validate_contract_examples.py`.

- [ ] **Step 1: Write the failing tests:**
  - `test_examples_validate` in `test_v1_contract.py`: every examples file parses with its model, and every v1 response model has an example.
  - `test_v1_job_kinds_registered` in `tests/workers/`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement**, then regenerate: `apps/api/.venv/bin/python apps/api/scripts/export_openapi.py --stdout > packages/contracts/openapi.json` and `node node_modules/openapi-typescript/bin/cli.js packages/contracts/openapi.json -o packages/contracts/src/schema.d.ts`.
- [ ] **Step 4: Run** `npm run contracts:check --workspace @pantrypulse/web` (PASS) and `node scripts/quality/run.cjs full` (PASS).
- [ ] **Step 5: Commit** with the message `feat(contract): freeze v1 API contract and schema`. From here on, contract changes need a CR.

### W0-09: Test-kit foundation (backup groups A and B, the lead parts) · size S–M · depends on: W0-01 · V1-A21

**Files:**
- Modify: `apps/web/package.json` (devDependencies pinned as on `b54ec7c`: `vitest 5.0.5`, `@vitest/coverage-v8 5.0.5`, `jsdom 30.1.3`, `@testing-library/react 16.3.3`, `@testing-library/jest-dom 7.0.1`, `@testing-library/user-event 14.6.8`; script `"test:unit": "vitest run && node --test tests/*.test.mjs"`), `package-lock.json`, root `package.json` (`"test:docker": "node scripts/testing/docker-tests.cjs"` and `"test:stories": "node scripts/testing/story-coverage.cjs"`).
- Create:
  - `apps/web/vitest.config.mts` and `apps/web/tests/unit/setup.ts` (adapted from `b54ec7c`);
  - `apps/web/tests/unit/sanity.test.ts`;
  - `scripts/testing/docker-tests.cjs`, a placeholder that exits 1 with `not implemented: W5-PK01`;
  - `docs/testing/user-stories.json` (the 24 IDs V1-A01…V1-A24, each with `"tests": []`);
  - `scripts/testing/story-coverage.cjs` (`--report` prints the uncovered IDs and exits 0; `--enforce` exits 1 when any ID is uncovered). It reads `@V1-Axx` from e2e titles and `# covers:` / `// covers:` headers from tests;
  - `scripts/quality/tests/story-coverage.test.cjs`.

- [ ] **Step 1: Write the failing test** `story-coverage.test.cjs`: on a temporary tree with one tagged spec, `--report` lists 23 uncovered IDs and exits 0, and `--enforce` exits 1.
- [ ] **Step 2: Run** `node --test scripts/quality/tests/story-coverage.test.cjs`. Expected: FAIL.
- [ ] **Step 3: Implement**, then run `npm ci`.
- [ ] **Step 4: Run** `npm run test:unit --workspace @pantrypulse/web` (vitest sanity + `forecast-proxy.test.mjs` PASS) and `node --test scripts/quality/tests/*.test.cjs` (all PASS).
- [ ] **Step 5: Commit.**

### W0-10: Re-plan gate and wave-1 launch · size S · depends on: W0-06, W0-08, W0-09

- [ ] **Step 1:** Apply the spike findings.
  - S1 decides which branch of W1-S05 applies, and the envelope.
  - S4 decides the shape of W1-D04 and W1-D05.
  - S3 decides any packaging notes.
  - Edit `wave-1.md`, `wave-3.md`, the README interfaces and the prompts wherever names changed. List every change in the gate report.
- [ ] **Step 2:** Confirm the plan call on `travel_days` in W1-D07 (`max(1, ceil(road_hours / 24))`) with Gabriel.
- [ ] **Step 3:** Open the `w0/foundation` PR. Get the verifier's review (requirements + diff + tests). Run `/devkit:ship-check`. With Gabriel's OK, merge into `v1-local`. Then run `node scripts/quality/run.cjs full` and the connected e2e (`PP_RUN_CONNECTED=1`) on `v1-local`. Expected: PASS, 0 skipped.
- [ ] **Step 4:** Set up the three wave-1 worktrees ([ORCHESTRATION.md §3](ORCHESTRATION.md#3-wave-lifecycle)), fill in `{{BASE_SHA}}` in `prompts/w1-*.md`, and update BOARD.md.
- [ ] **Step 5:** Verify whether a lane session opened in `~/code/PantryPulse-data` appears in `ListAgents`. Record the result in ORCHESTRATION.md §2.
- [ ] **Step 6:** Send the wave-start report with the spike verdicts. **Gabriel approves the wave 1 start.** Then run `/vault-wrap-up` for W0.
