# Testing PantryPulse v1

How each test kit runs, what it proves, and what it does not. A skipped, mocked or fixture-only check is never evidence that the application works (CLAUDE.md, V1-SPEC §13). Every acceptance ID (V1-A01–A24) maps to at least one check below; `story-coverage.cjs --enforce` keeps that true.

## Commands

| Kit | Command (from the repository root) | Runs on | Proves |
|---|---|---|---|
| Quick gate | `node scripts/quality/run.cjs quick` | host | web types and lint, API lint, API tests (the PostgreSQL suites skip here; never count them) |
| Full gate | `set -a; . ./.env.lane; set +a; node scripts/quality/run.cjs full` | host + test PostgreSQL | everything, with `PP19_TEST_SCHEMA_ISOLATION=1` and zero skips |
| E2E gate | `node scripts/quality/run.cjs e2e` | host, Playwright | browser journeys against the app (set `PLAYWRIGHT_PORT` to a free port) |
| Group A, unit | `npm run test:unit --workspace @pantrypulse/web` | host, Vitest + `node --test` | UI state, import errors, ranking, action text |
| **Group B, backend in Linux** | `npm run test:docker` | Docker only | the whole backend suite on PostgreSQL 16 in Linux containers, 0 skips |
| Config tests | `npm run test:config` | host | compose, gate and hook configuration |
| Lane script tests | `node --test scripts/testing/tests/*.test.cjs` | host + Docker CLI | the tools in this guide |
| Story coverage | `node scripts/testing/story-coverage.cjs --enforce` | host | each V1-A ID maps to a test or an evidence check |
| Egress journey | `set -a; . ./.env.lane; set +a; node scripts/testing/egress-journey.cjs` | Docker | V1-A03, V1-A04: outbound calls and secret leaks during the journey |
| Measurements | `set -a; . ./.env.lane; set +a; node scripts/bench/run-all.cjs` | Docker + host | V1-A09, A17, A19: [HARDWARE.md](../pantrypulse/HARDWARE.md) |
| Recorded runs | `node scripts/testing/check-recorded-runs.cjs` | host | V1-A01, A18, A24 (pull path): a person's runs on clean machines |

## Group B: `npm run test:docker`

For contributors without Python or a local PostgreSQL, including Windows and macOS hosts. Docker is the only prerequisite.

- `compose.test.yaml` builds the API image (`apps/api/Dockerfile`, from `uv.lock`), starts `postgres:16` with its data in tmpfs, and runs `pytest -q --junitxml` in a Linux container.
- The same container then runs `scripts/quality/require-test-evidence.py` (the check CI uses) on that JUnit file. Any skipped, failed or missing test fails the run.
- The suite sees the working tree through read-only mounts of the paths it reads. `.env*` files and `.pantrypulse/` are never mounted. The JUnit file lands in `artifacts/testing/api-linux.xml`.
- The runner uses its own Compose project, `<COMPOSE_PROJECT_NAME or pantrypulse>-tests`, and removes it afterwards, so it never touches an install's containers or volumes.
- If a test starts reading a new repository-root file, add a mount for it to `compose.test.yaml`. `scripts/testing/tests/docker-tests.test.cjs` checks that every mount source exists.

## Story coverage

`scripts/testing/story-coverage.cjs` reads [user-stories.json](user-stories.json): one entry per V1-A ID, with V1-SPEC §13's criterion and evidence. A test covers an ID when:

- an e2e title (`*.spec.ts`) carries `@V1-Axx`; or
- one of a test file's first five lines is `# covers: V1-Axx` (Python) or `// covers: V1-Axx` (JS/TS).

A story's `tests` list holds only evidence checks that carry no tag, written `<path> [args]`. `--enforce` exits 1 when an ID has no coverage or a listed path no longer exists. `--report` lists the map without failing.

## Recorded-evidence checks: V1-A01, V1-A18, V1-A24 (pull path)

A clean install (A01), a stranger following the README (A18) and pulling the published images (A24) can only be run by a person on clean Windows 11 and Ubuntu 24.04 machines. Each run becomes a record that `scripts/testing/check-recorded-runs.cjs` validates.

**Current state:** no run is recorded yet, so the check exits 1. These criteria stay open until the runs exist; the check is never skipped. The A24 pull path also needs the first authorized image release.

To record a run, put the files in `docs/testing/evidence/runs/`:

```json
{
  "id": "V1-A01",
  "os": "windows-11",
  "path": "build",
  "commit": "<the 40-character commit that was cloned>",
  "docker_version": "<docker version --format '{{.Server.Version}}'>",
  "started_at": "2026-11-20T10:00:00Z",
  "elapsed_seconds": 640,
  "result": "pass",
  "evidence": ["a01-windows-11-login.png"]
}
```

- `id` is `V1-A01`, `V1-A18` or `V1-A24`; `os` is `windows-11` or `ubuntu-24.04`; `path` is `build` (`docker compose up --build`) or `pull` (plain `docker compose up` after a release); `result` is `pass` or `fail`.
- `evidence` lists files next to the record: the login-page screenshot for A01; the observer's notes for A18 (install → sample → import of their own template set, including `inbound.csv` and `donation_history.csv` → forecast → compare → export); a screenshot and the elapsed time for A24.
- The check needs a passing record per OS for each ID, with `path: pull` for A24. The commit must exist in this repository and every evidence file must exist.

## Egress journey (V1-A03, V1-A04)

`scripts/testing/egress-journey.cjs` installs the stack fresh under `COMPOSE_PROJECT_NAME` (it runs `docker compose down -v` first, so it refuses the default `pantrypulse` project) and builds with lane-local image tags, so another install's images are never retagged.

1. **Capture.** `scripts/testing/egress-sniff.py` runs as the `egress-capture` service (`compose.test.yaml`, profile `egress`) in the Docker host's network namespace. On the stack's bridge it records each outbound TCP connection with its TLS server name and any outbound UDP. It reads no other payload.
2. **Journey.** Over HTTP through the web's same-origin proxy, it drives these steps on the two samples:
   - sign in with the generated password;
   - A06 templates, and an A07 malformed import, rejected with no network created;
   - one import of user addresses (A10), which geocodes through Census;
   - A12 forecast and backtest, and the A13 ranking and projection;
   - A14 Pantry comparisons in both transfer modes and A15 Retail in units and USD, every method verified;
   - A16 actions and CSV export.
3. **Checks.** Only `geocoding.geo.census.gov` is allowed, and `routes.googleapis.com` only when the user saved a Google key. `api.census.gov` is never called, because ACS rates come from the bundled table. A connection without a TLS server name, or any outbound UDP other than DNS, is flagged. The generated password and proxy token must not appear in `docker compose logs`, in the web's `.next` output, in tracked or untracked-but-not-ignored files, or in any commit made since the run started.
4. **Positive control.** The run fails if the capture saw no Census connection, because the journey geocodes and a capture that missed it would be blind.

It writes `artifacts/egress/report.json`. It reports secrets by name, never by value.

**Limits:**
- IPv4 only; the compose bridge has no IPv6.
- On Docker Desktop, the VM forwards DNS itself, so lookups can't be attributed to the stack. They only name addresses in the report.
- A Google-keyed run is not part of the journey (A03 is "no keys"). A11's live keyed run is separate.
- It exercises the journey's code paths, not every route.

## Measurements (V1-A09, A17, A19)

`scripts/bench/run-all.cjs` measures the first-run build and start, the idle stack, the maximum-envelope import, the forecast, and both comparison modes. It writes `docs/testing/evidence/bench-<date>.json` and regenerates the measurement block of [HARDWARE.md](../pantrypulse/HARDWARE.md) from it. `scripts/testing/tests/bench-report.test.cjs` checks that every number in that block is the artifact's own, and that the artifact names a real commit and timestamps.
