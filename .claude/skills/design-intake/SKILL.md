---
name: design-intake
description: "Lead only, main session: turn a user-supplied UI layout image plus a frontend design spec into a 'Design input' section of a PantryPulse PP-NN task packet before any frontend code is written. Use when the user attaches a layout image or design spec for a screen."
---

If you are a subagent (frontend-engineer, ux-critic or any worker), stop: intake belongs to the lead, who has the attached image and owns packets. Builders read the finished packet instead.

## Authority

The intake output is subordinate to docs/pantrypulse/SPEC-V5.md (section 14), docs/pantrypulse/ART-DIRECTION.md, docs/architecture/0002-ui-stack.md and 0004, docs/pantrypulse/INVARIANTS.md and .claude/rules/frontend.md. Point to them; don't copy them. The image supplies layout, hierarchy and density. Where the image or the user's spec conflicts with those documents (for example an unlabeled meal-plus-water total, a probability label, a missing required state, or a hardcoded result), record the conflict as an open question; never silently follow the image.

## Steps

1. Save each reference image as `docs/design/reference/<screen>@<width>.png` (width 1440, 1280 or 390) with a `<screen>.md` beside it, as docs/design/reference/README.md describes. Builders and ux-critic open these with Read.
2. Look at the image region by region before writing anything. Note what's ambiguous instead of guessing.
3. Write a `## Design input` section, about one page, into the screen's `docs/pantrypulse/tasks/PP-NN.md` packet (its Inputs field). Create the packet first if it doesn't exist (TASK-PROTOCOL.md).
4. Show the section to the user and resolve the open questions before delegating to frontend-engineer.

## Design input fields

- **Sources:** reference image paths and widths, the user's spec path, date. List missing widths.
- **Region map:** each region at 1440x900, with how it reflows at 1280x720 and 390x844 (order, stacking, what scrolls).
- **Vocabulary:** each region mapped to the ART-DIRECTION semantic components (SiteRiskCard, ForecastBandChart, ShortageTimeline, ResourceFlow, TransferRecommendation, ConstraintBadge, ProvenancePill, SolverStatus, ScenarioDelta, BeforeAfterMetric) or named as a new component for the lead to approve.
- **Primitives (select, never install):** each region's building block from what's already in the stack: an existing primitive, one named shadcn (new-york), `@watermelon` or `@kokonutui` item, Recharts 3.10, Motion 14.6 or lucide. Find items with the pinned CLI from apps/web (`npx --no-install shadcn search @kokonutui`, `npx --no-install shadcn view <item>`); never `shadcn@latest`. The packet lists the exact registry items the builder may add with `npm run ui:add -- <id>`; nothing else.
- **Tokens:** colors, type, spacing and radii mapped to existing `apps/web/src/app/globals.css` variables. Any new color or token is an open question for the lead and user; builders never add shared tokens. IBM Plex and motion timings remain proposals pending human acceptance (SPEC-V5 14.2).
- **States:** the SPEC-V5 14.1 states that apply to this screen (loading, empty, insufficient data, proxy warning, fallback, queued/running, failed with retry, partial comparison, method unavailable, FEASIBLE, UNKNOWN/MODEL_INVALID, validation failure, stale, 409, network failure), and how each looks, since a static image rarely shows them.
- **Data:** which values come from which API contract, and which are illustrative and must be labeled. Never hardcode a result shown in the image.
- **Accessibility and motion:** keyboard order, focus return, chart text/table alternative, contrast, reduced motion.
- **Acceptance:** the visual-review reference comparison at the three widths, the focused e2e spec, and `expectNoSeriousA11yViolations` enforced for the new screen.
- **Open questions:** numbered, each with the conflicting source.
