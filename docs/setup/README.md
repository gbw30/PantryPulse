# Setup and operations documentation

Updated October 25, 2026 for main `647f6a8`. [Current status](../pantrypulse/CURRENT-STATUS.md) separates implemented source, installed runtime and release evidence. All four product views and opt-in Chronos jobs are integrated; a source merge does not update a container or deploy a website.

| Need | Guide |
| --- | --- |
| Reopen the existing laptop video demo; Docker/ports/PowerShell fixes | [Local launch and troubleshooting](LOCAL-LAUNCH-GUIDE.md) |
| Install pinned dependencies | [Installation](../../INSTALLATION.md), [Windows quickstart](WINDOWS-QUICKSTART.md) |
| Start the tracked pp-local launcher or choose an isolated runtime | [Local demo](LOCAL-DEMO.md) |
| Bounded compute images/model cache | [Local compute](LOCAL-COMPUTE.md), [standalone Chronos tools](../../CHRONOS-LOCAL.md) |
| Opt-in application Chronos jobs and qualification limits | [Chronos jobs](../forecasting/CHRONOS-JOBS.md), [dossier](../forecasting/QUALIFICATION.md) |
| Jobs, cancellation and recovery | [Worker queue](WORKER-QUEUE.md) |
| Hosted database or optional hosting/tunnel | [External-service map](../../EXTERNAL-SERVICES.md), [Neon](NEON.md), [Cloudflare](CLOUDFLARE.md), [Fly](FLY.md), [Vercel](VERCEL.md) |
| Accounts/source/model preparation | [GitHub](GITHUB.md), [Hugging Face](HUGGING-FACE.md) |
| Migration, API and test acceptance | [Migrations](../../apps/api/migrations/README.md), [API runbook](../pantrypulse/ALL-API-RUNBOOK.md), [testing](../testing/README.md) |

The tracked `scripts/demo-local.ps1` uses explicit ports and recreates its own API/worker. The earlier ignored `artifacts/demo-recipe/setup_demo.py` automatically chooses free ports for a separate new demo; it is machine-local and absent from fresh clones. Its `presenter_demo_*` database and credentials differ from `pp-local-*`.

Visitor reads require `PP_VISITOR_ORGANIZATION_ID`; presenter authentication remains mandatory for compute, jobs, planning and mutations. Optional model jobs require the selected checkpoint/profile and a real compatible worker; raw model intervals are uncalibrated.

Keep private `.env` files, presenter access, model tokens and URLs with credentials out of Git. Do not reset volumes, migrate a different schema, kill all containers or change global security policy as routine setup. Hosting, supplier proposals and release qualification remain separate from local operation.
