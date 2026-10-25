# PantryPulse

PantryPulse is a project for Gator Hack V, October 23–25, 2026, exploring how food banks and community organizations can share limited supplies more fairly.

Start with the [consolidated project specification V5](docs/pantrypulse/SPEC-V5.md) for accepted requirements, the current main and forecasting-branch state, unresolved decisions and release acceptance.

When several organizations need food at the same time, there may not be enough to meet every request. Sending the same amount to everyone can overlook differences in need. Sending supplies wherever delivery is easiest can leave vulnerable communities with larger shortages. Meanwhile, food can expire, storage space is limited, and organizations donating supplies still need enough for the people they already serve.

PantryPulse aims to help a coordinator understand these trade-offs and compare possible allocation plans before making a decision.

## How it is intended to work

The demonstration will use simulated inventory, requests and institution-level vulnerability indicators for six beneficiary organizations and one or two distribution hubs. It will:

1. Estimate upcoming demand, with a simple seasonal forecast available when the more advanced forecasting model is unavailable.
2. Calculate two allocation plans from exactly the same supplies, requests and operating limits.
3. Show who receives supplies, which needs remain unmet, and how the plans differ in their treatment of shortages and vulnerability.
4. Let the coordinator explore a changed scenario and see how the recommendations respond.

Both plans must respect the same practical rules: supplies cannot be created or counted twice, organizations cannot receive more than they can handle, donors must retain protected supplies, and eligible food that expires sooner must be used first.

## What makes the comparison different

The first method, **classical goal programming**, balances a set of allocation goals. The second, **EGP-PI-inspired allocation**, is intended to make vulnerability and deprivation central to that balance. Deprivation means both how far an organization falls short of its needs and how its shortage compares with those of its peers.

The research basis is Rampazo et al., *An extended goal programming framework incorporating poverty measures: application to food bank logistics*, first published online September 11, 2026 ([research paper](https://doi.org/10.1111/itor.70252)). PantryPulse proposes a bounded adaptation using simulated vulnerability indicators. It does not claim to reproduce the complete published formulation.

The goal of the reproducible demonstration is to show when these research-derived priorities change actual allocation decisions, and to make the resulting trade-offs visible. A different recommendation is evidence of different priorities; it does not by itself establish better real-world outcomes.

## Current state

**PantryPulse is in early development.** The repository contains the frontend foundation, a backend process-health endpoint, locked dependencies, and a Linux container environment for the optimization libraries. Backend primitives cover transfer modes, route eligibility, demand rounding, fixed-point arithmetic, solver outcomes and forecast-history alignment. The complete allocation engines, application database schema and interactive comparison workflow are not yet implemented. Equation-level research validation remains a prerequisite for complex solver work.

This review-fix branch includes the [offline forecasting core](docs/pantrypulse/forecasting/IMPLEMENTATION.md) from PR #49 alongside the existing backend primitives. It provides preparation, baselines, evaluation and pure projection; actual Chronos inference, database publication, durable jobs and browser integration remain unfinished. Run the synthetic evaluation with `uv run --frozen --directory apps/api python -m scripts.evaluate_forecasting`. The [forecasting roadmap](docs/forecasting/README.md) preserves the remaining integration gates.

The demo is planned around simulated data and institution-level indicators. It will not purchase supplies or dispatch real deliveries.

## Project foundation

The planned system uses a Next.js/React interface, a Python/FastAPI backend, OR-Tools for allocation calculations, and PostgreSQL for shared data. Charts will explain the results, while brief animations and clear loading states will help users follow calculations in progress. Chronos-2 is the preferred optional forecasting model, with a seasonal-naive fallback.

For a future integrated presentation, the website and Python API can run on the presenter's computer, with Neon holding the demo database. A completely local database is available for an offline setup. A separate simulated Vercel preview is live; connecting a hosted frontend to the laptop API would require the V5 proxy/auth work and a temporary tunnel. Fly.io remains an optional hosted backend alternative. GitHub holds the source code.

## Further reading

- [Project specification V5 — current source of truth](docs/pantrypulse/SPEC-V5.md)
- [Original V4 source document](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.951hp1xdarlq)
- [Local development installation guide](INSTALLATION.md)
- [External services installation guide](EXTERNAL-SERVICES.md)
- [Personal-computer demo setup](docs/setup/LOCAL-DEMO.md)
- [Run Chronos locally](CHRONOS-LOCAL.md)
- [Prioritized implementation plan](docs/pantrypulse/IMPLEMENTATION-PLAN.md)
- [Architecture and research validation](docs/architecture/0001-v4-research-first.md)

V5 consolidates V4, later accepted decisions and actual implementation evidence. Older documents remain historical or detailed references where compatible.

The optional `/design-lab` route is an illustrative dashboard experiment, with a default 2D network and a [bounded optional 3D exception](docs/architecture/0004-design-lab-3d-exception.md). It does not connect to allocation APIs or represent committed transfers.

A [frontend-only Vercel preview of `/design-lab`](https://pantrypulse-prototype-preview-git-codex-e82088-gbw30s-projects.vercel.app/design-lab) is available from `codex/vercel-prototype-preview`. The root page remains the scaffold; no API, Neon database, tunnel or presenter workflow is connected. The [Vercel setup record](docs/setup/VERCEL.md) describes its branch-scoped deployment and remaining account checks. This preview is not the V5 release candidate.
