# Issue #21 — Internal stock transactions

These services implement the operational-v1 stock rules and BD-42–47. They do not
expose HTTP endpoints, authenticate a caller, import CSV, reserve plans or dispatch
real goods. Construct `StockActor` only after caller authorization; its actor and
organization are trusted server context, never a browser-supplied permission flag.

## Entry point and transaction ownership

`execute_stock(session, actor, request)` accepts typed internal requests from
`app/schemas/stock.py`. The caller owns the SQLAlchemy transaction. The service uses
a savepoint and never commits independently. A returned `APPLIED` result must not
be exposed as durable success until the caller's outer transaction commits.

- `PostReceipt`: explicitly post the latest non-void recorded revision. Every line
  requires an eligibility/expiry declaration. Creates the original posting, lots,
  ledger entries, inventory versions, command outcome, reconciliation marker and
  audit atomically. A different key cannot post the same receipt twice.
- `AdjustStock`: signed, nonzero, exact integer deltas on explicitly named existing
  lots, with a reason and source reference. No negative balances or BIGINT overflow.
  Ledger sum must match the cached physical balance before changing it.
- `DeclareLot`: audited eligibility/expiry changes without fabricated zero-quantity
  ledger entries. Increments inventory and metadata versions; immutable audit keeps
  before/after declarations. Unknown/held/ineligible stock stays unavailable.
- `ReconcileReceipt`: reconcile the latest factual revision against the last
  physically reconciled revision. Apply incremental deltas, not a second full
  receipt. New lines need explicit declarations and may create lots linked to a
  later revision while preserving the original posting. Receiver/product changes
  reverse the old units and create the replacement only when all stock checks pass.
  Void revisions implement posted cancellation with the same nonnegative rule.
- `ConfirmSupply`: explicitly change/cancel outstanding confirmed units using
  expected inventory and supply versions. Does not change on-hand stock. A downward
  receipt correction never creates a new arrival promise; reconfirmation is explicit.

Each receipt request carries **the complete desired supply allocation** for that
revision, not incremental allocation deltas. Empty `supply_matches` explicitly means
no units matched to expected supply. The caller must identify matches; the service
does not guess which incoming event a donation satisfies. Supply IDs/versions must
cover all prior nonzero allocations plus desired matches. Positive matching uses
only outstanding confirmed units; reducing received units never restores outstanding
units automatically. Allocation reversals preserve original immutable entries.

## Concurrency, replay and audit

The service serializes each organization/schema/idempotency key with a PostgreSQL
transaction advisory lock. SHA-256 identity includes the operation, trusted actor,
organization, exact values, reason and expected versions; unordered target lists
are canonicalized. Same key and payload returns the original saved outcome even
when original expected versions are now old. Changed payload/actor conflicts.
Replay does not increment versions or add ledger/audit entries.

Receipt operations first lock the receipt identity. All stock operations then
initialize/lock affected site/product inventory versions in UUID order, lock lots
in UUID order and lock matched supplies in UUID order. Each affected version pair
must be supplied exactly once; missing/extra pairs and stale versions are rejected.
Historical receipt appends also lock the receipt and atomically flag a newer factual
revision as needing reconciliation. Supply counters are checked against their
allocation history before mutation; corrupted counters are not silently repaired.

Successful commands retain immutable outcomes and audit with source revision,
lot count/declaration changes, supply counters and inventory versions. Failed
commands leave no successful idempotency record or partial physical changes.
Expected stock/supply version conflicts are internal `StockError`s with status 409;
invalid business input uses 422 and scoped missing records use 404. Public error
envelopes and endpoint mappings remain owned by #12/#34.

## Corrections versus physical facts

Commit a factual revision in its own caller-owned transaction before attempting
its stock reconciliation. A later failed stock command cannot roll that earlier
transaction back. When consumed stock prevents a correction/cancellation, physical
stock/ledger/allocation counters remain unchanged and the existing factual mismatch
marker remains visible. Do not clamp to zero or erase the correction. History APIs
must distinguish factual latest revision from physically reconciled revision.

`inventory_versions_match` allows later planning readers to detect stale inventory
without rewriting saved snapshots. No scenario tables exist in this work; automatic
scenario status publication awaits their owning issue. Source revision identity and
policy/mode freshness remain separate checks. `eligible_lots` is only a saved-stock
date/eligibility filter, not a donor surplus, FEFO allocation, reserve or route proof.

## Migration and tests

`pp21_0002` follows applied `pp19_0001`. It replaces the old per-command allocation
unique key with positive/reversal partial unique indexes, allowing one correction
to reverse multiple original allocations of the same receipt line. The original
baseline is unchanged. A downgrade refuses incompatible newer data rather than
discarding allocation evidence.

Tests run in generated disposable schemas on the user-selected Neon branch, never
by posting fixture stock into public tables. See [PP-37 evidence](tasks/PP-37.md).
Full transaction services are Python-callable; public APIs remain a separate task.
