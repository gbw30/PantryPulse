// covers: V1-A21
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const script = path.join(__dirname, '..', 'story-coverage.cjs');
const ids = Array.from({ length: 24 }, (_, i) => `V1-A${String(i + 1).padStart(2, '0')}`);

/** A tree where every ID but V1-A01 has a tagged test, and V1-A01 gets `story`'s fields. */
function tree(story) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'story-coverage-'));
  const write = (rel, text) => {
    fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
    fs.writeFileSync(path.join(root, rel), text);
  };
  write('scripts/x/tests/rest.test.cjs', `// covers: ${ids.slice(1).join(', ')}\n`);
  write('scripts/pass.cjs', 'process.exitCode = 0;\n');
  write('scripts/fail.cjs', 'process.exitCode = 1;\n');
  write('README.md', '# not a test\n');
  write('docs/testing/user-stories.json', JSON.stringify({ stories: ids.map((id) => (id === 'V1-A01' ? { id, ...story } : { id })) }));
  return root;
}
const run = (root, flag = '--enforce') => spawnSync(process.execPath, [script, flag, '--root', root], { encoding: 'utf8' });

test('--enforce rejects a tests entry that is not a test file carrying the story tag', () => {
  for (const tests of [['README.md'], ['scripts/x/tests/rest.test.cjs'], ['scripts/pass.cjs']]) {
    const result = run(tree({ tests }));
    assert.equal(result.status, 1, `${tests} must not cover V1-A01:\n${result.stdout}`);
    assert.match(result.stdout, /invalid V1-A01: .* is not a test file tagged V1-A01/);
  }
});

test('a listed check that passes covers its story', () => {
  const result = run(tree({ checks: ['scripts/pass.cjs V1-A01'] }));
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout, /^ok V1-A01: scripts\/pass\.cjs V1-A01 \(passes\)/m);
  assert.match(result.stdout, /covered 24\/24/);
});

test('a listed check that fails leaves its story pending, never ok, even with tagged tests', () => {
  const root = tree({ checks: ['scripts/fail.cjs V1-A01'] });
  fs.writeFileSync(path.join(root, 'scripts/x/tests/a01.test.cjs'), '// covers: V1-A01\n');
  const result = run(root);
  assert.doesNotMatch(result.stdout, /^ok V1-A01/m);
  assert.match(result.stdout, /^pending V1-A01: scripts\/fail\.cjs V1-A01 exits 1/m);
  assert.match(result.stdout, /covered 23\/24; pending 1 \(V1-A01\)/);
  assert.equal(result.status, 0, 'a pending story is mapped to its check, so --enforce passes');
});

test('--enforce fails on a listed check whose file does not exist', () => {
  const result = run(tree({ checks: ['scripts/gone.cjs V1-A01'] }));
  assert.equal(result.status, 1);
  assert.match(result.stdout, /stale V1-A01: scripts\/gone\.cjs does not exist/);
});

test('the real tree maps every V1-A ID; A01, A18 and A24 stay pending until their runs are recorded', () => {
  const result = spawnSync(process.execPath, [script, '--enforce'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stdout);
  for (const id of ['V1-A01', 'V1-A18', 'V1-A24']) assert.match(result.stdout, new RegExp(`^pending ${id}: scripts/testing/check-recorded-runs\\.cjs ${id} exits 1`, 'm'));
  assert.doesNotMatch(result.stdout, /^uncovered /m);
});
