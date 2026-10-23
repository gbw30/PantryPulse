# PantryPulse art direction

Direction: **calm community operations desk**. The interface feels like a carefully typeset logistics ledger with a living resource network. It helps a coordinator see risk, an action and its consequence. This is a proposed default for human approval, not an inferred existing brand.

## Composition and identity

Use a cool chalk canvas, white surfaces, navy ink, dark teal action, brick-red risk, ochre caution and muted blue forecast. Keep risk semantics stable across cards, chart and plan rows. Do not imply probability with color intensity. Use text and shape alongside color. Fine route/ledger rules and compact site identifiers connect the look to resource coordination.

Choose IBM Plex Sans for operational copy and numbers, and its condensed companion sparingly for page identity and site labels, with local/system fallbacks. Self-host licensed fonts where practical; avoid a runtime font dependency during the demo. Use tabular numerals, a 4px spacing base, 6/12/18px radius scale, thin dividers and one restrained shadow. The supplied CSS tokens are a starting point; verify contrast on rendered surfaces before acceptance.

At 1440x900: compact top bar with PantryPulse, current scenario, last updated and Simulated network pill. Show a short operational headline, category selector and main plan action. Put the seven-day shortage timeline at the center of attention. Beside it, show the three named sites and a clear first-deficit label. Underneath, the transfer explanation and before/after comparison make the recommended action concrete. Use at most three to four comparable summary measures. Each inventory/demand measure names category/unit and horizon.

At 390x844: preserve scenario identity and at-risk summary first. Stack timeline, site rows and plan. Use a horizontally scrollable data table only where row/column relationships need it, with a clear hint and accessible labels. Do not shrink charts until quantities become unreadable. At 1280x720 keep the plan CTA visible without an oversized hero.

## Semantic component vocabulary

SiteRiskCard; ForecastBandChart; ShortageTimeline; ResourceFlow; TransferRecommendation; ConstraintBadge; ProvenancePill; SolverStatus; ScenarioDelta; BeforeAfterMetric. Build these over consistent accessible primitives. shadcn defaults are foundations; token choice, density, hierarchy and domain language supply the product's identity.

Charts have labeled category/unit axes and a visible historical/forecast boundary. Use a solid historical series, distinguish forecast by dash/region and add a labeled uncertainty fill only when available. Provide a text summary and expandable data table. Plan rows read “Central → North · 40 meals · arrives before day-one demand” with donor reserve, receiving/handling utilization and projected benefit in details. Keep unresolved shortage prominent after optimization.

## Motion contract

| Interaction | Purpose | Duration guideline | Reduced motion |
|---|---|---|---|
| Open site detail | Preserve site identity and focus | 160–220ms | immediate/short opacity |
| New plan rows | Explain changed transfers | 180–280ms stagger capped | immediate update |
| ResourceFlow | Show direction of simulated recommendation | one brief 500–800ms pass | static arrow and label |
| Before/after metric | Connect solve to resulting quantity | 250–400ms after real response | exact number immediately |
| Draft scenario edit | Show unapplied change | immediate dirty badge | same |
| Loading | Identify pending operation | stable skeleton/status | no pulsing required |

Guidelines are design choices, not framework guarantees. MotionConfig reducedMotion="user" plus useReducedMotion/custom CSS should cover both Motion and custom effects. Avoid infinite beams, particle fields, glass cards, rainbow borders, oversized AI badges, generic marketing copy and animated axes that make comparison difficult. Number animation must never announce every intermediate value through aria-live; announce the completed meaningful result once.

## State and interaction QA

Review default, filtered, first shortage, plan result, unresolved shortage, no transfers needed, insufficient data, Chronos degraded, queued/running, failed solve, stale plan and network failure. Mark baseline versus scenario before users compare figures. Disable repeated submission while busy; offer retry and retain last successful state. Sliders show exact values and keyboard input; Recalculate is explicit. Use stable row keys for site/category/routes rather than array indices.

Keyboard walkthrough must reach filters, site details, chart data alternative, plan explanation, scenario editor, submit and close. Focus returns to the invoking control after closing a drawer; modal focus stays contained. Tooltips are supplemental; crucial values do not depend on hover. Verify text contrast, visible focus, labels and touch targets. Automated accessibility checks help; keyboard and screenshot review remain required.

## Critique protocol

Generate two or three composition sketches within 20 minutes, choose one with the human, then freeze tokens and component vocabulary. If the human is unavailable, implement this default and record the assumption; human visual acceptance remains pending. Capture the real seeded app at 1440x900, 1280x720 and 390x844. Send screenshots and interaction observations to ux-critic. Maximum five findings per round with viewport, region, severity and acceptance check. Fix comprehension/accessibility blockers first. One focused repair cycle per milestone; the human decides subjective taste disagreements.

Target: identify at-risk site/first deficit/action in ten seconds and explain the transfer within thirty seconds during rehearsal. These are usability goals to measure, not established results. A source-code-only critic cannot declare visual QA passed.
