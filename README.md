# PantryPulse

PantryPulse is a project for Gator Hack V, October 23–25, 2026, exploring how food banks and community organizations can share limited supplies more fairly.

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

**PantryPulse is in early development.** The repository contains the frontend foundation, a backend process-health endpoint, locked dependencies, and a Linux container environment for the optimization libraries. Backend primitives cover transfer modes, route eligibility, demand rounding, fixed-point arithmetic, solver outcomes and forecast-history alignment. The complete allocation engines, forecasting adapters, application database schema and interactive comparison workflow are not yet implemented. Equation-level research validation remains a prerequisite for complex solver work.

The demo is planned around simulated data and institution-level indicators. It will not purchase supplies or dispatch real deliveries.

## Project foundation

The planned system uses a Next.js/React interface, a Python/FastAPI backend, OR-Tools for allocation calculations, and PostgreSQL for shared data. Charts will explain the results, while brief animations and clear loading states will help users follow calculations in progress. Chronos-2 is the preferred optional forecasting model, with a seasonal-naive fallback.

For the presentation, the website and Python API can run on the presenter's computer, with Neon holding the demo database. A completely local database is also available for an offline setup. Vercel with a temporary tunnel supports access from other devices; Fly.io remains an optional hosted backend alternative. GitHub holds the source code.

## Further reading

- [Authoritative V4 specification](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.951hp1xdarlq)
- [Local development installation guide](INSTALLATION.md)
- [External services installation guide](EXTERNAL-SERVICES.md)
- [Personal-computer demo setup](docs/setup/LOCAL-DEMO.md)
- [Run Chronos locally](CHRONOS-LOCAL.md)
- [Prioritized implementation plan](docs/pantrypulse/IMPLEMENTATION-PLAN.md)
- [Architecture and research validation](docs/architecture/0001-v4-research-first.md)

V4 is the project's authoritative specification. Earlier versions are historical references.
