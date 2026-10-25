# PantryPulse

PantryPulse is a project for Gator Hack V, October 23–25, 2026, exploring how food banks and community organizations can share limited supplies more fairly.

Start with [current source/runtime status](docs/pantrypulse/CURRENT-STATUS.md) and the [consolidated specification V5](docs/pantrypulse/SPEC-V5.md) for implemented scope, accepted requirements, remaining decisions and release acceptance.

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

Main includes the connected simulated application: presenter access, persisted baseline forecasts, frozen scenarios, sequential classical/research-inspired comparisons, independent result verification and the `/optimization` workspace through a same-origin proxy. PR #75 integrated operational storage and baseline forecasting; PR #76 connected the bounded allocation workflow and active Linux/PostgreSQL/browser CI. These are simulated decisions, not operational dispatch or evidence of real-world policy effectiveness.

The [connected integration guide](docs/optimization/CONNECTED-INTEGRATION.md) records the supported domain and explicit demo loader. The current migration head is `ppor_0005`; all predecessor revisions are preserved. [Stock services](docs/pantrypulse/STOCK-SERVICES.md), [inventory projection](docs/pantrypulse/INVENTORY-PROJECTION.md) and [migration instructions](apps/api/migrations/README.md) describe the persistence boundary. Deployment and any update of existing running images remain controlled operations.

The production [worker](docs/setup/WORKER-QUEUE.md) supports `forecast.v1` and `or-comparison.v2`, with one active operation and two waiting jobs. PR #77 supplies [bounded local compute](docs/setup/LOCAL-COMPUTE.md), persistent model storage and prepared [Fly configuration](docs/setup/FLY.md). Full pinned Chronos-2 has passed real standalone CPU inference and synthetic timing checks; the application provider remains baseline-only. Representative forecast accuracy, integrated Chronos, supplier planning, visitor access, general imports and real operational actions remain separate work.

The demo is planned around simulated data and institution-level indicators. It will not purchase supplies or dispatch real deliveries.

## Project foundation

The planned system uses a Next.js/React interface, a Python/FastAPI backend, OR-Tools for allocation calculations, and PostgreSQL for shared data. Charts will explain the results, while brief animations and clear loading states will help users follow calculations in progress. Chronos-2 is the preferred optional forecasting model, with a seasonal-naive fallback.

The website, API and worker can run on the laptop using an isolated local or Neon schema. A separate synthetic Vercel preview remains branch-scoped; a separately selected hosted connected frontend must configure and verify the implemented proxy/auth path against its actual API. Fly remains a prepared alternative; login, platform validation and deployment are pending. See [external services](EXTERNAL-SERVICES.md).

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

A [frontend-only Vercel preview of `/design-lab`](https://pantrypulse-prototype-preview-git-codex-e82088-gbw30s-projects.vercel.app/design-lab) is available from `codex/vercel-prototype-preview`. That older deployment has no API/database/presenter connection; main now redirects its root to `/optimization`. The [Vercel record](docs/setup/VERCEL.md) explains the branch-specific build policy. Merging main does not refresh that preview or establish a hosted release.
