# Vercel Next.js setup

> **Frontend prototype preview (October 24, 2026):** The user resumed Vercel setup only for the simulated `/design-lab` preview. The preview branch redirects `/` to `/design-lab` and does not contact the API, require Neon, or need a tunnel or `NEXT_PUBLIC_API_BASE_URL`. Configure the Vercel project with `apps/web` as root, access to source files outside that root, Node 24.x, and the root lockfile install below. Verify the live URL and its preview access policy before sharing. V5's same-origin Next.js proxy is still required for any later connected frontend; the direct browser-to-API instructions further down this guide are historical and must not be used to claim completed integration. Backend/model hosting remains paused.
Purpose: optionally host the PantryPulse frontend for access from other devices. The backend runs on the laptop through an HTTPS tunnel as described in [EXTERNAL-SERVICES.md](../../EXTERNAL-SERVICES.md). Complete [GitHub](GITHUB.md), [Neon](NEON.md) and [local demo setup](LOCAL-DEMO.md) first. A presentation entirely in the laptop's browser does not require Vercel; [Fly.io](FLY.md) is only a hosted backend alternative.

## Connected prototype project

The `gbw30s-projects` Hobby team now has a Git-connected project named `pantrypulse-prototype-preview`, linked to `gbw30/PantryPulse`. Its root directory is `apps/web`; source outside that directory is enabled for the root npm workspace lockfile. Node 24.x, the locked install command below and `npm run build` are configured. There are no API, database, model or presenter secrets in this preview.

Only `codex/vercel-prototype-preview` should build automatically. The project's ignored-build command is:

```sh
if [ "$VERCEL_GIT_COMMIT_REF" = "codex/vercel-prototype-preview" ]; then exit 1; else exit 0; fi
```

A Vercel API deployment can explicitly use the nonproduction `staging` target if Git does not trigger a preview. The first deployment from this branch built successfully and the live page was checked at 1440×900 and 390×844: `/` leads to `/design-lab`, simulated/illustrative labels remain visible, location selection and 3D→2D work, and the browser reported no page errors or horizontal overflow. The exact deployment URL and commit are reported at handoff; future updates must be checked against their own deployment URL. The connected project has no deployment protection enabled, so the preview is publicly accessible to anyone with its URL. Keep all content synthetic.
## Manual account and import

1. Sign in at https://vercel.com, select the intended account/team, and review the plan and usage limits.
2. Choose Add New → Project and connect GitHub if needed.
3. Import the existing gbw30/PantryPulse repository, selecting the reviewed branch.
4. Set Root Directory to apps/web and Framework Preset to Next.js.
5. Ensure the build can access files outside the app root, including the repository-root npm workspace manifest and package-lock.json.
6. Choose the production branch deliberately. Use a non-production branch for preview validation where appropriate.

Vercel's [monorepo documentation](https://vercel.com/docs/monorepos) describes per-application roots. There is no rootDirectory key to add to vercel.json.

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

## Frontend configuration

Set this project variable using the actual laptop tunnel HTTPS URL (or the Fly URL only if choosing that alternative):

```text
NEXT_PUBLIC_API_BASE_URL=https://YOUR-API-HOST/api/v1
```

Configure Preview and Production intentionally. NEXT_PUBLIC_ values are public; never add DATABASE_URL, presenter tokens or Hugging Face credentials here. Updating a browser-embedded value needs a new build/deployment; see [environment variables](https://vercel.com/docs/environment-variables).

The current static page does not yet read this value or call the API. It is the future frontend-client configuration contract, not proof that integration exists.

## Deploy and verify

Deploy the reviewed source and record the actual returned URL/commit. The scaffold page should load, its stylesheet should resolve, and no hydration/import error should appear.

Once the real frontend API client/settings/CORS exist:

1. Add the exact Vercel origin to the laptop API's allowlist once settings/CORS are implemented, then recreate/restart the container with its updated configuration.
2. Redeploy the API as needed and rebuild the web app after URL changes.
3. Open browser Network tools and verify requests reach the intended /api/v1 endpoints over HTTPS.
4. Test error, pending, stale and successful comparison states.
5. Confirm the preview maps to the correct synthetic-data API/database rather than assuming automatic isolation.

A preview URL may change. Maintain exact allowed origins or introduce a tested same-origin proxy; do not broadly allow every origin as a workaround.

## Common setup failures

- Missing lockfile/dependencies: check workspace access and install-command directory.
- npm engine mismatch: confirm the pinned install command and Node major.
- Missing shadcn stylesheet: install development dependencies during builds.
- API health works in a terminal but browser fetch fails: inspect CORS and actual browser request URL.
- Changing environment variables appears ineffective: rebuild and verify the selected environment.

## Completion checklist

- [ ] Correct account/team, repository, commit and root selected.
- [ ] Locked dependency installation and production build succeed.
- [ ] Actual URL/Node version recorded.
- [ ] Public API URL maps to the intended active laptop tunnel, or deliberately selected hosted alternative.
- [ ] Scaffold rendering distinguished from pending end-to-end allocation validation.

No global Vercel CLI or VERCEL_TOKEN is required for this dashboard/Git integration workflow. No deployment was created by this guide.
