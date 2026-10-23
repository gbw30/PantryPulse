# PantryPulse release checklist

Unchecked boxes remain work, not implied success.

## Before parallel work

- [ ] Named repository path, allowed scope and existing changes inspected.
- [ ] Official event timing/rules/submission requirements confirmed.
- [ ] P0/P1 decisions and source ambiguities resolved in ADRs.
- [ ] API/data/provider/optimizer contracts and unit semantics frozen.
- [ ] Shared foundation committed; each task has exact base SHA and write boundary.
- [ ] Tokens, composition and semantic components chosen; human taste owner identified.
- [ ] Demo/test databases and worker ports separated; secrets absent from Git/context.

## Before each integration

- [ ] Candidate changed only assigned paths; dependencies and contracts current.
- [ ] Focused acceptance tests pass, including at least one independent edge case.
- [ ] Verifier reviewed requirements/diff before builder rationale.
- [ ] All demonstrated invariant/leakage/status/provenance defects resolved.
- [ ] Merged candidate passes full gates and the relevant E2E path.
- [ ] UI change has fresh desktop/mobile/reduced-motion evidence where relevant.
- [ ] No missing/skipped check represented as passed.
- [ ] Board, decision log and exact candidate commit/evidence updated.

## Before feature freeze at hour 41

- [ ] All FR-01–FR-15 rows accepted or explicitly marked unresolved; no quiet scope removal.
- [ ] Baseline forecast and real Chronos failure fallback work.
- [ ] OR-Tools allocations pass independent feasibility checks.
- [ ] Projection, stale version, import, scenario immutability and replay tests pass.
- [ ] Main judge journey asserts real data changes, not just visible headings.
- [ ] No numerical claim exceeds the supporting evidence.
- [ ] Correct category/unit/horizon and unresolved shortage displayed.
- [ ] Loading/empty/error/degraded/stale/unknown states usable.
- [ ] Keyboard/focus/chart alternatives/contrast/reduced motion reviewed.
- [ ] Public reset/mutations have an appropriate demo presenter boundary.
- [ ] CI workflow active after real command validation; no placeholder green checks.

## Before submission

- [ ] Frozen web/API/schema/dataset/model/solver release manifest recorded.
- [ ] Actual deployed URLs and CORS mapping smoke-tested.
- [ ] Full and E2E gates green on the release tree; evidence matches source fingerprint.
- [ ] Five clean reset-to-finish rehearsals, including cold/failure case.
- [ ] Local fallback and backup recording tested.
- [ ] README, limitations, provenance, architecture and setup committed.
- [ ] Video/screenshots/pitch meet organizer format and length.
- [ ] Team attribution, licenses and AI/sponsor disclosures accurate.
- [ ] Human reviewed final visual result and product truth claims.
- [ ] Submission authorized, submitted before verified deadline, link/playback checked.

P1 if implemented: atomic reservation, competing-approval conflict, idempotency, transactional completion and stock conservation tests must pass before approval/completion controls are exposed.
