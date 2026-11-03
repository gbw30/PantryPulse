# Documentation audit â€” October 25, 2026

Inspected source: main `647f6a8ccdb210de96204a314b62ae7d3d6b2701` through PR #99. This audit updates documentation only and preserves source-bound evidence, generated contracts, migrations, model experiments and existing application changes.

## Current documentation map

| Need | Current entry |
| --- | --- |
| Overview and limits | [README](../../README.md), [current status](CURRENT-STATUS.md), [SPEC-V5](SPEC-V5.md) |
| Install/run/recover | [installation](../../INSTALLATION.md), [setup index](../setup/README.md), [launch guide](../setup/LOCAL-LAUNCH-GUIDE.md), [local demo](../setup/LOCAL-DEMO.md) |
| Test/CI | [testing](../testing/README.md), [acceptance](ACCEPTANCE-MATRIX.md), [release](RELEASE-CHECKLIST.md) |
| Forecast/model | [forecasting](../forecasting/README.md), [jobs](../forecasting/CHRONOS-JOBS.md), [qualification](../forecasting/QUALIFICATION.md) |
| Planning/API/data | [connected planning](../optimization/CONNECTED-INTEGRATION.md), [API runbook](ALL-API-RUNBOOK.md), [contracts](../../packages/contracts/README.md), [migrations](../../apps/api/migrations/README.md) |
| Delivery/demo | [board](BOARD.md), [remaining plan](IMPLEMENTATION-PLAN.md), [demo](DEMO.md) |

## Corrections

- All four product views and data input are merged; `/optimization` redirects to Scenario Lab, root to Overview.
- Opt-in experimental Chronos and its frozen retail-proxy study are merged; complete model readiness and pantry/calibration claims remain unqualified.
- Planning accepts eight products; standard/extended seed sizes and old two-product benchmark/proof bounds remain distinguished.
- Visitor reads are implemented only for the configured saved catalog/dashboard/shortage subset.
- Migration head is ppvp_0007, not ppor_0005 or an empty migration directory.
- CI verify is a two-minute static/unit merge check; full is a separate parallel no-skips backend/PostgreSQL/contracts/build/browser gate. Superseded PR runs cancel; main runs are allowed to finish (#99).
- Tracked pp-local launchers, older copied-image video demos, historical Vercel preview and ignored machine-local helper scripts have different operational boundaries.
- Historical packets/proposals/ADRs retain body evidence; explicit notes route readers to current authority.

## Evidence limits

No complete application, model experiment, final holdout or deployment was rerun for this documentation audit. Existing test counts remain at their original source. The upstream `06dfc8d` CI run was observed in progress; see [that exact run](https://github.com/gbw30/PantryPulse/actions/runs/40228409442) for its verify/full outcomes. The local `647f6a8` builder-width commit is part of the source audit and had no corresponding hosted run at inspection. No hosted full pass is inferred for it. Documentation validation is recorded separately below.

## Files reviewed

Reviewed 165 first-party Markdown/MDX files (excluding agent instruction files, installed dependencies, generated runtime artifacts and personal data). Files without stale source/setup claims are retained. Existing JSON/XML/evidence/model artifacts were not rewritten.

## Updated files

| File | Change |
| --- | --- |
| [CHRONOS-LOCAL.md](../../CHRONOS-LOCAL.md) | Clarify historical evidence, decision, template or integration boundary |
| [EXTERNAL-SERVICES.md](../../EXTERNAL-SERVICES.md) | Clarify historical evidence, decision, template or integration boundary |
| [INSTALLATION.md](../../INSTALLATION.md) | Current implementation and procedure reconciliation |
| [README.md](../../README.md) | Current implementation and procedure reconciliation |
| [apps/api/migrations/README.md](../../apps/api/migrations/README.md) | Clarify historical evidence, decision, template or integration boundary |
| [apps/web/README.md](../../apps/web/README.md) | Current implementation and procedure reconciliation |
| [docs/architecture/0001-v4-research-first.md](../architecture/0001-v4-research-first.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/architecture/0002-ui-stack.md](../architecture/0002-ui-stack.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/architecture/0003-forecasting-core.md](../architecture/0003-forecasting-core.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/architecture/0004-design-lab-3d-exception.md](../architecture/0004-design-lab-3d-exception.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/architecture/0005-worker-job-queue.md](../architecture/0005-worker-job-queue.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/architecture/README.md](../architecture/README.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/design/specs/frontend-design-blueprint-v1.3.md](../design/specs/frontend-design-blueprint-v1.3.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/forecasting/DECISIONS-AND-ENHANCEMENTS.md](../forecasting/DECISIONS-AND-ENHANCEMENTS.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/forecasting/EXECUTION-PLAN.md](../forecasting/EXECUTION-PLAN.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/forecasting/MVP-COMPLETION.md](../forecasting/MVP-COMPLETION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/forecasting/QUALIFICATION.md](../forecasting/QUALIFICATION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/forecasting/README.md](../forecasting/README.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/01_OR_Mathematical_Specification.md](../optimization/01_OR_Mathematical_Specification.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/02_OR_Implementation_Design.md](../optimization/02_OR_Implementation_Design.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/03_OR_Codex_Execution_Spec.md](../optimization/03_OR_Codex_Execution_Spec.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/ACCEPTANCE.md](../optimization/ACCEPTANCE.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/BASELINE-RECONCILIATION.md](../optimization/BASELINE-RECONCILIATION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/CHECKPOINT-2026-10-24.md](../optimization/CHECKPOINT-2026-10-24.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/CHECKPOINT-EXPLANATIONS-2026-10-24.md](../optimization/CHECKPOINT-EXPLANATIONS-2026-10-24.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/CHECKPOINT-REVIEW-2026-10-24.md](../optimization/CHECKPOINT-REVIEW-2026-10-24.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/CONNECTED-INTEGRATION.md](../optimization/CONNECTED-INTEGRATION.md) | Current implementation and procedure reconciliation |
| [docs/optimization/DECISION-REGISTER.md](../optimization/DECISION-REGISTER.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/FINALIZATION.md](../optimization/FINALIZATION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/INTEGRATION-INTERFACE.md](../optimization/INTEGRATION-INTERFACE.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/NUMERICAL-PROOF.md](../optimization/NUMERICAL-PROOF.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/PRODUCT-BACKLOG.md](../optimization/PRODUCT-BACKLOG.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/QUALIFICATION.md](../optimization/QUALIFICATION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/README.md](../optimization/README.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/RESEARCH-MAPPING.md](../optimization/RESEARCH-MAPPING.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/SCOPE-CORRECTION.md](../optimization/SCOPE-CORRECTION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/optimization/SCOPE.md](../optimization/SCOPE.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/ACCEPTANCE-MATRIX.md](ACCEPTANCE-MATRIX.md) | Current implementation and procedure reconciliation |
| [docs/pantrypulse/ALL-API-RUNBOOK.md](ALL-API-RUNBOOK.md) | Current implementation and procedure reconciliation |
| [docs/pantrypulse/BACKEND-DATA-FLOW-SIMPLE.md](BACKEND-DATA-FLOW-SIMPLE.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/BACKEND-DATA-FLOW.md](BACKEND-DATA-FLOW.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/BACKEND-DESIGN-CHECKPOINT.md](BACKEND-DESIGN-CHECKPOINT.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/BACKEND-SPEC.md](BACKEND-SPEC.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/BOARD.md](BOARD.md) | Current implementation and procedure reconciliation |
| [docs/pantrypulse/CLAUDE-READY-BACKEND-PROMPT.md](CLAUDE-READY-BACKEND-PROMPT.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/CURRENT-STATUS.md](CURRENT-STATUS.md) | Current implementation and procedure reconciliation |
| [docs/pantrypulse/DEMO.md](DEMO.md) | Current implementation and procedure reconciliation |
| [docs/pantrypulse/DEPLOYMENT.md](DEPLOYMENT.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/ENVIRONMENT.md](ENVIRONMENT.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/FORECAST-API-FLOW.md](FORECAST-API-FLOW.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/FORECASTING-PROPOSAL-EVALUATION.md](FORECASTING-PROPOSAL-EVALUATION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) | Current implementation and procedure reconciliation |
| [docs/pantrypulse/INVENTORY-API-FLOW.md](INVENTORY-API-FLOW.md) | Current implementation and procedure reconciliation |
| [docs/pantrypulse/LOCAL-COMPUTE-EVALUATION.md](LOCAL-COMPUTE-EVALUATION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/LOCAL-VP-INTEGRATION.md](LOCAL-VP-INTEGRATION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/PR-75-REVIEW.md](PR-75-REVIEW.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/PR-77-REVIEW.md](PR-77-REVIEW.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/PROJECT-CONTRACT.md](PROJECT-CONTRACT.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/SCAFFOLD-VERIFICATION.md](SCAFFOLD-VERIFICATION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/SOURCE-SPEC.md](SOURCE-SPEC.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/SPEC-V5.md](SPEC-V5.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/VP-API-INTEGRATION.md](VP-API-INTEGRATION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/WINDOWS-DEVELOPMENT.md](WINDOWS-DEVELOPMENT.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/forecasting/IMPLEMENTATION.md](forecasting/IMPLEMENTATION.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/forecasting/PantryPulse_V4_Forecasting_Implementation_Plan(1).md](forecasting/PantryPulse_V4_Forecasting_Implementation_Plan(1).md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/OR-API.md](tasks/OR-API.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/OR-EXPLANATIONS.md](tasks/OR-EXPLANATIONS.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/OR-PURE.md](tasks/OR-PURE.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/OR-RESEARCH.md](tasks/OR-RESEARCH.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/OR-REVIEW-FIXES.md](tasks/OR-REVIEW-FIXES.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/OR-RUNTIME.md](tasks/OR-RUNTIME.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/OR-STORAGE.md](tasks/OR-STORAGE.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/OR-WEB.md](tasks/OR-WEB.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-09-forecasting-core.md](tasks/PP-09-forecasting-core.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-24.md](tasks/PP-24.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-25.md](tasks/PP-25.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-26.md](tasks/PP-26.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-27.md](tasks/PP-27.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-28.md](tasks/PP-28.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-29.md](tasks/PP-29.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-30-pr-review-fixes.md](tasks/PP-30-pr-review-fixes.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-30.md](tasks/PP-30.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-31.md](tasks/PP-31.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-33.md](tasks/PP-33.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-35.md](tasks/PP-35.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-37.md](tasks/PP-37.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-39.md](tasks/PP-39.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-45.md](tasks/PP-45.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-46-vp-inventory.md](tasks/PP-46-vp-inventory.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-46.md](tasks/PP-46.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-47.md](tasks/PP-47.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-48.md](tasks/PP-48.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-49.md](tasks/PP-49.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-50-vp-api-review.md](tasks/PP-50-vp-api-review.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-51.md](tasks/PP-51.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-52.md](tasks/PP-52.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-53.md](tasks/PP-53.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-54.md](tasks/PP-54.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-55.md](tasks/PP-55.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/tasks/PP-56.md](tasks/PP-56.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/pantrypulse/templates/COMMAND-CONTRACT.md](templates/COMMAND-CONTRACT.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/setup/CLOUDFLARE.md](../setup/CLOUDFLARE.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/setup/FLY.md](../setup/FLY.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/setup/GITHUB.md](../setup/GITHUB.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/setup/HUGGING-FACE.md](../setup/HUGGING-FACE.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/setup/LOCAL-COMPUTE.md](../setup/LOCAL-COMPUTE.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/setup/LOCAL-DEMO.md](../setup/LOCAL-DEMO.md) | Current implementation and procedure reconciliation |
| [docs/setup/LOCAL-LAUNCH-GUIDE.md](../setup/LOCAL-LAUNCH-GUIDE.md) | Current implementation and procedure reconciliation |
| [docs/setup/NEON.md](../setup/NEON.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/setup/README.md](../setup/README.md) | Current implementation and procedure reconciliation |
| [docs/setup/VERCEL.md](../setup/VERCEL.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/setup/WINDOWS-QUICKSTART.md](../setup/WINDOWS-QUICKSTART.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/setup/WORKER-QUEUE.md](../setup/WORKER-QUEUE.md) | Clarify historical evidence, decision, template or integration boundary |
| [docs/testing/README.md](../testing/README.md) | Current implementation and procedure reconciliation |
| [packages/contracts/README.md](../../packages/contracts/README.md) | Current implementation and procedure reconciliation |

| [docs/optimization/evidence/acceptance-initial-checkpoint.md](../optimization/evidence/acceptance-initial-checkpoint.md) | Correct three relative links; original evidence body/results retained |

## Final validation

- 165 first-party Markdown/MDX files reviewed; 118 documents updated.
- 968 local links and heading targets checked: zero unresolved paths/anchors.
- 72 PowerShell fenced examples parsed: zero syntax errors. These commands were parsed, not executed against services.
- Key claims checked against actual routes, eight-product schemas, production job registration, migration files and split CI configuration.
- Historical JSON/XML/model evidence and application source were not edited by this audit; other concurrent source changes remain intact.
- After the initial 647f6a8 snapshot, e7ee785 merged PR #100's finite-animation accessibility wait adjustment. That small test-only difference was inspected; it does not change the product/API/model/setup facts above. No new full-suite pass is claimed.
- No services were restarted, databases reset, model study rerun, commit created or changes pushed for this documentation update.
