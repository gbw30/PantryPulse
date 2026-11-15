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
  write('scripts/fail.cjs', 'console.log("pending: nothing recorded yet");\nprocess.exitCode = 1;\n');
  write('scripts/crash.cjs', 'null.x;\n');
  write('scripts/hang.cjs', 'setInterval(() => {}, 1000);\n');
  write('scripts/two.cjs', 'process.exitCode = 2;\n');
  write('scripts/noisy.cjs', 'console.error("warning: something is off");\nprocess.exitCode = 1;\n');
  write('README.md', '# not a test\n');
  write('docs/testing/user-stories.json', JSON.stringify({ stories: ids.map((id) => (id === 'V1-A01' ? { id, ...story } : { id })) }));
  return root;
}
const run = (root, flag = '--enforce', env = {}) =>
  spawnSync(process.execPath, [script, flag, '--root', root], { encoding: 'utf8', env: { ...process.env, ...env } });

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

test('a check that crashes, exits with another code, or writes to stderr is broken, never pending, and fails --enforce', () => {
  for (const [file, reason] of [
    ['crash', /exits 1 with stderr: .*TypeError/],
    ['two', /exits 2/],
    ['noisy', /exits 1 with stderr: warning: something is off/],
  ]) {
    const result = run(tree({ checks: [`scripts/${file}.cjs V1-A01`] }));
    assert.equal(result.status, 1, `${file}:\n${result.stdout}`);
    assert.match(result.stdout, new RegExp(`^broken V1-A01: scripts/${file}\\.cjs V1-A01 ${reason.source}`, 'm'));
    assert.doesNotMatch(result.stdout, /^(ok|pending) V1-A01/m);
    assert.match(result.stdout, /covered 23\/24; broken 1 \(V1-A01\)/);
  }
});

test('a check that runs past the timeout is broken and fails --enforce', () => {
  const started = Date.now();
  const result = run(tree({ checks: ['scripts/hang.cjs V1-A01'] }), '--enforce', { PP_STORY_CHECK_TIMEOUT_MS: '500' });
  assert.ok(Date.now() - started < 20_000, 'the override shortens the timeout');
  assert.equal(result.status, 1, result.stdout);
  assert.match(result.stdout, /^broken V1-A01: scripts\/hang\.cjs V1-A01 timed out after 500 ms/m);
});

test('--enforce fails on a listed check whose file does not exist', () => {
  const result = run(tree({ checks: ['scripts/gone.cjs V1-A01'] }));
  assert.equal(result.status, 1);
  assert.match(result.stdout, /stale V1-A01: scripts\/gone\.cjs does not exist/);
});

test("V1-A24 runs the version-pin check, so a README pin that differs from compose.yaml is never ok", () => {
  const stories = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', '..', 'docs/testing/user-stories.json'), 'utf8')).stories;
  const a24 = stories.find((s) => s.id === 'V1-A24');
  assert.ok(a24.checks.includes('scripts/testing/check-version-pin.cjs'), JSON.stringify(a24.checks));
  // The real check, in a tree whose README pins 0.1.0 while compose.yaml tags 0.2.0.
  const root = tree({ checks: ['scripts/testing/check-version-pin.cjs'] });
  fs.mkdirSync(path.join(root, 'scripts/testing'), { recursive: true });
  fs.copyFileSync(path.join(__dirname, '..', 'check-version-pin.cjs'), path.join(root, 'scripts/testing/check-version-pin.cjs'));
  fs.writeFileSync(path.join(root, 'README.md'), 'Version pin: `0.1.0`\n');
  fs.writeFileSync(path.join(root, 'compose.yaml'), 'services:\n  api:\n    image: ghcr.io/gbw30/pantrypulse-api:0.2.0\n');
  const result = run(root);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout, /^pending V1-A01: scripts\/testing\/check-version-pin\.cjs exits 1/m);
  assert.doesNotMatch(result.stdout, /^ok V1-A01/m);
});

test('the real tree maps every V1-A ID; A01, A18 and A24 stay pending until their runs are recorded', () => {
  const result = spawnSync(process.execPath, [script, '--enforce'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stdout);
  for (const id of ['V1-A01', 'V1-A18', 'V1-A24']) assert.match(result.stdout, new RegExp(`^pending ${id}: scripts/testing/check-recorded-runs\\.cjs ${id} exits 1`, 'm'));
  assert.doesNotMatch(result.stdout, /^(uncovered|broken) /m);
  assert.match(result.stdout, /^pending V1-A24: [^\n]*check-version-pin\.cjs \(passes\)/m, 'the real README and compose.yaml agree');
});
