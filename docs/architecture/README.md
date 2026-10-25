# Architecture decisions

Start with [Project specification V5](../pantrypulse/SPEC-V5.md), the current source of truth for accepted requirements, main/branch implementation status and open work. [ADR 0001](0001-v4-research-first.md) preserves the research-first architecture and gate; its illustrative policies yield to later accepted decisions in V5. The older [implementation plan](../pantrypulse/IMPLEMENTATION-PLAN.md) is a historical roadmap.

The finalized frontend libraries and component registry policy are recorded in [0002-ui-stack.md](0002-ui-stack.md).

PR #51 integrated the offline core from PR #49. [ADR 0003](0003-forecasting-core.md) records its experimental shared-contract boundary; V5 retains the historical main/branch baseline.


[ADR 0004](0004-design-lab-3d-exception.md) records the user-approved optional 3D exception limited to `/design-lab`.

[ADR 0005](0005-worker-job-queue.md) records the internal durable-job foundation from PR #52, including Linux containment, recovery and publication fencing. See the [worker queue runbook](../setup/WORKER-QUEUE.md) for verification and operating boundaries. Its provisional deployment decisions remain open.
