# VP API integration review

October 25, 2026. Review base main `9df7c51`, VP `35615a6`, integration branch
`codex/vp-api-integration`. The user approved keeping main's contracts, immutable
planning storage, independent verifier and 120–300-second budgets canonical, and
adapting VP's additional plan/review APIs to them.

## Retained and reconciled changes

- Current inventory inspection with exact decimal-string quantities, disjoint
  eligibility/expiry exclusions and no read-side stock mutation.
- Audited version-checked inventory adjustments; receipt history, explicit posting
  and reconciliation; lot declarations; supply creation/confirmation/cancellation.
- Bounded JSON/CSV demand and donation-coverage imports preserving missing values,
  immutable revisions, tenant ownership and idempotent command replay.
- Dashboard inventory and dated shortage reads using the committed forecast
  authority and main's inclusive expiry kernel; no inference on GET.
- Single-method plan submissions and simulation reviews integrated with canonical
  frozen scenarios, the shared queue, equal solver settings and independent replay.
- VP history, task records and original migration files remain preserved. Historical
  VP planning records use a separate read-only contract family and are never
  silently reinterpreted as executable main-v2 inputs.

## Contract convergence

| Earlier VP interface | Integrated interface |
|---|---|
| Arbitrary executable `/or/input-packages` and separate `/or/policies` | Main `/planning-assumptions`, `/planning-catalog`, and server-captured `/scenarios`; no client assertion establishes source commitment/freshness |
| Competing POST/GET `/scenarios` and GET `/comparisons/{id}` shapes | Main contracts preserved; GET `/scenarios` additionally lists saved canonical scenarios |
| `or-allocation-v1` / `or-comparison-v1` with short fixed budgets | `or-allocation.v2` / existing `or-comparison.v2`; selected 1–300 s native search, default 120 s; unchanged frozen-input retry semantics |
| `/scenarios/{id}/plans` | Same path, canonical scenario hash, explicit method and optional search_seconds |
| `/scenarios/{id}/compare-methods` | Compatibility submission route delegates to canonical POST `/comparisons` |
| `/plans/{id}` and `/plans/{id}/review` | Verified canonical method result and append-only REVIEWED/REJECTED simulation event; no reservation, dispatch or stock change |
| Existing VP persisted scenario/plan/comparison | Authenticated GET `/legacy-planning/{kind}/{id}`, labeled VP_LEGACY, historical and non-executable |

New plans can come from one method or a verified partner in a comparison. Main's
older comparison method records remain readable through the plan interface without
rewriting saved evidence. Reviewing such a record materializes a new immutable plan
reference and review, preserving its original payload. Failed partners never become
verified plans; main's honest PARTIAL comparison behavior is retained.

## Migration and rollout

New head `ppvp_0007` joins `ppor_0005` and `pp49_0006` and adds canonical
`planning_plans` / `planning_reviews`. HTTP command journaling and historical OR
migrations remain byte-for-byte preserved. All planning/review/journal histories
remain immutable. Tests upgrade fresh schemas and both pre-existing planning heads,
assert preserved payloads/triggers, then downgrade disposable schemas.

Do not migrate a running shared service implicitly. Stop/drain its old worker,
select the dedicated target schema and direct database URL, migrate deliberately,
then start the current production registry. Old unmerged VP job contracts are not
registered for execution; their records remain historical. No live database or
production service is modified by this review.

The connected adapter retains main's bounded simulated scope and rejects
outstanding confirmed supply without expiry declarations. General import APIs are
added; a general import/data-management UI, visitor access, operational dispatch,
supplier planning, Chronos application registration and deployment remain separate.

## Review findings corrected

1. **P1: competing planning contracts/runtime would break the connected workspace.**
   VP's raw-package scenario API, legacy handler IDs and shorter settings conflicted
   with main. The approved convergence preserves main's contracts/core and adapts
   plan/review additions. Old VP payloads remain in a non-executable legacy family.
2. **P1: two migration heads prevented a clean upgrade.** A successor joins both
   applied histories and adds canonical plan/review records. Prior migration files
   remain unchanged; tests preserve actual records/triggers across upgrades.
3. **P2: write locks crossed schema boundaries.** An actual concurrent transaction
   in another isolated schema blocked despite independent storage. The regression
   failed before adding current_schema() to lock identity, then passed afterward.
4. **P2: shortage reads accepted outdated calendar identity.** Equal timezone
   strings did not establish the saved calendar version. The current adapter
   rejects a changed version with 409, including same-timezone replacements.
5. **P2: forecast completion could precede catalog readiness.** A real browser
   receipt/import/forecast journey reproduced STALE_PLANNING_SOURCE on immediate
   freeze. The workspace now completes the catalog refresh before reporting ready,
   blocks freezing during forecast preparation, and fences older catalog responses.

## Verification

[Source manifest](evidence/vp-api-review.json) records the final changed source hashes,
base/VP identities, approved architecture and exact gate scope. Local verification:

| Gate | Result |
|---|---|
| Complete backend, real Linux containment and isolated PostgreSQL | **1206 passed, zero skipped**, 266.95 seconds; [JUnit](evidence/vp-api-backend.xml) |
| Full genuine browser/proxy/API/PostgreSQL/worker journey on production build | **11 passed, zero skipped**; [transcript](evidence/vp-api-browser.txt) |
| Configuration / proxy unit tests | **18 / 6 passed** |
| Types / ESLint / Ruff / production build / contract drift | PASS |
| Retained dense benchmark evidence | **20 outcomes independently replayed**, solver core unchanged |

The browser gate caught the stale-catalog race before the fix; the final rerun
passed on the rebuilt application. Historical-fixture retries use an immutable
idempotency key. A rerun during API restart was discarded as unavailable evidence.
No failed/skipped attempt is presented as passing.

 Tests include real Linux processes and isolated
PostgreSQL; skipped tests do not count as application evidence. The browser gate
runs the production UI and genuine browser/proxy/API/database/worker path, including
new operational writes, CSV transport, a single plan and simulation review.
