> Historical pre-correction scope/evidence. Adjacent implementation is archived, not active on this OR branch. [Current scope and handoff](SCOPE-CORRECTION.md) supersede its implementation instructions/status.

# OR saved-result explanation milestone — October 24, 2026

Base: `46ff0cd` on `or_pipeline`, plus the working tree. The user requested actual
team-facing backlog issues before more implementation, then a stop at the next
substantial tested milestone for their commit.

## Backlog organization

Created [#59–#66](PRODUCT-BACKLOG.md) as product backlog items with user outcomes,
readiness, existing technical links, acceptance criteria and dependencies. #54
indexes them; #48, #37 and #43 retain their original bodies with refinement links.
#59–#62 are assigned to GestebanFalcon. No prior issue or spec was replaced or closed. #48/#63 are also assigned to GestebanFalcon for backlog/documentation follow-up.
Remote main was `873d3569` (preview-documentation merge); this work continues the
user's committed OR branch without merging unrelated branch changes.

## Implemented scope

- #59: typed frozen assumptions in the existing safe scenario summary, derived only
  from immutable saved bytes: local planning/forecast dates, snapshot time, demand
  multipliers/effective methods/buffers and actual policy. Generated OpenAPI and
  TypeScript updated. Raw source packages retain presenter-only payload access.
- #59: separate draft controls from frozen comparison identity; unapplied-change
  disclosure; old saved work remains accessible after freezing a new scenario.
  Job reads publish labels/plans/comparison together and reject late responses
  from a previous selection. Saved result/scenario hashes must agree.
- #60: results lead in DOM, keyboard and mobile reading order, with a compact
  per-product service outcome in the scenario card and accessible editor links.
  Transfer lists collapse with checked recommendation counts; beneficiary columns
  stay visible while keyboard-scrolling service and policy tables.
- #61: actual per-product beneficiary gains/losses and unchanged counts; common
  units stay separate. Saved policy details expose exact ratios, vulnerability
  multipliers, weighted deficits, quantized q values, current-group means and
  strict AP/RP thresholds. Rounded decimal displays are identified. Missing methods
  cannot produce a comparative gain, and terminal missing methods are unavailable.
- #62: extended actual PostgreSQL/API/production-supervisor/Chromium flow covers
  refreshed 1.5× saved work, draft edits/new freezes/history, delayed real old
  metadata, zero-stock comparisons and cancellation retaining only classical.
  No mocked response is passed off as a native solver result.

## Verification and visual review

The full configured gate passes all ten steps on a source tree unchanged during
verification. [Exact gate report](evidence/quality-explanations.json) records the
checked source fingerprint, base SHA and timings. Test coverage: 928 API/process/
PostgreSQL tests (787 non-integration plus 141 real PostgreSQL integration), three
proxy tests, 17 configuration tests, generated contracts and 20 decision mappings.
Web/API lint, TypeScript and the production build pass.

All eight Chromium tests pass in 59.0 seconds, including five complete rehearsals
and actual zero-stock/cancelled-partner cases. [Sanitized browser evidence](evidence/browser-explanations.json)
records real identities and states. OR page errors in the five rehearsals: none.
`git diff --check` and byte comparison of the three supplied specs also pass.
No implementation changed after the successful gate; this result and its reports
were appended to documentation afterward.

Intermediate
failures reproduced the missing metadata/UI before implementation. A test initially
expected 403 for a public package summary; the actual intended contract is 200 with
`payload=null`, and that boundary remains tested.

Independent screenshot review under `.claude/skills/visual-review/SKILL.md` found
outcome placement, long transfer lists and undersized jump targets. A focused repair
cycle fixed all three; recapture confirmed the repairs. Expanded policy values were
visibly reviewed. A later partial-result finding (“Waiting” after cancellation)
was repaired and covered by a browser assertion. Human visual taste approval and
broader V5 screen acceptance remain unverified.

Reproduction: dedicated local PostgreSQL `*_test`, locked Node/npm/uv dependencies,
`node scripts/quality/run.cjs full` and `npm run test:e2e:or`. Browser credentials are
random/in-memory; the harness owns and removes its schema/processes. Logs/screenshots
stay under ignored `artifacts/or`; sanitized reports are in `evidence/`.
Environment: Linux, Python 3.12.13, OR-Tools 9.15.6755, PostgreSQL 16.15,
Node 24.16.0/npm 11.13.0. Solver settings/mathematics/policy identities are unchanged.

The quality-gate configuration and untracked CI workflow already existed before
this milestone and remain preserved. A local passing gate does not qualify a
hosted Actions run. The user owns the commit; no staging, push or deployment occurs.

## Remaining work

- #62: human visual acceptance and broader state/accessibility review; OR-A11 remains
  bounded to observed evidence, with no automatic subjective sign-off.
- #63: concrete decision alternatives/revisit triggers, wider V5/OPEN reconciliation,
  intentional quality/CI commit and actual hosted Actions evidence.
- #64/#65: committed forecast publication and authoritative stock/operational read
  adapters. #66 then qualifies the real committed-source journey (OR-A12).
- Original technical and wider product issues retain their unfinished scope.
  Supplier #45, Chronos #46 and hosting remain paused.

This tested milestone is ready for the user to commit. Suggested message:
`feat: explain saved OR assumptions and allocation trade-offs`. #54 and the broader
product are not finished.
