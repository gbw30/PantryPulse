> **Current approved integration:** [Connected application and v2 contracts](CONNECTED-INTEGRATION.md) supersede historical OR-only/no-proxy scope and 15/25/60-second execution limits below. The old decision manifest and qualification artifacts remain historical evidence; their hashes and semantics are not reinterpreted.

# OR scope and backlog ownership

The user corrected the assignment to the research-centered OR service only. Read
[execution revision 1.2](03_OR_Codex_Execution_Spec.md) and the [handoff record](SCOPE-CORRECTION.md).
Previous UI/integration implementation is archived; no issue is closed from it.

| Current OR work | Issues |
|---|---|
| Tracker, specifications and pure data/forecast contracts | #54 #55 #56 #11 |
| Independent mathematical gate and oracle | #10 |
| OR-local projection/candidates/shared physical constraints | #23 #24 |
| Independent checker, policy metrics, both objectives | #25 #26 #27 #28 |
| Computational/offline validation, enumeration, verification, solve/compare | #57 |

| Existing product backlog item | Owner boundary / current status |
|---|---|
| #59 saved-assumption UI | Frontend/API handoff; historical code archived |
| #60 mobile reading order | Frontend handoff; historical code archived |
| #61 visual policy/trade-off explanations | Frontend handoff; OR returns typed metrics |
| #62 browser/visual acceptance | UI/integration owner; not an OR completion gate |
| #63 broader documentation/hosted CI | Project/quality owner; OR-specific context corrected |
| #64 committed forecast publication | Forecast/data/shared-runtime owner |
| #65 authoritative stock/operational reads | Data/inventory owner |
| #66 committed-source connected journey | Integration owner after upstream contracts |

These PBIs and original PP/WQ issues remain open and readable. The OR agent's
assignment was removed from adjacent frontend/API/data/runtime tasks; other
assignees were preserved. #33's title no longer requests a Next proxy. Next.js is
frontend only: never implement Next API routes/proxies. No new owner was invented.
Supplier, Chronos and hosting pauses remain unchanged.

## Longer configurable solver budgets

**Planned OR refactor, requested by the user October 25, 2026.** The current
15-second search cap is an initial execution limit, not a permanent product
requirement. Make longer searches possible through explicit, validated settings,
especially for offline research runs. The dense qualification cases have large
optimality gaps; assess whether additional search time improves their solutions
and bounds before choosing future defaults.

- Benchmark both methods on the same frozen inputs and equal budgets, initially
  comparing 15/30/60/120 seconds. Record objective, bound/gap, native status, elapsed
  time and memory; longer searches do not guarantee a proven optimum.
- Support explicit budget profiles or per-run settings, retaining the chosen budget
  in settings hashes and replay metadata. Select defaults from measured quality
  versus runtime, with separate consideration for interactive and research use.
- Reconcile the existing 25-second method-child and 60-second pair deadlines with
  longer native search, allowing startup, construction, verification and cleanup.
  Preserve cancellation, resource limits and independent verification. Coordinate
  application deadlines with the shared-runtime owner; this does not expand OR
  ownership into API routes, frontend or shared-worker implementation.

Acceptance: longer configured runs can complete without premature outer timeouts;
paired comparisons retain equal settings; timeout/cancellation tests pass; and a
reproducible quality/runtime comparison supports the selected limits. Current
runtime limits remain unchanged until this refactor is implemented and tested.
See [qualification evidence and limitations](QUALIFICATION.md).
