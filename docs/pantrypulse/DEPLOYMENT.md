# Deployment and recovery

Updated October 25, 2026. [Current status](CURRENT-STATUS.md), [SPEC-V5](SPEC-V5.md), [connected integration](../optimization/CONNECTED-INTEGRATION.md) and [external services](../../EXTERNAL-SERVICES.md) define the implemented scope and target-specific procedures. Source includes baseline forecasts, authenticated scenarios/comparisons, verified methods and `/optimization`; it is no longer a process-only scaffold.

## Separate source, runtime and deployment evidence

Local backend/model preparation and the merge of PR #77 are authorized. No new paid service or public deployment follows automatically. The earlier branch-scoped [Vercel `/design-lab` preview](../setup/VERCEL.md) is a separate synthetic deployment. A source merge does not replace a running image, apply migrations, update that preview or qualify an integrated model provider.

| Environment | Required boundary |
|---|---|
| Local development/review | Dedicated database/schema and ports; disposable tests never reset a running demo |
| Connected synthetic demo | NEW `ppor_demo_*` schema, explicit seed, presenter controls, matching proxy settings, version-2 worker |
| Hosted release | Exact authorized app/project/region, API/worker/database pairing, secure cookies/origins, manifest and rollback |

## Controlled release sequence

1. Freeze the exact source/commit and validate the combined tree. Active `.github/workflows/pantrypulse-ci.yml` runs Linux/PostgreSQL, contracts, web build and the real connected browser path and rejects skipped evidence. An ignored provider build or process health response is not a passed product gate.
2. Select the dedicated database, runtime and direct migration roles, schema, ports and API/web targets. Preserve TLS settings. Review migrations through `ppor_0005` on a fresh isolated target. Never mutate old applied revisions or run migrations from every replica.
3. Use the deliberate demo loader for a NEW `ppor_demo_*` schema. It creates fictional history/stock/assumptions and no fake forecast/comparison results. It refuses reuse; reset/retention and production data operations are separate contracts.
4. Configure API/worker `DATABASE_URL` and `PP_DATABASE_SCHEMA`; private presenter username/password hash/organization, `PP_ALLOWED_ORIGINS`, `PP_TRUSTED_PROXY_TOKEN`, and `PP_COOKIE_SECURE`. `APP_ENV`/`DEMO_MODE` alone do not authorize anything. Configure Next.js `PANTRYPULSE_API_ORIGIN` and the same private proxy token. No secret belongs in a browser-exposed variable.
5. Inspect existing active/queued jobs and preserve running tasks. A version-1 worker cannot advertise the new contract. Plan a controlled drain and replacement after active work finishes; do not clear ownership rows or automatically retry an interrupted attempt. Local supervisor drain is 720 seconds with 725-second container grace.
6. Start only the chosen API and production supervisor, keeping one active operation/two waiters in the shared PostgreSQL lane. Validate the actual effective resource limits and fresh version-2 advertisement for `forecast.v1`/`or-comparison.v2`. Core CPU/RAM ceilings are six/eight GiB, separate from API/database needs.
7. Verify the actual browser URL through its proxy, login/CSRF/logout, baseline forecast publication, explicit-mode frozen scenario, real sequential comparison, independent method verification, partial outcomes, replay/idempotency and saved reads after worker loss. Check stale-selection behavior, mobile/keyboard access and simulated provenance.
8. Record the release manifest and tested rollback pair before declaring that exact environment ready. Source CI and earlier measured runs remain scoped to their own tree and runtime.

## Fly alternative

[Fly configuration](../setup/FLY.md) defines separate API/worker Machines, a four-vCPU/eight-GiB worker and persistent model storage. Login, target selection, platform validation and deployment remain pending. Fly's maximum configured shutdown window is 300 seconds, shorter than a possible 690-second comparison: drain/confirm an idle lane BEFORE deployment; never assume SIGTERM can finish the longest job inside that window. Cross-host takeover is not qualified; do not attach a local and a Fly worker to the same queue.

## Chronos and release claims

Pinned full Chronos-2 CPU inference and synthetic timings have been measured separately. The application forecast policy remains baseline-only; model-handler admission, fallback/deadline/publication integration, representative accuracy and calibration remain separate qualification. A cached checkpoint or fresh heartbeat is not an integrated forecast result. Keep raw quantiles and simulated/donation provenance explicit.

## Manifest and rollback

Record web commit/build URL, API image/commit, worker capability/profile, database/schema revision, dataset/input hashes, model/checkpoint if used, solver settings and results, origins and rollback targets without secret values. Preserve the last known-good compatible web/API pair.

On failure, classify web/API/configuration/database/worker/model before acting. Roll back application code only to a schema-compatible version; it does not roll back data. Never run an untested destructive downgrade, broad process kill, dirty-worktree reset or volume deletion. Reconcile interruption/cleanup through the [worker runbook](../setup/WORKER-QUEUE.md), and retain manual retry against immutable inputs.

Keep a local rehearsal, dependencies/model cache, screenshots and a labeled backup recording. Verify venue connectivity and any actual hosted URL separately. Supplier planning, broad data-management UI, visitor access, production reset, purchasing/reservation/dispatch and real-world policy efficacy are not established by this bounded simulated release.
