# PantryPulse developer installation

For a shorter walkthrough with separate host and teammate instructions, follow the [Windows installation and Cloudflare connection quickstart](docs/setup/WINDOWS-QUICKSTART.md).

This guide targets Windows x64 with PowerShell 5.1 or 7. [Project specification V5](docs/pantrypulse/SPEC-V5.md) is authoritative for accepted requirements, current main/forecasting-branch status and unresolved work. The [V4 tab](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.951hp1xdarlq) and saved snapshot are historical sources. Setup commands do not override V5's proxy/job architecture or resume paused model/hosting work.

**Current state:** frontend/API scaffold plus backend primitives for transfer modes, route eligibility, demand rounding, fixed-point arithmetic, solver outcomes and forecast-history alignment. The complete EGP-PI-inspired and classical allocation engines, forecasting adapters, domain migrations and complete demo are pending. Installed libraries do not imply those features work.

## 1. Install these prerequisites manually

The setup script deliberately does not install system tools, enable virtualization, change security policy, or create cloud accounts.

| Prerequisite | Version / choice | Manual action |
|---|---|---|
| Git for Windows | Current maintained Git 2.x; tested 2.56.0.windows.2 | Install from [Git's Windows page](https://git-scm.com/install/windows), with Git available on PATH. |
| Node.js | **24.16.0** | Use the Windows x64 MSI from the [official release archive](https://nodejs.org/download/release/v24.16.0/), or your existing Node manager. Add Node/npm to PATH. |
| npm | **11.13.0** | Comes with Node; verify the version. If needed, run `npm install --global npm@11.13.0` in your normal toolchain environment. |
| uv | **0.11.15** | Install with the versioned Astral command below or the binary from the [0.11.15 release](https://github.com/astral-sh/uv/releases/tag/0.11.15). |
| Docker Desktop + Compose plugin | Linux containers; tested engine 29.9.2 and Compose 5.6.1 | Install using [Docker's Windows guide](https://docs.docker.com/desktop/setup/install/windows-install/). Start Desktop and finish its first-run setup before running project setup. |
| WSL 2 / virtualization | Docker's supported Windows backend | Enable hardware virtualization and install/update WSL if Docker requires it. This can require administrator rights and a restart. |
| Editor and browser | Your choice | VS Code is convenient; no mandatory extension. Playwright installs its own Chromium separately. |

Versioned uv installer, per [Astral's instructions](https://docs.astral.sh/uv/getting-started/installation/):

```powershell
irm https://astral.sh/uv/0.11.15/install.ps1 | iex
```

Reopen PowerShell after changing PATH. Verify:

```powershell
git --version
node --version
npm --version
uv --version
docker --version
docker compose version
docker info --format '{{.OSType}}'
```

Expected pinned output: Node v24.16.0, npm 11.13.0, uv 0.11.15. Docker OSType must be linux.

For a WSL-based Docker installation, an administrator may need `wsl --install` or `wsl --update`, followed by a restart. Follow Docker's requirements for your Windows edition; the project script does not perform these system changes.

**Do not separately install Python, pip packages, PostgreSQL, OR-Tools, Java, CUDA, Rust or Visual Studio Build Tools for the standard setup.** uv downloads Python 3.12.13, Python dependencies use prebuilt wheels, and Docker provides PostgreSQL 16. A GPU is unnecessary for the core CP-SAT environment. Hardware-specific Chronos setup is optional and separate.

No Neon, Vercel, Fly.io, Gemini or other API account/key is needed for local setup.

For the presentation, use the separate [external services and laptop demo guide](EXTERNAL-SERVICES.md): your laptop runs the backend, and Neon hosts the database. Vercel plus a tunnel is optional for access from other devices; Fly.io is not required. [Hugging Face / Chronos-2](docs/setup/HUGGING-FACE.md) remains optional. The guide identifies application integration still to be implemented.

For the optional model itself, follow [CHRONOS-LOCAL.md](CHRONOS-LOCAL.md). It provides a separate Linux image, a persistent checkpoint cache, real synthetic-data inference commands, performance checks and shutdown steps; it does not implement the application's forecasting API.

## 2. Open the correct checkout

```powershell
git clone https://github.com/gbw30/PantryPulse.git
Set-Location PantryPulse
git rev-parse --show-toplevel
```

If the repository is already cloned, open that checkout instead. The root contains `package.json`, `compose.yaml`, `apps/` and `scripts/`. A pre-existing nested `PantryPulse/` copy on the original host is preserved historical work; do not install or run the project from it.

`.node-version` documents the Node pin but does not switch your installed Node automatically. Root `package-lock.json` owns the npm workspace; `apps/api/uv.lock` owns Python. Keep both lockfiles in Git.

## 3. Run automated setup

Recommended on Windows, including Chromium and the Docker backend:

```powershell
.\scripts\setup-windows.ps1 -WithContainerApi -WithBrowser
.\scripts\doctor-windows.ps1 -RequireContainerApi
```

The setup script:
1. Checks pinned Node/npm/uv versions and, for Docker options, engine/Compose availability.
2. Runs root `npm ci` using the committed lockfile.
3. Creates `apps/api/.venv` with uv-managed Python 3.12.13 and frozen Python dependencies.
4. Leaves the optional `forecast` extra uninstalled.
5. Installs Chromium when `-WithBrowser` is selected.
6. Builds/starts the API and PostgreSQL when `-WithContainerApi` is selected.
7. For that container option, runs a trivial CP-SAT solve and read-only PostgreSQL connection check.

Other modes:

```powershell
# Dependencies only; no containers or Chromium:
.\scripts\setup-windows.ps1
# Dependencies + PostgreSQL, for a compatible native Python host:
.\scripts\setup-windows.ps1 -WithDatabase -WithBrowser
```

The Docker option also creates a native Python environment for lint and health tests. It does not install optional ML libraries into either runtime.

If local script policy blocks the .ps1 file, use your organization's approved process or run these individual commands in PowerShell:

```powershell
npm ci --no-audit --no-fund
uv sync --frozen --project apps/api --python 3.12.13 --no-extra forecast
npm run test:e2e:install
npm run dev:api:docker
npm run check:runtime:docker
```

## 4. Configuration and local environment files

The current health endpoint and static web shell require no .env files. Templates are provided for the future domain services:

```powershell
# Run only if these destinations do not already exist.
Copy-Item apps/api/.env.example apps/api/.env
Copy-Item apps/web/.env.example apps/web/.env.local
```

Do not overwrite an existing developer configuration. Private env files are Git-ignored; only examples are tracked. The API settings loader, CORS configuration and forecast settings consumption are still pending. These examples document intended configuration rather than implemented behavior.

| Setting | Local value / meaning |
|---|---|
| NEXT_PUBLIC_API_BASE_URL | http://127.0.0.1:8000/api/v1 |
| DATABASE_URL (native host) | postgresql+psycopg://pantrypulse:local_dev_only@127.0.0.1:55432/pantrypulse_dev |
| DATABASE_URL (container) | Provided by Compose, using postgres:5432 |
| CORS_ALLOWED_ORIGINS | ["http://127.0.0.1:3000"] |
| FORECAST_PROVIDER | seasonal-naive; adapter not implemented yet |
| FORECAST_MODEL_ID / FORECAST_DEVICE | amazon/chronos-2 / cpu; optional future adapter |
| SOLVER_TIME_LIMIT_SECONDS | 5; domain solver not implemented yet |
| DEMO_FIXED_DATE | 2026-10-24 |
| APP_ENV / DEMO_MODE | development / true |

The credentials above are dedicated local development values from Compose. Never reuse them for hosting. NEXT_PUBLIC_ settings are browser-visible; never put database or API secrets there.

## 5. Start, verify and stop

If setup used `-WithContainerApi`, the backend and database are already running. In a web terminal:

```powershell
npm run dev:web
```

Otherwise start the Docker backend first with `npm run dev:api:docker`. It runs detached and builds from copied sources. After Python changes, run that command again to rebuild; the container does not provide hot reload.

| Service | Address |
|---|---|
| Next.js web | http://127.0.0.1:3000 |
| API process liveness | http://127.0.0.1:8000/api/v1/health |
| OpenAPI UI | http://127.0.0.1:8000/docs |
| PostgreSQL host port | 127.0.0.1:55432 |

```powershell
npm run check
npm run build
npm run test:config
npm run test:e2e
npm run test:api:docker
npm run check:runtime:docker
.\scripts\doctor-windows.ps1 -RequireContainerApi
```

Expected health JSON: `{"status":"ok","scope":"process"}`. Current tests cover the scaffold, not an allocation/forecast demonstration. Full domain quality gates remain pending; do not interpret their absent tests as successful product validation.

Native alternative on hosts with working allowed Python DLLs: run `npm run dev:api` in a separate terminal. Do not run it alongside the container API on port 8000. On the original Windows host, Application Control rejected a pandas DLL imported by OR-Tools; native health works but does not prove solver availability. Use the verified Docker route without changing security policy.

Stop the web/native API with Ctrl+C in its terminal. Stop project containers without deleting data:

```powershell
docker compose stop api postgres
```

The named PostgreSQL volume survives. Startup SQL creates pantrypulse_dev and pantrypulse_test plus existing lane databases only when the volume is first initialized. Do not delete a volume as a routine setup fix. There are no Alembic domain revisions yet; migration validation will be added after the research contract gate.

## 6. Installed dependency groups

| Group | Packages / tooling |
|---|---|
| Web runtime | Next.js, React/React DOM, Recharts, Motion, Lucide, Radix Slot, class-variance-authority, clsx, tailwind-merge, tw-animate-css |
| Web development | TypeScript/types, Tailwind/PostCSS, ESLint/Next config, Playwright, openapi-typescript, pinned shadcn CLI |
| API runtime | FastAPI, Uvicorn, Pydantic/settings, SQLAlchemy, Alembic, psycopg binary, OR-Tools, python-multipart |
| API development | pytest, HTTPX, Ruff |
| Local services | PostgreSQL 16; optional API development container |
| Browser testing | Playwright Chromium with `-WithBrowser` or `npm run test:e2e:install` |

The OpenAPI generator is installed; generated domain schemas/types will follow validated Pydantic contracts.

### Finalized frontend UI stack

| Library / source | Use | Setup status |
|---|---|---|
| Tailwind CSS 4 | Layout, responsive styling, shared design tokens and CSS depth effects | Installed with its PostCSS integration |
| shadcn/ui + Radix primitives | Buttons, forms, dialogs, tables, tabs, drawers and accessible interactions | shadcn CLI 4.22.1 installed locally; existing Radix Slot/helpers retained; component source and additional primitives installed when selected |
| Recharts 3.10.1 | Backend-driven forecasts, allocation comparisons and deprivation charts | Installed; one charting system for the MVP |
| Motion 14.6.0 | State transitions, loading feedback and animated network/changed-allocation explanations | Installed as `motion`; import React APIs from `motion/react` |
| Lucide React | Consistent icons | Installed |
| Watermelon UI | Selected dashboard/layout components | Registry configured as `@watermelon`; add component source on demand |
| Kokonut UI | Selected expressive cards and animated interactions | Registry configured as `@kokonutui`; add component source on demand |

`tw-animate-css` 1.4.0 provides CSS animation utilities for shadcn components and is imported in globals.css along with shadcn's Tailwind utilities. It is not a second JavaScript animation engine. Semantic color/chart/radius tokens are mapped to Tailwind using the existing PantryPulse palette.

shadcn/ui, Watermelon and Kokonut distribute component source. There is no need to install a package named shadcn-ui, watermelon-ui or kokonut-ui. The pinned local CLI reads apps/web/components.json, writes selected component files into the workspace, and adds their actual dependencies. Do not clone entire component catalogues or install all Radix primitives preemptively.

Use these commands from the repository root:

```powershell
# Inspect framework, primitive base, aliases and registry configuration:
npm run ui:info
# Example: intentionally add one standard shadcn component:
npm run ui:add -- button
```

For registry components, pass the exact identifier from the official [Watermelon installation guide](https://ui.watermelon.sh/installation) or [Kokonut component documentation](https://kokonutui.com/docs) to the same ui:add command. Configured URLs are `https://registry.watermelon.sh/r/{name}.json` and `https://kokonutui.com/r/{name}.json`. No external registry components have been copied yet. Review generated source, dependencies and license notices, then commit source, manifests and the root lockfile together. Do not rerun shadcn init over the existing configuration.

New developers only need npm ci or the setup script: there is no global CLI or manual UI-library installation. Node installs the locked packages; Tailwind imports the CSS utilities. Include development dependencies when building because the stylesheet imports shadcn/tailwind.css from the local shadcn package.

Interactive Motion/chart components should use narrow Next.js client boundaries. Use MotionConfig reducedMotion="user" for Motion-powered UI and honor reduced-motion preferences in CSS as components are introduced. Keep controls responsive, show honest pending states, preserve prior results, and animate changed allocation values only after backend responses. No Motion provider or product animation has been wired into the static scaffold yet.

Three.js, React Three Fiber, React Spring and Bklit are outside the finalized MVP stack. CSS perspective/transforms and Motion can provide the planned dimensional 2D network. Godly and Variant are design references, not runtime dependencies. See [ADR 0002](docs/architecture/0002-ui-stack.md) for the decision.

## 7. Optional dependencies considered but not installed

The following are omitted from the canonical environment on purpose. Some are named in V4 as optional/P1 supporting tools; others are candidate tooling for those features.

| Dependency | Purpose | Reason deferred |
|---|---|---|
| chronos-forecasting and its torch, transformers, accelerate, huggingface-hub, safetensors dependencies | Chronos-2 inference | Large install and checkpoint/hardware validation; research solver and baseline come first |
| maplibre-gl | Map display | Geographic UI is optional |
| @xyflow/react | Process/transfer-flow diagrams | Optional visualization |
| mapie / scikit-learn | Calibrated intervals and classical model tooling | Requires held-out evaluation and a defined calibration method |
| google-genai | Gemini natural-language scenario input/explanations | Optional; no authority to alter inventory or approve actions |
| vitest / @testing-library/react | Frontend unit/component tests | pytest and Playwright cover the current scaffold; add when components justify them |
| Fly/Vercel/Neon CLI tools | Hosted deployment | Local environment needs no cloud CLI or account; the separate Fly deployment guide requires flyctl |

Only the forecast extra is currently declared as an optional install group and resolved in uv.lock. A lock entry is not an installation. Other candidates must be explicitly added and locked if adopted. Pandas and NumPy are already installed through OR-Tools and are not omitted dependencies.

To install the declared forecast extra into the **native** environment later:

```powershell
uv sync --frozen --project apps/api --python 3.12.13 --extra forecast
```

This does not install the extra in the Docker image, download the amazon/chronos-2 checkpoint, or implement the adapter. The default API Dockerfile excludes forecast dependencies. Docker inference needs a separate intentional Dockerfile/lock-compatible setup and hardware validation. Re-running default setup returns the native environment to core dependencies.

## 8. Troubleshooting and updates

- **Command not found:** reopen the shell after installation; check PATH and the selected Node version.
- **Version mismatch:** install/switch to the pinned versions rather than regenerating locks to accommodate a different toolchain.
- **Docker pipe missing:** start Docker Desktop and wait for Linux engine readiness; run `docker info`.
- **Port occupied:** 3000, 8000 and 55432 must be available. Existing services on 5432/5433/15432 are why this project uses 55432.
- **Native DLL blocked:** use the container API; do not disable Application Control.
- **Package download or cache permissions:** use an approved writable environment and authorized network access; do not copy the historical nested node_modules as setup.
- **Existing volume missing test DB:** inspect the volume and initialization history before changing databases.
- **Expected compiler/model tools missing:** the core setup uses binary wheels. CUDA/build tools are not a standard prerequisite.
- **Deprecation messages:** current ESLint 9 and HTTPX-backed TestClient produce notices; they were recorded in verification. Do not suppress them or silently update locks.

For intentional dependency changes, use npm install in the root workspace or uv lock --project apps/api, review the manifest/lock changes, then rerun frozen setup and relevant checks. Do not maintain a parallel requirements.txt or another package-lock.json inside apps/web.

See [architecture/research gate](docs/architecture/0001-v4-research-first.md), [implementation plan](docs/pantrypulse/IMPLEMENTATION-PLAN.md) and [verification evidence](docs/pantrypulse/SCAFFOLD-VERIFICATION.md). EGP-PI-inspired remains our own bounded mathematical implementation, not a separately installable library.

