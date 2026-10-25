# ADR 0004: Optional 3D in the isolated design lab

Date: October 24, 2026. Status: accepted prototype exception by explicit user decision.

The user chose: “Keep 3D only in /design-lab and document an explicit prototype exception.” This follows review of PR #50 against V5 section 14.2 and ADR 0002.

Allow Three.js and its types solely for the optional `/design-lab` experiment. Keep the default view 2D, load Three.js only when the 3D component mounts, provide a 2D return path on initialization failure, retain a keyboard-accessible location selector and respect reduced motion. Label the example as simulated at every viewport. This exception does not approve Three.js for the production dashboard, select a final visual design, or replace the accepted Tailwind/shadcn/Radix/Recharts/Motion/Lucide stack.

Tradeoffs: keeping the experiment preserves spatial comparison and the work already done, but adds dependency size, GPU/WebGL compatibility and lifecycle maintenance. Removing it would simplify dependencies and verification while losing the optional 3D comparison. The user selected retention within the bounded route. Revisit the exception before any production use; removing the optional component and dependencies is the rollback path.

Amounts and routes remain illustrative proposals. No allocation computation, confirmed movement, stock change or dispatch is established by the prototype.
