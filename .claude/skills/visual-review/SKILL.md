---
name: visual-review
description: "Review PantryPulse visual and interaction evidence against the chosen direction, and compare a built screen against a user-supplied reference image when one exists."
---

Read ART-DIRECTION.md. Capture or request existing authorized viewport evidence at 1440x900, 1280x720 and 390x844. Exercise baseline, shortage, plan, changed assumptions, stale state, loading, errors, fallback and empty results. Check keyboard, reduced motion, focus return and textual chart alternative. Give ux-critic screenshots and observations, without builder rationale. Limit each pass to five ranked findings. Apply accepted repairs, recapture and get human taste signoff. Source-only review is not visual verification.

## Reference image comparison

Use this only when the screen's packet lists a reference image under docs/design/reference/ (see its README). Don't apply it to every UI change, and after the hour-41 feature freeze use it only for demonstrated P0 visual blockers.

- **Precedence:** SPEC-V5 section 14, ART-DIRECTION.md and .claude/rules/frontend.md beat the image. The image sets layout, hierarchy and density only. Mockup numbers, copy, colors or states that conflict with the contract are reported as spec conflicts, not copied.
- **Capture:** in the builder's own worktree, add or extend a focused spec under apps/web/tests/e2e/ that follows the design-lab.spec.ts viewport loop (setViewportSize, `emulateMedia({ reducedMotion: "reduce" })`, full-page screenshot to `testInfo.outputPath`). Set `PLAYWRIGHT_PORT` to the lane port (3001–3003 per TASK-PROTOCOL.md); `reuseExistingServer` is on outside CI and would otherwise capture another checkout's server. Run only that spec: `npx --no-install playwright test tests/e2e/<screen>.spec.ts --project=chromium` from apps/web.
- **Compare:** open the reference and the capture for the same width with Read and list the differences in layout, hierarchy, spacing, density and missing regions. One focused repair cycle per milestone, at most five findings per round (ART-DIRECTION.md), and the two-failed-fix limit. Don't keep iterating toward pixel matching.
- **Handoff:** the builder reports its final screenshots, the difference list from its round and any spec conflicts. The lead gives ux-critic the reference image, the user's spec and the candidate commit's viewport-tagged screenshots, without builder rationale. Human taste acceptance and the keyboard walkthrough remain required; screenshots alone don't close V5-A17.
- **Accessibility:** call `expectNoSeriousA11yViolations` from apps/web/tests/e2e/a11y.ts in the screen's spec, enforcing for product screens. Its results are supplementary evidence only.
- **No pixel baselines yet:** don't add `toHaveScreenshot` baselines for mockup matching or regressions until a product screen is human-accepted, Playwright is exact-pinned by the lead and baselines are generated in one controlled environment.
