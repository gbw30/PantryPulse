# PantryPulse

Gator Hack V · October 23–25, 2026. Planned resource-allocation platform comparing classical GP with EGP-PI-inspired optimization.

**Status: development scaffold with a tested offline forecasting core. Allocation engines, domain persistence, durable jobs, public forecasting endpoints and the integrated six-beneficiary demo remain unimplemented.**

The [V4 tab](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.951hp1xdarlq) is authoritative. Older three-site contracts are historical where they conflict with V4.

Research: Rampazo et al., *An extended goal programming framework incorporating poverty measures: application to food bank logistics*, [DOI 10.1111/itor.70252](https://doi.org/10.1111/itor.70252), first published online **September 11, 2026**. The intended adaptation uses absolute/relative deprivation goals, institution vulnerability attributes and a weighted/Chebyshev objective. Fixed simulated proxy weights and a limited horizon do not reproduce the complete research formulation or establish real-world equity gains.

## Development

New developers: start with [INSTALLATION.md](INSTALLATION.md) for manual prerequisites, pinned versions, automated setup, and optional dependencies.

Finalized UI stack: Tailwind CSS, shadcn/ui with Radix, Recharts, Motion and Lucide; selected Watermelon/Kokonut components through configured registries. See [ADR 0002](docs/architecture/0002-ui-stack.md). The pinned component CLI is available through `npm run ui:info` and `npm run ui:add -- button`.

Prerequisites: Node 24.16.0, npm 11.13.0, uv 0.11.15; Docker Desktop for PostgreSQL. Use the outer repository root.

```powershell
.\scripts\setup-windows.ps1
npm run check
npm run build
# Recommended API runtime on this Windows host:
npm run dev:api:docker
# Web terminal:
npm run dev:web
```

Web: http://127.0.0.1:3000 · API process health: http://127.0.0.1:8000/api/v1/health.

Windows Application Control blocked a native pandas DLL required by OR-Tools. The Docker API profile provides the backend development runtime without changing that policy. Native `npm run dev:api` remains available for compatible hosts; its current health endpoint does not import OR-Tools.

See [Windows development](docs/pantrypulse/WINDOWS-DEVELOPMENT.md), [prioritized implementation plan](docs/pantrypulse/IMPLEMENTATION-PLAN.md), [architecture and research gate](docs/architecture/0001-v4-research-first.md), and [verification record](docs/pantrypulse/SCAFFOLD-VERIFICATION.md).

## Layout

- apps/web: Next.js, React, TypeScript, Tailwind, shadcn configuration and Playwright scaffold smoke test.
- apps/api: FastAPI health; pure forecasting preparation/baselines/evaluation and lot projection; uv dependencies for OR-Tools, SQLAlchemy/Alembic/PostgreSQL, pytest, optional Chronos.
- packages/contracts: generated API type boundary after schema validation.
- data/demo: historical fixture retained; V4 research fixture follows mathematical validation.
- docs/architecture: decisions and research contract.
- PantryPulse/: preserved pre-existing untracked nested copy; not part of the canonical workspace.

All planned demonstration data and vulnerability indicators are simulated. P0 will not purchase or dispatch real resources.

The [forecasting core implementation and evidence](docs/pantrypulse/forecasting/IMPLEMENTATION.md)
includes a deterministic six-beneficiary/one-hub/two-product fixture. Run its offline
evaluation with `uv run --frozen --directory apps/api python -m scripts.evaluate_forecasting`.
Actual Chronos inference remains unqualified; the adapter reports unavailability and
uses a labeled baseline only when fallback is explicitly allowed.
