# ADR 0002: Frontend UI libraries

> **Current authority:** [Project specification V5](../pantrypulse/SPEC-V5.md). This ADR retains the accepted UI stack. V5 consolidates project status, integration boundaries, UI requirements and unresolved work.

Date: 2026-10-23. Status: accepted for the MVP dependency stack.

## Decision

Use Tailwind CSS for styling; shadcn/ui with Radix primitives for controls; Recharts for quantitative charts; Motion for animation; Lucide for icons. Watermelon and Kokonut are approved supplementary component-source registries. Standardize copied components on PantryPulse's shared tokens rather than maintaining independent themes.

Installed additions: motion 14.6.0, tw-animate-css 1.4.0 and local development CLI shadcn 4.22.1. Existing Recharts, Lucide, Tailwind, Radix Slot and helper dependencies remain. Runtime imports and transitive versions are pinned through package-lock.json. Only the component CLI and CSS/registry foundations are prepared; no application interaction or component catalogue was generated in this change.

## Scope and boundaries

- Recharts renders backend results; Python owns forecasts, optimization, deprivation metrics and objective decomposition. Keep axes, units, category boundaries and input snapshots comparable across methods.
- Motion handles UI state transitions and the 2D distribution network. Respect reduced motion, retain exact results and report real pending/status information. No synthetic allocation animation while a solve is incomplete.
- tw-animate-css handles primitive CSS transitions; it is not a second JavaScript animation library.
- Prefer narrow Next.js client components for interaction and animation. Keep the root layout/server rendering boundary intact.
- Configure Watermelon/Kokonut through components.json; add only selected source/components and their dependencies. Keep the Radix primitive base consistent, adapting a component if it introduces another base.
- Additional Radix packages are installed with their corresponding component source, not as a blanket dependency collection.

The installation guide contains the final list and pinned local CLI commands. Component installation is a source mutation and should be followed by lint/typecheck, source/lock review, and relevant browser checks.

## Alternatives

Three.js/React Three Fiber are deferred because spatial camera/rendering work is unnecessary for the six-beneficiary network. Use CSS depth/isometric styling and Motion first. React Spring is excluded to avoid a second JavaScript animation system. Bklit is excluded to keep one chart implementation. Godly and Variant remain visual references with no runtime dependency. Full 3D or a different chart engine requires a later explicit architecture decision.

## Sources

- [shadcn manual setup](https://ui.shadcn.com/docs/installation/manual) and [registry namespaces](https://ui.shadcn.com/docs/registry/namespace).
- [Motion installation](https://motion.dev/docs/react-installation) and [reduced-motion guidance](https://motion.dev/docs/react-accessibility).
- [Watermelon installation](https://ui.watermelon.sh/installation).
- [Kokonut installation](https://kokonutui.com/docs).

Documentation and CLI configuration were checked during setup. Individual third-party component behavior/accessibility still needs validation when chosen.

## Later bounded exception

On October 24, 2026, the user explicitly retained optional Three.js only in `/design-lab`. [ADR 0004](0004-design-lab-3d-exception.md) records the tradeoffs and constraints. The production stack above remains unchanged.
