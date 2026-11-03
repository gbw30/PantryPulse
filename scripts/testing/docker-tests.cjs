// One isolated Compose project; cleanup is limited to this kit's ephemeral stack.
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "../..");
fs.mkdirSync(path.join(root, "artifacts/testing"), { recursive: true });
const compose = ["compose", "-f", "compose.test.yaml"];
let result;
let cleanup;
try {
  result = spawnSync("docker", [...compose, "up", "--build", "--abort-on-container-exit", "--exit-code-from", "api-tests"], {
    cwd: root, stdio: "inherit", windowsHide: true, timeout: 20 * 60 * 1000,
  });
} finally {
  cleanup = spawnSync("docker", [...compose, "down"], {
    cwd: root, stdio: "inherit", windowsHide: true, timeout: 60_000,
  });
}
if (result?.error) console.error(result.error.message);
if (cleanup?.error) console.error(cleanup.error.message);
process.exitCode = result?.status === 0 && cleanup?.status === 0 ? 0 : 1;
