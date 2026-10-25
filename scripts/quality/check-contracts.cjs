#!/usr/bin/env node
const { spawnSync } = require("node:child_process");
const path = require("node:path");
const root = path.resolve(__dirname, "../..");
const python = process.env.PP_PYTHON || path.join(root, "apps/api/.venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
for (const [command, args] of [
  [python, ["apps/api/scripts/export_openapi.py", "--check", "packages/contracts/openapi.json"]],
  [process.execPath, ["node_modules/openapi-typescript/bin/cli.js", "packages/contracts/openapi.json", "-o", "packages/contracts/src/schema.d.ts", "--check"]],
]) {
  const result = spawnSync(command, args, { cwd: root, stdio: "inherit" });
  if (result.error) console.error(result.error.message);
  if (result.status !== 0) process.exit(result.status || 1);
}
