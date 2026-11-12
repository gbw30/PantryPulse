// covers: V1-A21
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.join(__dirname, '..', '..', '..');

function config() {
  const result = spawnSync('docker', ['compose', '-f', 'compose.test.yaml', 'config', '--format', 'json'], {
    cwd: root, encoding: 'utf8', timeout: 60000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

test('test_command_includes_require_no_skips', () => {
  const command = config().services['api-tests'].command.join(' ');
  assert.match(command, /pytest .*--junitxml=\/reports\/api-linux\.xml/);
  // The same JUnit file must pass the CI evidence check, which rejects any skipped test.
  assert.match(command, /&& .*require-test-evidence\.py \/reports\/api-linux\.xml/);
  const env = config().services['api-tests'].environment;
  assert.equal(env.PP19_TEST_SCHEMA_ISOLATION, '1', 'PostgreSQL suites opt in instead of skipping');
  assert.ok(env.PP19_TEST_DATABASE_URL && env.PP_TEST_DATABASE_URL);
});

test('test_compose_test_mounts_exist_in_tree', () => {
  const binds = Object.values(config().services).flatMap((s) => s.volumes ?? []).filter((v) => v.type === 'bind');
  assert.ok(binds.length > 0);
  for (const { source, target, read_only: readOnly } of binds) {
    const rel = path.relative(root, source);
    assert.ok(!rel.startsWith('..'), `${source} is inside the repository`);
    assert.doesNotMatch(rel, /(^|[\\/])\.env|\.pantrypulse/, `${rel} must not expose local secrets`);
    if (readOnly) assert.ok(fs.existsSync(source), `${rel} (mounted at ${target}) exists in the tree`);
    else assert.match(rel, /^artifacts[\\/]/, `${rel} is the only writable mount, under artifacts/`);
  }
});

test('the runner uses its own Compose project, never the app stack', () => {
  const { project } = require('../docker-tests.cjs');
  assert.equal(project({}), 'pantrypulse-tests');
  assert.equal(project({ COMPOSE_PROJECT_NAME: 'pp-packaging' }), 'pp-packaging-tests');
});
