# Vercel Next.js setup

> **Scope (October 24, 2026):** This guide records the live, simulated `/design-lab` preview. That historical deployment's root remains static. The preview does not contact the API, use Neon, require a tunnel, or need `NEXT_PUBLIC_API_BASE_URL`. Local backend/Chronos preparation is now resumed; the preview's scope remains unchanged. [Project specification V5](../pantrypulse/SPEC-V5.md) requires a thin same-origin Next.js proxy before any later connected frontend or product release.

## Connected prototype project

The `gbw30s-projects` Hobby team has a Git-connected project named [`pantrypulse-prototype-preview`](https://vercel.com/gbw30s-projects/pantrypulse-prototype-preview), linked to `gbw30/PantryPulse`. Its root directory is `apps/web`; source outside that directory is enabled for the root npm workspace lockfile. Node 24.x, the locked install command below and `npm run build` are configured. No API, database, model or presenter variables were added for this preview.

The [branch `/design-lab` URL](https://pantrypulse-prototype-preview-git-codex-e82088-gbw30s-projects.vercel.app/design-lab) is public and moves to the latest successful build from `codex/vercel-prototype-preview`. The [reviewed deployment](https://pantrypulse-prototype-preview-7r77os2kv-gbw30s-projects.vercel.app/design-lab) of commit `b04fee1e7c8fac5cbe8b7fc8171a58571126e9ff` is READY: `/` returns HTTP 200 with the scaffold landing page, and `/design-lab` returns HTTP 200 with simulated/illustrative disclosures. An earlier deployment of `81387fe8d7ca97774a61425c97d75a982b1ab1be` redirected `/`; that redirect was removed. Check the current commit and URL before treating a later build as verified.

Only `codex/vercel-prototype-preview` should build automatically. The project's ignored-build command is:

```sh
if [ "$VERCEL_GIT_COMMIT_REF" = "codex/vercel-prototype-preview" ]; then exit 1; else exit 0; fi
```

Merging PR #53 into `main` preserves this branch-specific build policy; it does not promote the preview or connect the backend. Keep the preview branch while this project uses it. Further pushes to that branch can update the public preview; changes on `main` alone do not refresh it. The worker foundation from PR #52 is separate infrastructure and does not make this preview call a worker or database.

A Git push to this branch triggered a Vercel Preview deployment. The `/design-lab` page was checked at 1440×900 and 390×844: simulated/illustrative labels remained visible, location selection and 3D→2D worked, and the browser reported no page errors or horizontal overflow. No ready Production deployment was created; an initial API request classified as Production was canceled before readiness. The project has no deployment protection enabled, so anyone with the URL can access the synthetic preview.

The original deployment session supplied the desktop/mobile interaction evidence above. PR #53 review independently rechecked the READY deployment's commit/alias, Node 24.x, disabled access protection, and public HTTP responses. It did not repeat the visual interaction smoke or verify environment-variable contents; the account checks below remain open.

## Manual account checks

The project, GitHub import, root directory and build settings are already configured. To use the preview, no additional Vercel setup is required. In the [Environment Variables settings](https://vercel.com/gbw30s-projects/pantrypulse-prototype-preview/settings/environment-variables), confirm no inherited API URL, database credential or other secret is present. The integration returned HTTP 403 when listing variables, so this one setting could not be independently verified. Do not add variables for the current simulated preview. Review the Hobby plan's permitted use and usage; decide whether public URL access is appropriate before sharing.

Vercel's [monorepo documentation](https://vercel.com/docs/monorepos) describes per-application roots. The root directory is a Vercel project setting; this branch needs no `vercel.json`.

## Build configuration for this repository

| Setting | Value |
|---|---|
| Root Directory | apps/web |
| Framework | Next.js |
| Node.js | 24.x |
| Install Command | cd ../.. && npx --yes npm@11.13.0 ci --no-audit --no-fund |
| Build Command | npm run build |
| Output Directory | Leave the Next.js preset default |
| Development Command | Leave preset default |

The install override assumes Vercel starts it in apps/web; it moves to the repository root to use the one workspace lockfile. Confirm that directory and root lockfile in build logs. Do not generate apps/web/package-lock.json.

The pinned npm invocation avoids relying on Vercel's bundled npm version. Keep devDependencies installed: TypeScript, Tailwind, build tools and the imported shadcn stylesheet require them during the build.

Vercel selects a supported Node major and manages its patch version; it does not guarantee our exact local 24.16.0 pin. The repository accepts >=24.16.0 <25. Check the actual version in build logs. See [supported Node versions](https://vercel.com/docs/functions/runtimes/node-js/node-js-versions).

## Future connected frontend

Do not set `NEXT_PUBLIC_API_BASE_URL` on this project. Earlier direct browser-to-FastAPI examples in [EXTERNAL-SERVICES.md](../../EXTERNAL-SERVICES.md) and other setup guides are historical reachability examples, not the selected V5 architecture. Main now implements the connected `/optimization` workspace, same-origin proxy and FastAPI presenter/CSRF controls. A separately authorized connected deployment must configure server-only `PANTRYPULSE_API_ORIGIN`, matching `PP_TRUSTED_PROXY_TOKEN`, actual backend allowed origins/secure cookies and an isolated API/schema mapping, then verify that target. Never put database or presenter secrets in `NEXT_PUBLIC_` variables. The existing ignored-build branch policy does not deploy these main changes.

## Deploy and verify

For each new commit, inspect its Vercel Preview build, record the commit and deployment URL, then check the root landing page and `/design-lab` in desktop and mobile browsers. Confirm the simulated disclosures, stylesheet, location selection and optional 3D/2D controls work without page errors. The branch URL may point to a newer build than the immutable deployment above. A successful static preview does not prove API, database, forecasting or allocation readiness.

For a later connected release, verify proxy/auth behavior, correct synthetic API/database isolation, error and pending states, full comparison, and rollback using [the deployment runbook](../pantrypulse/DEPLOYMENT.md). A tunnel health response alone establishes only API reachability.

## Common setup failures

- Missing lockfile/dependencies: check workspace access and install-command directory.
- npm engine mismatch: confirm the pinned install command and Node major.
- Missing shadcn stylesheet: install development dependencies during builds.
- Branch push produces a skipped build: check the ignored-build command and branch name.
- Branch URL differs from a recorded deployment: confirm the deployment commit before sharing.

## Completion checklist

- [x] Project linked to the intended repository and branch, with `apps/web` root.
- [x] Locked dependency installation and Next.js build succeeded on Vercel.
- [x] Preview URL and deployed commit recorded; desktop/mobile browser smoke passed.
- [x] Public preview distinguished from pending V5 integration and release acceptance.
- [ ] Owner checks Environment Variables in the dashboard; integration access returned 403.
- [ ] Owner reviews Hobby use/usage and public-access preference.

No global Vercel CLI or `VERCEL_TOKEN` is required for this Git integration workflow.
