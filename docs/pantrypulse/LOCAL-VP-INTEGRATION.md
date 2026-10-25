# Local main → VP integration — October 24, 2026

- Working branch: `VP`. Fetched main: `873d3569ee6bcb9efb827f930cb6d0c40c84db47`.
- Local merge commit: `1f5e60c`; local main was fast-forwarded to the fetched main.
  No changes were pushed to either remote branch.
- Original local work is recoverable from stash
  `61f7d92fdff4c3dd9487a923974829ba33e7cc7c` (retained, not dropped).
- Local implementation and integration edits remain uncommitted on VP, matching
  the prior local-work workflow. Ignored private `.env` was retained.

## Reconciliation

- Combined both README updates, preserving main's forecasting, worker and frontend
  changes alongside VP's operational inventory and scenario work.
- Preserved forecasting `project_daily` and its historical `ProjectionLot`/
  `ProjectionDay` types via explicit re-exports from `experimental_projection.py`.
  It retains the forecasting experiment's expiry boundary; it is not the adopted
  operational policy. `project_inventory` retains BD-43/44/48 inclusive expiry,
  lot exclusions, commitments and daily lost-sales behavior. Neither API silently
  substitutes the other contract.
- Unified Alembic connection/schema selection and metadata. Caller-supplied worker
  connections keep their isolated schema. Direct connection strings are required;
  private credentials are not stored in Alembic configuration.
- Added no-SQL merge revision `pp_merge_0003`, joining `0001_jobs_foundation` and
  `pp21_0002`. Original worker and operational revision files were not rewritten.
- Combined-head tests cover all 27 domain/job tables. Operational metadata drift
  remains checked; worker metadata deliberately mirrors columns only, so its
  columns are checked separately instead of claiming complete ORM/FK parity.
  The historical jobs-only migration test targets its original revision explicitly.

## Verification

- Combined non-database backend suite: **807 passed**, **11 skipped** because Linux
  `/proc` process containment is unavailable on Windows; one existing Starlette/
  httpx deprecation warning. Command:
  `python -m pytest -q -p no:cacheprovider --ignore=tests/integration --tb=short`.
- Focused final graph and both projection-API regressions: **77 passed**. This
  includes the subsequently added single-head graph test; no full-suite total
  including that additional case is implied.
- Actual PostgreSQL operational/stock integration suite: **38 passed**, including
  upgrade from each pre-existing parent history to the combined head and full
  downgrade on generated disposable schemas. The worker `*_test` database reset
  suite was not run against the shared Neon database.
- Read-only check afterwards: public remains at **pp21_0002**, with **zero**
  remaining generated `pp19_test_*`/`ppmerge_test_*` schemas. No new public migration
  or fixture data was applied by this merge.
- Ruff passed for application/migration code and changed integration tests.
  Alembic reports exactly one head: `pp_merge_0003`. No Git unmerged entries or
  conflict markers remained; `git diff --check` passed.
- All 37 originally untracked files were restored; normalized Git blob checks
  confirm all four frozen operational migration files match the recovery stash.
- Frontend dependencies were installed from the fetched lockfile with pinned npm
  11.13.0, Node 24.21.0 and install scripts disabled. The final install used the
  local cache; the official Three.js archive was checked against the lockfile's
  SHA-512 integrity. No dependency manifest or lockfile changed.
- `npm run typecheck` and `npm run lint` both passed on the merged frontend after
  the completed dependency sync. No production build, browser E2E or deployment
  is claimed.

Independent review, Linux worker containment, full product acceptance and remote
publication are separate; a local integration does not establish those outcomes.

## VP publication preparation

The user subsequently authorized pushing the combined project work to origin/VP.
Private environment files and the local `.neon` pointer are excluded. The staged
credential-pattern/private-file scan passed. The final staged whitespace check
excludes only the immutable generated `pp19_0001_tables.sql`, whose existing
trailing spaces are retained to preserve the already-applied migration bytes.
No main-branch push or database migration is part of this publication.
