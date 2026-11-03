# Branch, code and documentation diagnostics — October 25, 2026

## Scope and result

The earlier testing-kit findings applied to the current `design/overview-intake`
checkout at `a4573b5`, plus its uncommitted changes. **Many of the missing features
already exist in newer main.** Do not rebuild them from the old checkout's gap list.

Remote references were refreshed. Sources were exported into ignored directories;
the working branch was not switched, merged, reset or committed. Existing worktrees
and running application/worker containers were preserved. Database and process tests
used a separate disposable PostgreSQL 16/Linux stack, no shared database, and newly
generated ephemeral presenter credentials. No deployment or GitHub issue mutation occurred.

## Branch inventory

| Ref inspected | Exact commit | What it contains / relationship |
|---|---|---|
| Current checkout | `a4573b5` | Static Network Atlas and design lab; health-only API. Its committed history has 12 commits absent from main; main has 28 absent here. The uncommitted testing kit is additional work |
| `origin/main` | `5add76008faddae08a969514c2e827299bc84d50` | Includes connected OR integration, forecasting/persistence/presenter/proxy and converged VP operational APIs through PR #78 |
| `origin/VP` | `35615a64823726aff0cd42f713e4d7ebba426f37` | Operational contracts, stock, receipts, supply/import/projection/planning work. This exact head is an ancestor of inspected main; main adapts its planning APIs to canonical contracts |
| `origin/or_pipeline` | `465d0261988f9ee43d2f76506d7b8267055327fc` | Computational methods, independent verification and research evidence. This exact head is an ancestor of main; connected main uses its versioned inclusive-expiry contracts, not unmodified old branch contracts |
| `pp/overview-live` | `9e45524e26367d0b1aed0d7af9e078becfe15504` | Includes current main and the Atlas/shell/polish work; adds typed dashboard/shortage responses and generated contracts. Still uses the static Atlas adapter |
| `pp/overview-polish` | `16c47d79deb6437ade976bb672227bd30f394583` | Earlier unmerged Atlas supply/spacing/motion and optimization-shell work; incorporated into `pp/overview-live` |

All local and origin refs were inventoried in
`artifacts/diagnostics/2026-10-25/reports/branches.json`. Older helper/forecasting
heads can have unique commits because of historical integration/squashing; that
alone does not establish missing functionality. The substantive newer operational
and OR implementations above were checked against main's code and tests.

## Where the missing stories exist

| Stories | Implementation found | Remaining boundary |
|---|---|---|
| US-01, US-05: inventory/shortages | Main inventory, dashboard-summary and dated-shortage APIs; typed response additions in `pp/overview-live` | Atlas remains a static fixture; live dashboard wiring and a full site page remain open |
| US-02: adjustments | Main version-checked audited stock API, transaction tests and connected browser-proxy test | No general stock-management screen |
| US-03: imports | Main bounded JSON/CSV demand import, donation coverage, revision/idempotency/row feedback | General upload/data-management UI remains open; imported history is separate from stock posting |
| US-04, US-06, US-12: forecasts/provenance | Main committed baseline runs, production forecast handler, saved metadata, validation/fallback and planning handoff | Standalone Chronos evidence does not register/qualify it as the application provider; no fabricated calibrated intervals |
| US-07, US-08, US-10: plans/explanations/failure | Main canonical single-method and paired jobs, both methods, independent replay, saved results, explanations and honest partial outcomes | Bounded simulated policy/domain; no physical dispatch or efficacy claim |
| US-09: revised scenarios | Main immutable assumptions/scenarios and connected workspace; stale-response protection and manual job retry | New assumptions require a new scenario; existing frozen input remains immutable |
| US-11: repeatable demo/reset | Main explicit loader creates a **new** isolated `ppor_demo_*` schema with audited fictional stock | Protected reset-in-place and five full rehearsals are separate acceptance items |
| US-15–18: research comparison/policy | Main paired classical/research-inspired results and editable simulated policy; committed independent enumeration/replay/budget evidence | Mathematical adaptation/policy remains bounded and provisional; not a claim of real-world fairness or complete product acceptance |

Source anchors:
[main router registration](https://github.com/gbw30/PantryPulse/blob/5add76008faddae08a969514c2e827299bc84d50/apps/api/app/main.py),
[operational API](https://github.com/gbw30/PantryPulse/blob/5add76008faddae08a969514c2e827299bc84d50/apps/api/app/routers/operations.py),
[planning/review](https://github.com/gbw30/PantryPulse/blob/5add76008faddae08a969514c2e827299bc84d50/apps/api/app/routers/planning.py),
[connected browser journey](https://github.com/gbw30/PantryPulse/blob/5add76008faddae08a969514c2e827299bc84d50/apps/web/tests/e2e/operations-api.spec.ts),
[connected contract and limitations](https://github.com/gbw30/PantryPulse/blob/5add76008faddae08a969514c2e827299bc84d50/docs/optimization/CONNECTED-INTEGRATION.md).

## Diagnostic findings

1. **Current-checkout integration gap.** The kit's original status is correct for
   `a4573b5`, but cannot describe latest main. Its root redirect, disabled navigation
   and unimplemented-plan 404 assertions must be adapted when integrating with
   newer main. Preserve main's existing proxy tests, contracts and connected tests;
   do not overwrite its scripts/configuration with the old branch's versions.

2. **Windows contract-check false failure.** On the exported main tree,
   `openapi-typescript --check` rejects `schema.d.ts`: Windows `core.autocrlf=true`
   converts the exported file to 6,277 CRLF lines while the generator emits LF.
   Normalizing line endings makes them identical. More strongly, the freshly
   generated file is **byte-for-byte identical to the committed Git blob**.
   Main OpenAPI independently matches the application schemas. This is a Windows
   checkout/checker portability issue, not actual committed contract drift or proof
   that Linux CI fails. Recommend explicit LF attributes for generated contracts
   or deliberate line-ending normalization in the checker.

3. **`CURRENT-STATUS.md` has outdated current-state claims on main.** Line 10 says
   the root redirects to `/optimization`, but main's root renders a landing page
   linking there (`apps/web/tests/e2e/scaffold.spec.ts:3`). Line 11 still names
   `ppor_0005` as the single head; `alembic heads` reports `ppvp_0007`. Lines 16–23
   call VP integration a candidate awaiting merge although PR #78 is in the inspected
   main head. The document should distinguish current merged source from deployed
   runtime, without retaining candidate wording as the current state.

4. **Three broken local links in historical evidence.** In
   `docs/optimization/evidence/acceptance-initial-checkpoint.md`, line 11 incorrectly
   uses `evidence/model-bounds-six-beneficiary-v1.json` from inside `evidence/`;
   lines 13 and 49 link `RESEARCH-MAPPING.md` and `BASELINE-RECONCILIATION.md` in the
   wrong directory. Correct relative targets are `model-bounds-six-beneficiary-v1.json`,
   `../RESEARCH-MAPPING.md` and `../BASELINE-RECONCILIATION.md` respectively. Keep the
   historical checkpoint's date/scope and result claims unchanged.

5. **Atlas name does not imply live integration.** On `pp/overview-live`,
   `apps/web/src/components/overview/network-atlas.tsx:18` still imports
   `overviewSourceFor` from `static-fixture`. Dashboard response typing is useful
   preparation; it does not connect this UI to saved data. Main's two dashboard
   reads require presenter access; visitor reads and broad supply support are not
   established by the static Atlas.

6. **Old checkout's full gate still cannot run.** The new local diagnostic command
   confirms `.claude/quality-gate.json` references missing web `contracts:check`
   and missing `tests/integration/test_migrations.py`. Newer main has executable
   scripts and corrected migration paths. Reconcile these during integration;
   do not add no-op checks merely to make this checkout green.

These are scoped code/contract/documentation diagnostics, not a deep security scan.
Dated evidence is not considered stale merely because newer work exists. Existing
runtime images/deployments were not upgraded or certified by this audit.

## Fresh verification

| Target/check | Result |
|---|---|
| Main full Linux/PostgreSQL API suite, locked dependencies | **1,207 passed, zero skips**, 450.05 seconds; includes real processes, migrations, imports, stock transactions, allocation and canonical review |
| Main XML evidence validator | **PASS**, no skips/failures/errors |
| Main TypeScript, ESLint, proxy unit tests and production build | **PASS**; 6 proxy tests |
| Main configuration/hook tests | **18 passed**, zero skips |
| Main production browser suite with real API/PostgreSQL/Linux worker | **11 passed**, zero skips, 6.1 minutes; all five connected tests enabled, including stock/import/review, paired comparison/revision, partner failure, cancellation/retry and stale response ordering |
| Main Python static checks (`ruff check --no-cache .`) | **PASS** |
| Main OpenAPI/application drift and migration graph | **PASS**; one head `ppvp_0007` |
| Main generated TypeScript | Windows raw-file check **FAIL**; committed blob/fresh generation **identical**; see finding 2 |
| Twenty recorded solver-budget outcomes | **PASS** independent replay with exact input/settings identities; no new benchmark/model download |
| `pp/overview-live` TypeScript, ESLint, six proxy tests and production build | **PASS** |
| `pp/overview-live` changed dashboard API/contract regression slice | **8 passed**, zero skips |
| `pp/overview-live` OpenAPI/application drift | **PASS**; typed dashboard schemas and generated OpenAPI are synchronized |
| `pp/overview-live` focused production Atlas/shell browser suite | **26 passed**, zero skips, 52.4 seconds; static Atlas tests, not a claim of live dashboard wiring |
| Current checkout local-doc/gate scan | Two findings: missing legacy full-gate script/test |
| Main local-doc/gate scan | 122 Markdown files / 547 local links; three broken historical-document links; no missing gate commands or unresolved merge-conflict blocks found |
| Overview local-doc/gate scan | 125 Markdown files / 550 local links; same three broken historical-document links |
| New diagnostic-checker tests | **3 passed**: heading anchors, file/anchor resolution with fenced examples, missing gate commands/tests |

Main's five prerequisite-gated connected browser tests were explicitly enabled;
none were skipped or replaced with mocks. Fault injection targeted only the exact
test comparison child inside the disposable diagnostics worker. The existing
browser test for late response ordering deliberately delays a real response.

Artifacts: `artifacts/diagnostics/2026-10-25/reports/` holds branch identities, JSON
file/link/gate findings and fingerprints, JUnit reports and the line-ending comparison.
Browser traces/screenshots remain inside the respective exported snapshot's
`apps/web/test-results/`. Test secrets remain ignored and are never part of this report.

## Integration recommendation

Use latest main's connected backend/workspace as the implementation baseline. Review
`pp/overview-live` for the Atlas/shell and typed dashboard changes, then wire the real
adapter under the actual presenter/proxy contract. Integrate this kit additively:
retain its unit/invariant coverage, preserve upstream connected tests and change
story assertions to the appropriate route/data source. Correct the Windows contract
check and current-status documentation as bounded follow-ups. No merge or restart
was performed as part of these diagnostics.
