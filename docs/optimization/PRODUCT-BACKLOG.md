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
