# PantryPulse web application

The main baseline is a static Next.js development landing page. The dashboard, method comparison, presenter controls, API client and selected same-origin proxy remain to be implemented.

On `codex/vercel-prototype-preview`, the [Vercel branch preview](https://pantrypulse-prototype-preview-git-codex-e82088-gbw30s-projects.vercel.app/) redirects `/` to the illustrative `/design-lab`. It contains simulated data only and needs no API, database or environment variable. See the [deployment record](../../docs/setup/VERCEL.md). The local `/` landing page is still available in development; the redirect is configured in `vercel.json` for Vercel.

Read [Project specification V5](../../docs/pantrypulse/SPEC-V5.md) for current requirements, main/forecasting-branch status, UI architecture and acceptance. Follow the root [installation guide](../../INSTALLATION.md) for the pinned toolchain.

Run from the repository root:

```powershell
npm ci
npm run dev:web
```

The web server binds to `http://127.0.0.1:3000`. The root npm workspace and `package-lock.json` own dependency installation; do not create a second lockfile in this directory.

The accepted UI stack is Tailwind, shadcn/Radix, Recharts, Motion and Lucide, with selected Watermelon/Kokonut component sources. Python owns inventory, forecasting, optimization and research metrics. The future thin Next.js proxy forwards authenticated intent to FastAPI.

`npm run check`, `npm run build` and `npm run test:e2e` are available at the repository root. Current browser coverage is a scaffold smoke test, not evidence of the complete judge journey. Never put database or presenter credentials in browser-public configuration.
