# PantryPulse task and integration protocol

## Task packet

Copy one packet per task into docs/pantrypulse/tasks/PP-NN.md. Lead creates it before delegation.

```text
Task ID and owner:
Goal and relevant FR/INV IDs:
Base commit SHA and worktree root:
Allowed write paths and explicitly excluded shared files:
Inputs and immutable contract/fixture versions:
Dependencies already merged:
Acceptance commands and expected outcomes:
Independent reviewer and review boundary:
Budget and checkpoint time:
Stop rule: two different failed fixes, missing dependency or required out-of-scope edit.
Handoff: final commit, diff summary, commands/results, evidence, unresolved assumptions.
```

Do not start with “build the entire backend.” A task should usually fit 30–90 minutes, produce one reviewable outcome and avoid a shared foundational file. Context includes relevant contracts, fixtures and requirements; it excludes unrelated prior conversations. Worker updates report evidence and blockers rather than a stream of speculation.

## Topology and delegation

Human owns product scope, taste, operational policy and external commitments. Main Claude session is Lead/Integrator. Active writing lanes: forecast/projection, solver/data, frontend/product. Lead supplies API/persistence foundations and integration. Verifier, UX critic and adversary run at milestones; integration-fixer is temporary. This is four lanes including lead, not eight permanent agents. Start with fewer if compute, account capacity or lead bandwidth is limited.

Read-only perspectives can be parallel where useful. Do not let multiple builders write the same files. Directory boundaries are instructions, not a security boundary; worktrees isolate file changes, and permissions govern tools. Reviewers with shell/test access can create test artifacts and still need normal permissions; Read/Grep/Glob alone is stronger for a source-only critic.

Bounded council: use only for an ambiguous high-impact choice. Lead asks proposer for a recommendation, skeptic for a counterexample, domain reviewer for spec conflicts. Cap at ten minutes and one round. Lead writes ADR decision/evidence/alternatives/rollback trigger. No voting or repeated consensus loop. Routine changes use one builder plus objective tests.

## Worktree strategy

Commit the accepted scaffold/config/contracts before parallel work; new worktrees do not inherit uncommitted changes. Record the exact foundation SHA. Native worktrees may start from the default branch rather than the parent's current HEAD. Workers must check their HEAD before editing. A mismatch is a dependency error, not permission to silently work from old contracts.

Reliable manual option, run by lead after substituting verified paths and SHA:

```text
git worktree add -b pp/forecast ../pantrypulse-forecast BASE_SHA
git worktree add -b pp/solver ../pantrypulse-solver BASE_SHA
git worktree add -b pp/frontend ../pantrypulse-frontend BASE_SHA
```

Start a normal Claude session inside each explicit worktree and provide the role/task packet. To use the supplied isolated subagent definitions from the lead instead, delegate with the matching type and confirm returned worktree/base. If a newly created isolated worktree is clean but on the wrong base, lead can explicitly authorize a non-forced new task branch at BASE_SHA inside it. Never realign a dirty worktree or delete its changes. Do not start a second isolated subagent inside a manually isolated worker session unless needed; that adds another checkout and base to track.

Give each running app its own web/API ports and isolated database/schema or branch: for example lane1 3001/8001, lane2 3002/8002, lane3 3003/8003. The normal integration pair is 3000/8000. Install dependencies per worktree; do not share writable node_modules or .venv. Migrations/seeding against a shared dev DB are lead-only. Never run tests/reset on a production URL. Provision secrets privately in each environment; do not copy credential files into worktrees automatically.

At task finish the worker commits only owned files, reports SHA and leaves worktree intact. Lead reviews an immutable candidate. After integration and verification, stop active processes, inspect git status and confirm all useful commits are retained before removing a clean worktree. Do not force-delete or prune another session's checkout.

## Integration gate

1. Verify base SHA, write boundary and acceptance evidence. Reject unexpected migrations, lockfiles or generated contract changes back to lead ownership.
2. Independent verifier gets task requirements, candidate diff and tests without the builder's rationale first. It derives at least one independent counterexample.
3. Findings require trigger, reproduction or precise code evidence, expected/actual and severity. Numerical invariant violations, leakage, misleading labels, security exposure and broken P0 paths block regardless of model confidence. A self-rated 80/100 is only a prioritization hint, never a calibrated probability or release gate by itself.
4. Builder receives the smallest failure evidence and fixes it. Two different failed fixes trigger lead diagnosis/contract review/simplification/rollback. Resume a worker where useful instead of spawning more duplicates.
5. Lead integrates one candidate into the integration branch by merge or cherry-pick according to repo policy. Shared changes land first. Abort conflicts if intent is unclear; do not mechanically choose ours/theirs.
6. Run full gates and E2E on the merged tree. Before merge tests do not prove the combined app works. Review fresh screenshots for changed screens. Record commit and source fingerprint.
7. Deploy an authorized preview, smoke-test the actual URL, update board and preserve last known good commit/URL. Every new merge invalidates prior combined-tree release evidence.

Do not auto-push, deploy or submit simply because a review passes. Existing user authorization for a named target persists; obtain a missing target/authorization only when the prepared result is ready for that action.

## Recovery and context hygiene

After compaction or a fresh session, read CLAUDE.md, board, current task, last accepted ADR and gate evidence. Inspect Git rather than assuming a chat summary is current. Keep handoffs concise. Record domain decisions in contracts, procedures in skills, role instructions in agent files, and mechanical checks in scripts. Do not grow CLAUDE.md into the handbook.

If the same mistake occurs twice across files, repair the shared validator/component/gate before continuing local patches. If lead spends more time reconciling work than landing it, reduce concurrency. Agent teams and dynamic workflows are optional, account/version-dependent mechanisms; no critical path depends on them.
