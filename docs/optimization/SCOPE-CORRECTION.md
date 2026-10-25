# Approved OR-only scope correction

The user approved removing adjacent-layer implementation and correcting execution
context first. Base before OR: `f3946c7`; broad implementation commits `e49e360`
and `46ff0cd` remain in Git. No commit was rewritten, reset, pushed or deleted.

## Current ownership

Read [execution revision 1.2](03_OR_Codex_Execution_Spec.md) and [scope](SCOPE.md).
This branch delivers the OR computational pipeline, Python input/output schemas,
independent verifier/metrics, explicit fixtures and offline/native tests. It creates
no frontend or Next API routes, FastAPI routes/auth, ORM/migrations, persistent
queue, shared supervisor/worker or public generated client.

The API owner supplies authorized coherent frozen data, calls `freeze_scenario`,
`solve_one` or `compare`/`assemble`, and owns HTTP, persistence and runtime scheduling.
OR returns checked typed outcomes. The frontend owner consumes FastAPI under the
team's access/deployment contract. Next.js is frontend only: the old Next proxy
proposal is withdrawn, not merely deferred for this agent to implement later.

## Reversible handoff

Before removal, 81 attributable adjacent-layer files were archived. Their patch was
applied to reconstructed baseline files in a temporary directory and every resulting
file matched its recorded SHA-256. [Manifest](scope-handoff-manifest.json) lists exact
paths, restore/remove actions, base/head and artifact checksums.

Local preserved artifacts (ignored so executable integration code is not part of
the OR deliverable):

- `artifacts/or-scope-handoff/2026-10-24/integration.patch`: baseline-to-integration
  changes only; intended for the respective owners to inspect/reconcile.
- `artifacts/or-scope-handoff/2026-10-24/source-snapshot.tar.gz`: all 171 changed/new
  source/doc files after the approved guidance correction and before removal.
- `artifacts/or-scope-handoff/2026-10-24/manifest.json`: matching checksums and paths.

These artifacts preserve the uncommitted explanation work as well as earlier
integration code. Keep/copy the folder before cleaning ignored artifacts. Historical
committed work is also recoverable from the two commits above. No handoff patch was
applied to another developer's branch or sent to anyone. Owners must inspect their
current contracts/changes before applying anything; Next proxy code is historical
reference and must not be introduced into this architecture.

## Exact correction

New attributable adjacent files were removed; attributable edits were restored to
their pre-OR bytes. In particular, frontend source/tests/config, API entry point and
health tests, the existing inventory projection, package manifests/lock and shared
quality configuration match the baseline. The OR-specific inventory network replay
and kernel were moved into `services/optimization`, leaving inventory unchanged.

The five computational CLI commands plus common file I/O now use an OR-local child boundary rather than imported
jobs/workers. It bounds native work, output and child lifetime; it is not a scheduler.
It tests real inherited affinity/per-process address-space limits and process-group
cleanup. Kernel aggregate-memory quotas, shared admission, leases, crash recovery
and committed publication remain the runtime owner's responsibilities.

Historical OR-DEC IDs remain in immutable fixture/hash contracts. The v2 marker
manifest validates 18 core/bounded decisions and explicitly reports persistence
OR-DEC-012 as external and Next-proxy OR-DEC-014 as withdrawn. No missing external
implementation is represented as passing core coverage.

## Verification

Completion checks on October 25, 2026 pass. [Machine-readable evidence](evidence/scope-correction.json)
records the retained core source/test fingerprint, base/head and limitations.

- `npm run check`: types/lint and all **594 retained Python tests pass**, including
  **106 OR cases**, actual native objectives/ablations/bounds and OR-only child cleanup.
- `npm run test:config`: all 17 tests pass.
- `npm run build`: restored frontend builds only `/`, `/design-lab` and not-found;
  no OR page or Next API route remains. Stale generated type caches referring to
  deleted OR routes were cleared before the successful run; no frontend source fix.
- Marker check: 18 core/bounded decisions verified; two external/withdrawn decisions
  reported explicitly. The baseline-relative diff check passes for owned changes; the later-restored worker reference retains its original Markdown hard-break whitespace.
- 79 adjacent paths are absent or match exact pre-OR bytes; two imported worker-authored reference documents are retained unchanged after re-audit. The archived patch
  reconstructs all 81 prior files exactly. The one-time audit is not a permanent
  test freezing other teams' files against future legitimate changes.

Logs are under `artifacts/or-scope-handoff/2026-10-24/`. The Starlette/httpx
compatibility warning remains. Historical 928-test/browser/DB results describe the
archived broad implementation and are not current application acceptance.

The restored shared full-gate template contains pre-existing placeholder commands;
those are outside this assignment and are not replaced by invented pass results.
Use the actual retained `npm run check`, OR marker check and core/native tests for
this correction. Frontend byte identity and a read-only baseline build can verify
restoration without claiming ownership of frontend features.

## Backlog handoff

#54/#55/#56/#57 and OR math/model/checker issues retain only their core scope.
#59–#66 and existing frontend/API/storage/worker tasks remain open as external-owner
handoffs; their old implementation/acceptance history remains visible. No issue is
closed from an archived test run. Supplier, Chronos and hosting remain paused.

This correction is ready for the user to commit. Suggested message:
`refactor: isolate OR service and hand off integration layers`. No automatic commit,
staging, history rewrite, push, merge, deployment or database change was performed.

## Ownership re-audit — October 25, 2026

The user's additional check audited all 194 pre-OR tracked files: none are missing;
all original code/configuration matches baseline. Four project documents have only
approved scope notices prepended; their original bodies are byte-identical.
[Audit evidence](evidence/ownership-audit.json) records the checks.

The shared-worker implementation was authored on a separate branch and explicitly
copied into the OR tree by the original OR session. Removing those imported copies
does not remove the originals on `origin/be/worker-queue` at `d7e44ed`, which remains
intact. They must not be described as code the OR agent originally authored.

Deleting two non-executable imported references was unnecessary. The worker build
specification and its architecture ADR have been restored byte-for-byte from that
branch/archive. This preserves their author's documentation without reintroducing
worker runtime or granting OR ownership. The approved OR-only/Next frontend-only
rules still control this assignment. The original preservation archive/checksums
are unchanged. No commits, other branches, executable code or schemas changed in
this re-audit.
