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
| Claude Code | CLI 2.1.310 (npm global, 2026-10-24); desktop app 3.6556.2, Agent SDK 0.3.308 | |
| Language servers | pyright 1.1.414, typescript-language-server 6.0.2, global TypeScript 5.9.3 | npm global, for the LSP plugins. Global TypeScript is pinned to the workspace version because TypeScript 7 ships no `tsserver.js` |

## Configuration verification status

| Item | Status | Evidence |
|---|---|---|
| Hook syntax (`command` + `args` exec form, `onFailure: block`, PreToolUse deny JSON, Stop exit 2) | Checked against docs | code.claude.com/docs/en/hooks, 2026-10-23 |
| `onFailure: block` honored by the installed build | VERSION OK | CLI 2.1.310 meets the documented v2.1.295 minimum. Not exercised with a failing hook process. The hook script also exits 2 on bad input, which blocks independently of `onFailure` |
| Hook scripts with synthetic inputs | PASS | `node --test scripts/quality/tests/*.test.cjs`, plus manual Windows-path and space-in-path cases |
| Agents load in a live session | PASS | A new session listed all 8 agent types |
| Skills load in a live session | PARTIAL | The model-invocable skills verify-forecast, verify-solver and visual-review were listed. The manual run-demo and release-check skills are hidden from the model by design; confirm they appear in the `/` menu |
| Path-scoped rules load | PENDING | Confirm when the first file under a rule's `paths` is edited |
| PreToolUse hook fires live | PASS | Fired in the installing session and denied a Bash call whose text contained a hard-reset/force pattern. It matches text anywhere in the command, including quoted test strings, so put such strings in a script file |
| SessionStart hook fires live | PASS | A new session received the hook's PantryPulse context message |
| Stop gate resolves the active worktree | PASS | In a disposable detached worktree at 3f84c9b, path with a space, the main checkout's hook was driven by a synthetic gate: disabled exits 0 with UNVERIFIED, failing exits 2, `stop_hook_active` exits 0, passing exits 0, and evidence is written in the worktree. Worktree removed afterwards |
| Stop gate | ENABLED (quick gate) | `.claude/quality-gate.json` has `enabled: true` since commit 245ded0. It runs the quick gate only, not full or e2e |
| CI | TEMPLATE ONLY | `.github/workflows/pantrypulse-ci.yml.template` is not active |
| Plugins installed | PASS | 2026-10-24: `claude plugin marketplace add anthropics/claude-plugins-official` (declared in user settings), then `claude plugin install <name>@claude-plugins-official --scope project`. `claude plugin list` shows superpowers 7.0.0, context7 58267944f921, pyright-lsp 1.0.0, typescript-lsp 1.0.0 and frontend-design 58267944f921, all project scope and enabled. Superpowers was reviewed at the v7.0.1 tag; the installed 7.0.0 has the same single SessionStart hook and 15 skills. The official marketplace auto-updates, so re-review on version changes |
| Plugins load in a live session | PENDING | Start a new session. Confirm both SessionStart contexts (PantryPulse and `using-superpowers`), `/superpowers:*` and `/frontend-design:*` skills, the context7 tools (`mcp__plugin_context7_context7__*`), and LSP diagnostics after editing a .py and a .tsx file |
| Builder access to context7 and LSP | PENDING | Builders, integration-fixer and verifier list `LSP` and `mcp__plugin_context7_context7__*`; adversarial-reviewer lists `LSP`. Confirm with one builder task that both tools are available. context7 sends library-name queries to Upstash, so never include secrets |
| Custom skills | PASS (static), PENDING (live) | egp-pi-model, cpsat-patterns, research-claims-check added; verify-solver and verify-forecast updated to V4. The cpsat-patterns encodings and the ADR 0001 oracle were run against ortools 9.15.6755 in the API container. Confirm the new skills are listed in a new session |
| Builder/verifier preload of `superpowers:*` skills | PENDING | Namespaced plugin skills in an agent's `skills:` list aren't documented. Spawn one builder with a trivial task and confirm the skills are in its context. If they aren't, it can still invoke them through the `Skill` tool it now has |

## Local development services

`docker compose up -d --wait` from the repo root starts `postgres:16`, matching CI, on **127.0.0.1:55432**. Ports 5432, 5433 and 15432 are already used by other Postgres instances on this machine. Local-only credentials: user `pantrypulse`, password `local_dev_only`.

| Database | Used by |
|---|---|
| pantrypulse_dev | Integration pair, web 3000 / API 8000 (lead only for migrations and seed) |
| pantrypulse_test | Local pytest and migration tests |
| pantrypulse_lane1..3 | Forecast, solver and frontend worktrees (web 3001-3003 / API 8001-8003) |

Local DATABASE_URL form, no TLS: `postgresql+psycopg://pantrypulse:local_dev_only@127.0.0.1:55432/pantrypulse_dev`. Put it in `apps/api/.env` yourself when the API exists; the PreToolUse guard blocks agents from writing `.env` files. The `api.env.example` template's `sslmode=require` URL is for hosted Neon.

The init script in `scripts/db/init/` runs only on a fresh volume. Use `docker compose down` to stop. `docker compose down -v` also destroys the local data, so ask the lead first.
