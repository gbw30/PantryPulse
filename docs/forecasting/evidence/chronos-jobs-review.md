# FC-05 / #84: durable Chronos application integration

October 25, 2026. Working branch: `feat/forecasting-next`, based on main `5add760`.
This stage integrates the pinned adapter; predictive qualification remains #85/#86.

## Resulting behavior

The existing `/api/v1/forecasts` surface accepts `CHRONOS2` and freezes the
server-approved checkpoint/package/profile before historical snapshot hashing.
Browser-selected Chronos checkpoint/revision/profile fields are rejected. A
separate `forecast.chronos.v1` registration prevents old baseline workers from
accepting the new strategy. Registry/schema imports and saved reads remain usable
without optional model dependencies. `forecast.v1` and its baseline inputs remain
compatible: the original main synthetic fixture still hashes to
`515f61754ca862e1ad6e40885feced72be40b11251d2122d1a539e77f3190891`.

No default-valued fields were added to ForecastPolicy. Its existing adapter-version
field gained the explicit Chronos CPU-float32/two-thread/context366 profile.
Checkpoint revisions and execution profiles participate in frozen reuse identity.
Manual retry retains its original input and must match current worker capability.

The supervisor filters actual execution advertisement using an optional handler
preflight. Chronos requires explicit opt-in, the exact model package, and local
configuration/weight files for the approved full revision. The advertisement
includes the exact model/profile metadata; admission and retry reject missing,
malformed or mismatched profiles. Existing handlers without a preflight retain
their behavior. Corrupt model configuration suppresses this model capability
without crashing baseline startup. Preflight performs no heavy imports or model
loading; child inference remains cache-only.

The trusted enable/revision/cache variables are forwarded through the process
driver's precise environment allowlist; database credentials and model tokens are
not. Model computation retains the existing 270-second primary cutoff, 300-second
operation ceiling, shared lane, ownership/cancellation fences and atomic
publication. One explicitly allowed whole-batch moving-average fallback follows a
classified failure. Output provenance, profile, quantile meaning, fallback
authorization and uniform whole-batch fallback are checked again at publication.

The existing workspace now has a method selector and labels the **last generated
job's** actual providers/fallback/incomplete readiness. A manual saved selection
clears that last-generated status. Generated OpenAPI/TypeScript match the API.
See [operator configuration and job semantics](../CHRONOS-JOBS.md).

## Actual isolated journey

The explicit smoke created a uniquely named schema in the dedicated `_test`
database, migrated/seeding only that schema, and started its own loopback Uvicorn
HTTP server and production supervisor. It used real HTTP requests, PostgreSQL,
the actual Linux process-group driver and the cached real Chronos model.
No existing runtime was stopped or restarted; its generated schema was removed.

| Gate | Observed result |
|---|---|
| Actual full-scope model job, fallback off | Durable SUCCEEDED, 12 demand series / 84 points, actual CHRONOS2, `planning_ready=false` |
| Invalid donation quantiles | Remain rejected; no clipping or policy widening |
| Explicit whole-batch fallback | Durable SUCCEEDED, 26 series / 182 mean points, actual MOVING_AVERAGE, planning-ready |
| Real contained child cancellation | CANCELLED, boundary confirmed empty; database URLs absent from child environment |
| Manual retry | Same job, new attempt; original frozen input/pin; actual execution SUCCEEDED |
| Canonical planning handoff | Committed fallback result froze a canonical scenario with MOVING_AVERAGE provenance and derived hub-zero demand |
| Worker outage | Saved reads/exact committed reuse succeed; forced new computation returns COMPUTE_UNAVAILABLE / 503 |
| Smoke duration | 54.752 seconds for complete setup, executions, cancellation/retry, HTTP checks and cleanup |

The first smoke reached the same application gates but its final scenario test
expected the wrong derived-provider string (`DERIVED_ZERO`). Main uses
`DERIVED_HUB_ZERO_DEMAND`. Correcting that test assertion and rerunning the full
smoke passed. No production policy or solver behavior changed to satisfy it.
Machine evidence: [chronos-jobs-smoke.json](chronos-jobs-smoke.json); raw summary:
`/tmp/pantrypulse-chronos-jobs-smoke.json`.

## Checks and reproduction

- **352 changed-path tests passed** across forecasting, job policy and driver
  capability. Subsequent final ticket tests: **26 passed**, covering the added
  malformed-cache and publication-boundary regressions too.
- **95 real PostgreSQL/queue/supervisor/process tests passed**, zero skips, covering
  forecast storage/reuse, ownership/publication fences, timeout and containment.
- Ruff check, changed source formatting and whitespace checks passed.
- Frontend typecheck, ESLint, generated-contract checks, proxy unit test and Next
  production build passed. Browser E2E was **not run in this stage**; this is not
  full visual/product acceptance.
- The initially installed frontend lacked the already-declared
  `@axe-core/playwright@4.13.0`. That exact dependency was installed in
  `/tmp/pantrypulse-fc84-web` and linked under ignored node_modules; manifests and
  dependency locks were not changed. Existing Starlette/httpx and upstream model
  dtype deprecation notices remained visible.

Representative commands from the repository root:

```sh
apps/api/.venv/bin/python -m pytest apps/api/tests/forecasting \
  apps/api/tests/jobs apps/api/tests/workers/test_driver_capability.py -q -p no:cacheprovider
apps/api/.venv/bin/python /tmp/pantrypulse-forecast-test-runner.py \
  tests/integration/test_forecast_api_postgres.py tests/integration/test_job_queue.py \
  tests/integration/test_supervisor.py tests/workers/test_process_driver.py -q -p no:cacheprovider
npm run typecheck
npm run lint
npm run contracts:check --workspace @pantrypulse/web
npm run test:unit --workspace @pantrypulse/web
npm run build
```

The local test runner loads only the already-selected test URL from its private
`/tmp` file, requires a `_test` database and enables schema-isolated fixtures.
It never prints connection credentials. For the real smoke, use
`/tmp/pantrypulse-chronos-fc04/bin/python -m scripts.smoke_chronos_jobs` from
`apps/api`, with private `PP_TEST_DATABASE_URL` and the operator settings in
[CHRONOS-JOBS.md](../CHRONOS-JOBS.md), writing to a `/tmp` output path.

The isolated model environment now also contains the locked base API/test
dependencies and optional `pyarrow==22.0.0` for subsequent evaluation work. The
shared baseline `.venv` and repository lockfiles were not changed. No final
holdout, retail benchmark, real pantry accuracy, interval calibration, hosted
deployment or new OR solve was claimed by this stage. The single owner stops
after this handoff so #85 can resume against the stable integration.
