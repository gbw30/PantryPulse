> Historical broad-implementation reconciliation, superseded by the approved [OR-only correction](SCOPE-CORRECTION.md). Imported worker/API/UI ownership below was withdrawn; it is not current build guidance.

# Baseline reconciliation

Reviewed October 24, 2026 America/New_York. Local and refreshed remote main: `f3946c726e53fa546be1400d80ab717fcb2c3468`. The three source specs remain verbatim Draft 1.1; this record carries factual updates.

| Ref | Refreshed SHA | Reconciliation |
|---|---|---|
| main | f3946c726e53fa546be1400d80ab717fcb2c3468 | PR51 merged; preserve corrections |
| forecasting | bed08544e3dc9b00499224806d92dd8f437f0644 | Merge-base a0ad11f; incorporated through PR51; no replay |
| VP | b82f85f2f7b43f05df5ab0ef033c9bf0e8b28b38 | Merge-base ca5909b; documentation ideas only |
| be/worker-queue | d7e44eddc9da51ba7886a6e317e90ace894b7847 | NEW since supplied review: 37 files / ~8025 lines; reuse shared queue and process driver |

Remote reads used the connected GitHub app; `git fetch origin` refreshed local refs without merging. PR51 is merged. PR49/50 are historical original candidates, not dependencies requiring replay.

The worker branch contains actual shared queue tables, transactional admission, generation fencing, policies, supervisor/process driver, migration0001 and tests. Its source was imported selectively for integration without merging branches. Its ADR is numbered 0005 here to preserve design-lab ADR0004. No prior tests on that branch are treated as current evidence; all are rerun. OR migration0002 extends shared metadata instead of creating another compute queue.

| Component | Action | Reason |
|---|---|---|
| BE01–06 | Retain | Strict independent method/mode, topology, dated ceilings, Fraction floor/status gate/history |
| Forecast schemas/preparation/providers/evaluation/handoff | Retain | Preserve constant29, genuine fractions, basis mismatch and proxy authorization |
| Inventory projection | Adapt via shared pure recurrence | Preserve experimental null expiry while OR excludes unknown expiry |
| Worker branch | Reuse and extend | One shared expensive lane, no queue vendor; OR adds real handlers and checked partial publication |
| Public health | Retain exact contract | Process liveness remains cheap |
| Domain public API, session/proxy, generated contracts | Add provisional Draft1 contracts | Absent from main/worker branch |
| Stock/history/receipt ledger | Do not duplicate | OR snapshots hold source identities; no physical writes |
| Design lab | Retain isolated prototype | Its illustrative values are not solver evidence |

Read ports: ForecastReadPort owns committed immutable forecast publication/results, InventoryReadPort owns authoritative stock plus source revision, OperationalReadPort owns routes/reserves/capacity snapshot consistency. These upstream committed LIVE ports are not implemented on main. Arbitrary client asserted LIVE packages must fail SOURCE_INTEGRATION_UNAVAILABLE. SIMULATED package publication persists complete normalized data and can qualify bounded OR integration only. `ready_for_publication` and a valid `ForecastHandoff` do not establish committed planning readiness.

Locks: root package-lock.json and apps/api/uv.lock retained. API dependency lock includes OR-Tools9.15.6755. Runtime and exact validation commands are in ACCEPTANCE.md. Historical PP30 reports are retained as historical evidence.

Ownership: lead integrates shared schema/config/API/contracts; [research](../pantrypulse/tasks/OR-RESEARCH.md), [pure inputs/projection](../pantrypulse/tasks/OR-PURE.md), [storage](../pantrypulse/tasks/OR-STORAGE.md) are disjoint parallel lanes. Existing #54 issue owners remain; assignment is GestebanFalcon. Paused supplier/Chronos hosting remains separate.
