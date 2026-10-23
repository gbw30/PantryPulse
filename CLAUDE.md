# PantryPulse

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
