#!/usr/bin/env node
// Group B (V1-A21): the full backend suite against PostgreSQL 16 in Linux containers, so Windows
// contributors can run it. compose.test.yaml's command fails on any skipped test.
// Usage: npm run test:docker
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');

// Its own project, so `down -v` can never touch the app stack (even under a lane's COMPOSE_PROJECT_NAME).
const project = (env) => `${env.COMPOSE_PROJECT_NAME || 'pantrypulse'}-tests`;

function main() {
  fs.mkdirSync(path.join(root, 'artifacts/testing'), { recursive: true });
  const compose = ['compose', '-p', project(process.env), '-f', 'compose.test.yaml'];
  const run = (args, timeout) => spawnSync('docker', [...compose, ...args], { cwd: root, stdio: 'inherit', windowsHide: true, timeout });
  let result;
  let cleanup;
  try {
    result = run(['up', '--build', '--abort-on-container-exit', '--exit-code-from', 'api-tests'], 40 * 60 * 1000);
  } finally {
    cleanup = run(['down', '-v', '--remove-orphans'], 120_000);
  }
  for (const r of [result, cleanup]) if (r?.error) console.error(r.error.message);
  if (result?.status === 0) console.log('JUnit: artifacts/testing/api-linux.xml');
  process.exitCode = result?.status === 0 && cleanup?.status === 0 ? 0 : 1;
}

if (require.main === module) main();
module.exports = { project };
