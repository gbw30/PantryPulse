# PantryPulse

V4 authority update (2026-10-23): Start with docs/architecture/0001-v4-research-first.md and docs/pantrypulse/IMPLEMENTATION-PLAN.md. V4 requires six beneficiary institutions plus hub(s), lot-aware FEFO and CLASSICAL_GP versus EGP_PI_INSPIRED with active AP/RP objectives. Older three-site/shortage-first rules below are historical where conflicting. Do not implement complex solver features before the research validation gate.

Build the Gator Hack V 48-hour MVP: three fictional sites, two resource categories, seven-day forecasts, and a 1–3-day simulated allocation window. Preserve the current repository and user changes.

## Read first
- docs/pantrypulse/PROJECT-CONTRACT.md: scope, units, forecast and solver contracts.
- docs/pantrypulse/INVARIANTS.md: quantitative truth conditions.
- docs/pantrypulse/ART-DIRECTION.md: approved visual direction.
- docs/pantrypulse/TASK-PROTOCOL.md: ownership, review and integration.
- docs/pantrypulse/DEMO.md: reset and judge journey.
- docs/pantrypulse/BOARD.md: delivery board; task packets live in docs/pantrypulse/tasks/PP-NN.md.
- Reference only, don't preload: docs/pantrypulse/SOURCE-SPEC.md (original PRD), docs/pantrypulse/HANDBOOK.md (orchestration rationale), docs/pantrypulse/templates/ (scaffold fragments for the lead), docs/pantrypulse/ENVIRONMENT.md (toolchain and config verification status).

## Delivery
- Lead owns contracts, migrations, lockfiles, shared configuration, integration, deployment and scope.
- Forecast/projection, solver/data, and frontend work in separate contexts and isolated worktrees. Delegate only bounded work with an explicit base SHA and write boundary. Do not spawn nested workers by default.
- Read-only verifier and UX critic are milestone gates. They report evidence; only the lead integrates. A reviewer does not approve its own changes.
- Never count a skipped, missing, disabled, timed-out, or fixture-only check as application validation.
- Run focused tests before handoff; run full gates on the merged candidate. Report exact commit, commands, results and unresolved limitations.

## Superpowers methods
Superpowers (`superpowers@claude-plugins-official`, reviewed at v7.0.1) supplies engineering methods. The PantryPulse lead stays the orchestrator, and the project agents keep their roles. Precedence, highest first:
1. The approved PRD (docs/pantrypulse/SOURCE-SPEC.md as resolved by the accepted decisions in PROJECT-CONTRACT.md) and the demo acceptance criteria.
2. Contracts, invariants and deterministic fixtures.
3. This file, the rules, the agent definitions and the task packet.
4. Superpowers skills.

When a skill conflicts with a project constraint, keep the project rule and use the compatible form below. Never weaken verification or approved product behavior. Full rationale: HANDBOOK.md, Amendment A1.
- **Every lane:** `verification-before-completion` (mandatory: run the commands and read their output before any pass/fixed/deployed claim), `systematic-debugging` (mandatory: root cause before fixing; the two-failed-fix limit below still applies), `test-driven-development` (failing test first for inventory, forecasting, optimization, simulation and API logic; delete only code you wrote in this task) and `receiving-code-review`.
- **Lead only:**
  - `writing-plans`: run once, from the approved PRD. Save the plan to docs/pantrypulse/IMPLEMENTATION-PLAN.md, track tasks on BOARD.md, and turn each task into a PP-NN packet.
  - `brainstorming`: only for decisions that are genuinely open. Don't redo settled requirements.
  - `subagent-driven-development`: selective, for complex independent tasks only. Dispatch the project builder agent for that domain with a packet, never `general-purpose`. At most three builders, no nested workers, and no per-task review cycle for trivial UI changes.
- **`using-git-worktrees`:** the lead creates worktrees at the packet's exact base SHA. Builders started with `isolation: worktree` are already isolated: they check their base and never create a nested worktree.
- **`requesting-code-review`:** the reviewer is the project `verifier` agent (or `ux-critic`/`adversarial-reviewer`), given the requirements, diff and tests before any builder rationale. Review depth scales with risk.
- **`finishing-a-development-branch`:** builders use it only to check readiness, then hand back their commit and evidence. Builders never merge, push, open PRs or discard. The lead integrates; shared-branch merges, discarding work and cleanup of a dirty worktree need the user's approval.
- **Other skills:** use them when directly relevant. Run `diagnosing-superpowers` only on request, and never file issues without the user's approval.

## Product truth
- Forecasts are projections. Label simulated/proxy data and actual model/fallback provenance.
- Preserve null/missing demand; never silently turn it into zero. No future leakage.
- Raw quantiles are not calibrated intervals or stockout probabilities.
- Preserve inventory, units, reserves, capacities and solver status. Do not sum different category quantities into an unlabeled inventory KPI.
- Keep forecasts immutable; save scenario and planning inputs. Stale inventory versions return 409.
- P0 review is a simulation with no reservation or dispatch. Real approval/completion is P1 and requires atomic reservations and idempotency.
- An LLM never directly approves or changes inventory.

## Commands after scaffold
- Quick: node scripts/quality/run.cjs quick
- Full: node scripts/quality/run.cjs full
- E2E: node scripts/quality/run.cjs e2e
- Config tests: node --test scripts/quality/tests/*.test.cjs
Gate commands are declared in .claude/quality-gate.json. Create and validate the application commands before enabling Stop enforcement. Do not install this kit's templates over existing manifests.

## Operating limits
- Two materially different failed fixes: return a minimal failing case to the lead.
- A council is one proposal, one critique, one domain check and one lead decision, capped at 10 minutes.
- Feature freeze at hour 41; only demonstrated P0 blockers afterward.
- Keep secrets out of prompts, logs, fixtures and client bundles. Use only dedicated demo/test databases.
- Do not bypass permission controls. Writes outside the named repository, destructive operations, new paid services, production changes and submission need the user's corresponding authorization.
- Do not edit another worktree, force-push, reset away work, or remove a dirty worktree.
