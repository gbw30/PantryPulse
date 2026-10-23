# Environment record

Recorded 2026-10-23 when the Claude Code kit was installed. Update this file when a toolchain version changes.

| Tool | Version | Note |
|---|---|---|
| OS | Windows 11 Home 10.0.26200 | Git Bash and PowerShell both available |
| Node.js | v24.16.0 | CI template targets Node 22 and no Node version manager is installed. Keep code Node 22-compatible, or have the lead move CI to 24 when scaffolding |
| Python (system) | 3.15.0 | Not used by the project |
| Python (project) | 3.12.13, uv-managed | Root `.python-version` pins 3.12, which uv applies to `apps/api` |
| uv | 0.11.15 | |
| Git | 2.56.0.windows.2 | |
| Claude Code | desktop app 3.6556.2, Agent SDK 0.3.308 | No `claude` CLI on PATH, so `claude --version` was unavailable |

## Configuration verification status

| Item | Status | Evidence |
|---|---|---|
| Hook syntax (`command` + `args` exec form, `onFailure: block`, PreToolUse deny JSON, Stop exit 2) | Checked against docs | code.claude.com/docs/en/hooks, 2026-10-23 |
| `onFailure: block` honored by the installed build | UNVERIFIED | Needs Claude Code v2.1.295+, and the CLI version could not be read. The hook script also exits 2 on bad input, which blocks independently of `onFailure` |
| Hook scripts with synthetic inputs | PASS | `node --test scripts/quality/tests/*.test.cjs`, plus manual Windows-path and space-in-path cases |
| Agents load in a live session | PASS | A new session listed all 8 agent types |
| Skills load in a live session | PARTIAL | The model-invocable skills verify-forecast, verify-solver and visual-review were listed. The manual run-demo and release-check skills are hidden from the model by design; confirm they appear in the `/` menu |
| Path-scoped rules load | PENDING | Confirm when the first file under a rule's `paths` is edited |
| PreToolUse hook fires live | PASS | Fired in the installing session and denied a Bash call whose text contained a hard-reset/force pattern. It matches text anywhere in the command, including quoted test strings, so put such strings in a script file |
| SessionStart hook fires live | PASS | A new session received the hook's PantryPulse context message |
| Stop gate resolves the active worktree | PASS | In a disposable detached worktree at 3f84c9b, path with a space, the main checkout's hook was driven by a synthetic gate: disabled exits 0 with UNVERIFIED, failing exits 2, `stop_hook_active` exits 0, passing exits 0, and evidence is written in the worktree. Worktree removed afterwards |
| Stop gate | DISABLED (UNVERIFIED) | Enable only after the app's quick-gate commands exist and pass |
| CI | TEMPLATE ONLY | `.github/workflows/pantrypulse-ci.yml.template` is not active |

## Local development services

`docker compose up -d --wait` from the repo root starts `postgres:16`, matching CI, on **127.0.0.1:55432**. Ports 5432, 5433 and 15432 are already used by other Postgres instances on this machine. Local-only credentials: user `pantrypulse`, password `local_dev_only`.

| Database | Used by |
|---|---|
| pantrypulse_dev | Integration pair, web 3000 / API 8000 (lead only for migrations and seed) |
| pantrypulse_test | Local pytest and migration tests |
| pantrypulse_lane1..3 | Forecast, solver and frontend worktrees (web 3001-3003 / API 8001-8003) |

Local DATABASE_URL form, no TLS: `postgresql+psycopg://pantrypulse:local_dev_only@127.0.0.1:55432/pantrypulse_dev`. Put it in `apps/api/.env` yourself when the API exists; the PreToolUse guard blocks agents from writing `.env` files. The `api.env.example` template's `sslmode=require` URL is for hosted Neon.

The init script in `scripts/db/init/` runs only on a fresh volume. Use `docker compose down` to stop. `docker compose down -v` also destroys the local data, so ask the lead first.
