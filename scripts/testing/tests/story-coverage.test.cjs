// covers: V1-A21
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const script = path.join(__dirname, '..', 'story-coverage.cjs');
const ids = Array.from({ length: 24 }, (_, i) => `V1-A${String(i + 1).padStart(2, '0')}`);

function tree(tests) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'story-coverage-'));
  fs.mkdirSync(path.join(root, 'docs/testing'), { recursive: true });
  fs.mkdirSync(path.join(root, 'scripts'), { recursive: true });
  fs.writeFileSync(path.join(root, 'scripts/check.cjs'), '');
  fs.writeFileSync(path.join(root, 'docs/testing/user-stories.json'), JSON.stringify({ stories: ids.map((id) => ({ id, tests })) }));
  return root;
}
const run = (root) => spawnSync(process.execPath, [script, '--enforce', '--root', root], { encoding: 'utf8' });

test('--enforce accepts a listed evidence check whose file exists', () => {
  const result = run(tree(['scripts/check.cjs V1-A01']));
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('--enforce fails on a listed evidence check whose file does not exist', () => {
  const result = run(tree(['scripts/gone.cjs V1-A01']));
  assert.equal(result.status, 1);
  assert.match(result.stdout, /stale V1-A01: scripts\/gone\.cjs does not exist/);
});

test('the real tree maps every V1-A ID', () => {
  const result = spawnSync(process.execPath, [script, '--enforce'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout, /covered 24\/24/);
});
