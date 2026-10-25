> Historical pre-correction scope/evidence. Adjacent implementation is archived, not active on this OR branch. [Current scope and handoff](SCOPE-CORRECTION.md) supersede its implementation instructions/status.

# OR implementation commit checkpoint — October 24, 2026

User requested a pause at substantial milestones so they can commit before continuing.
This is a bounded implementation checkpoint, not completion of issue #54 or V5.
Base commit: `f3946c726e53fa546be1400d80ab717fcb2c3468`. Changes remain uncommitted;
the user owns the commit. Existing shared worker source was reconciled from
`d7e44eddc9da51ba7886a6e317e90ace894b7847`; no branches were merged or deployed.

## Working milestone

- All three supplied Draft 1.1 documents are preserved verbatim in this directory.
- Strict normalized inputs, immutable scenarios, forecast adaptation without double
  rounding, shared FEFO projection and independent candidate verification are implemented.
- Both real CP-SAT methods run in both explicit transfer modes. Native full-fixture
  optima match independent enumeration: classical `(1,1,1,1,1,1)` per product,
  objective `163/50`; research `(2,2,1,1,0,0)` per product, objective `1393/300`.
  AP/RP examples and small physical feasible-set checks also pass.
- PostgreSQL migrations through `0005_or_active_dedup`, immutable records, atomic
  verified publication, shared durable queue, partial-result retention, linked OR
  retries, cancellation, source/epoch fencing, and synthetic reset are implemented.
- Presenter sessions, origin/CSRF checks, saved reads, durable 202 submissions,
  reviews, generated OpenAPI/TypeScript and the connected `/optimization` page/proxy
  are implemented. The web production build passes.
- A real HTTP/PostgreSQL/production-supervisor test completes paired solving,
  disruption into a new scenario, append-only review, saved reads after worker
  shutdown and an isolated reset retaining history.

## Review corrections in this checkpoint

The locked OR-Tools 9.15 native repeated container returns the first endpoint for
`domain[-1]`. The bound audit now uses a nonnegative last index. Three regression
tests first reproduced underestimated upper bounds and missed unsafe constraint/
objective activities; all pass after the correction. The emitted-model evidence was
regenerated: maximum activities are 13,040,000 (classical) and 90,120,000 (research),
both below the exclusive `2**60` limit. Physical fingerprints match.

Resource tests now distinguish per-process allocation rejection from actual cgroup
OOM enforcement. They read the kernel `memory.events` counter and handle systemd's
whole-scope stop after a child OOM. All five resource tests pass on the local host.
Hosts without an accessible user systemd manager report the hard aggregate limit as
unverified. Latest worker lint errors were corrected, and the unfinished decision
manifest/check command now verifies all 20 decisions against behavior symbols,
assertion-bearing tests and fixture metadata.

## Verification and resumption

Verification: combined type/lint/API/PostgreSQL check passed 870 tests; the updated OR suite passed 59 tests including three new overflow regressions. Production web build, contract drift, 17 configuration tests and decision coverage also passed. See [acceptance evidence](ACCEPTANCE.md) for commands, results and remaining gates.
The installed test environment is Python 3.12.13, OR-Tools 9.15.6755, PostgreSQL
16.15, Node 24.16.0 and npm 11.13.0. Local tool binaries are under
`/tmp/pantrypulse-node/node_modules/.bin` and `/tmp/pantrypulse-uv/bin`.
The dedicated database is local `pantrypulse_or_test` on port 55439; tests use
isolated schemas. No production data or physical inventory was changed.

Resume after the user's commit:

1. Inspect Git and rerun relevant checks against the committed SHA.
2. Run the real `/optimization` browser journey and inspect desktop/mobile,
   keyboard, reduced-motion and error behavior. The Playwright journey is written
   but its five reset-to-finish rehearsals have not been executed successfully.
3. Complete the persisted benchmark and CLI smoke/exit-code matrix; retain exact
   timing, resource, input/policy/settings hashes and environmental evidence.
4. Finish the strict OR-A01…12 acceptance audit, decision-register alternatives/
   limitations review, source read-port documentation and broader V5 documentation.
5. Review remaining native numerical/status/failure boundaries and complete
   independent security/runtime review before claiming full first-draft completion.

LIVE source integration is unavailable: committed authoritative forecast
publication and inventory/operational read adapters have not landed. Pure
`ready_for_publication` is not committed readiness. Supplier planning and actual
Chronos/model hosting remain paused. No deployment or GitHub issue closure is claimed.
