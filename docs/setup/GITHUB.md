# GitHub setup

Purpose: keep PantryPulse source, reviewed changes and test evidence available to the team and deployment providers. Start here; then continue with [Neon](NEON.md). Local prerequisites are in [INSTALLATION.md](../../INSTALLATION.md).

## Account and access

1. Sign in to GitHub or create an account.
2. Open the existing repository: https://github.com/gbw30/PantryPulse.
3. Ask the repository owner for the access needed to contribute. An administrator can manage collaborators/teams in repository settings. Do not create a second repository or transfer ownership as part of ordinary onboarding.
4. Configure Git authentication through Git Credential Manager/browser login or SSH using GitHub's official authentication instructions.
5. The simulated Vercel preview is already connected to this repository. Review the GitHub App's repository access in the account if needed; the laptop backend builds from the reviewed local checkout and needs no GitHub App or CI token.

See [GitHub authentication](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github) and [repository access management](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-teams-and-people-with-access-to-your-repository).

## Clone and verify

In PowerShell:

```powershell
git clone https://github.com/gbw30/PantryPulse.git
Set-Location PantryPulse
git remote -v
git status --short
git branch --show-current
```

For an existing checkout, skip cloning and run the last three commands there. Origin should identify the existing repository. Work from the outer repository root containing apps/, scripts/, compose.yaml and package.json.

Review local changes before pulling, switching branches or synchronizing. Do not overwrite another developer's work. Use a task branch prefixed codex/ when creating a new branch for this project's agent changes; human team branch conventions can be agreed separately.

Run local setup/checks from INSTALLATION.md before opening a pull request.

## Make source deployable

A provider importing GitHub sees only the selected remote commit, not a developer's uncommitted working files.

Before deployment, the owner should review and commit the intended manifests, lockfiles, application files and docs, then push the reviewed branch. Include apps/api/Dockerfile, apps/api/uv.lock, the root package-lock.json and workspace manifests. Do not use an indiscriminate add of unrelated work or private configuration.

No commit or push is performed by this guide.

## Checks and deployment connections

The existing .github/workflows/pantrypulse-ci.yml.template is a template, not an active workflow. Renaming it is not sufficient: it references older Node/lockfile paths and future domain tests. Adapt it to the current root npm workspace, chosen Python environment and implemented checks before enabling it.

Current local commands:

```powershell
npm run check
npm run build
npm run test:config
npm run test:e2e
```

Configure branch protections/required checks when the checks are active. Hosting integrations may deploy automatically on pushes to their configured branches; verify that branch/environment mapping before connecting them.

## Completion checklist

- [ ] Team members can access the existing repository.
- [ ] Git authentication works and origin is correct.
- [ ] The exact reviewed deployment commit is present on GitHub.
- [ ] Lockfiles and required source files are included.
- [ ] CI is described truthfully as active or pending.
- [ ] Owner verifies the existing Vercel GitHub integration has only the intended repository access.

No GitHub token is required in the PantryPulse application runtime. Follow the laptop workflow in [EXTERNAL-SERVICES.md](../../EXTERNAL-SERVICES.md); Vercel's dashboard integration is optional for a hosted frontend. Do not commit tokens.
