// covers: V1-A21
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const script = path.join(__dirname, '..', '..', 'testing', 'story-coverage.cjs');
const ids = Array.from({ length: 24 }, (_, i) => `V1-A${String(i + 1).padStart(2, '0')}`);

function tree() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'story-coverage-'));
  const write = (rel, text) => {
    fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
    fs.writeFileSync(path.join(root, rel), text);
  };
  write('docs/testing/user-stories.json', JSON.stringify({ stories: ids.map((id) => ({ id, tests: [] })) }));
  write('apps/web/tests/e2e/install.spec.ts', 'test("login page loads @V1-A01", async () => {});\n');
  // An ID mentioned in a non-test file must not count.
  write('apps/web/src/note.ts', '// covers: V1-A02\n');
  // A tag inside an ignored dependency folder must not count.
  write('apps/web/node_modules/x/tests/a.spec.ts', 'test("x @V1-A03", () => {});\n');
  return root;
}

const run = (root, flag) => spawnSync(process.execPath, [script, flag, '--root', root], { encoding: 'utf8' });

test('--report lists the 23 uncovered IDs and exits 0', () => {
  const result = run(tree(), '--report');
  assert.equal(result.status, 0, result.stderr);
  const uncovered = result.stdout.match(/V1-A\d{2}/g).filter((id) => result.stdout.includes(`uncovered ${id}`));
  assert.equal(uncovered.length, 23);
  assert.doesNotMatch(result.stdout, /uncovered V1-A01\b/);
  assert.match(result.stdout, /covered 1\/24/);
});

test('--enforce exits 1 while any ID is uncovered', () => {
  const result = run(tree(), '--enforce');
  assert.equal(result.status, 1);
});

test('python "# covers:" headers and a non-empty tests list count', () => {
  const root = tree();
  fs.mkdirSync(path.join(root, 'apps/api/tests'), { recursive: true });
  fs.writeFileSync(path.join(root, 'apps/api/tests/test_x.py'), '# covers: V1-A02, V1-A03\n');
  const storiesFile = path.join(root, 'docs/testing/user-stories.json');
  const stories = JSON.parse(fs.readFileSync(storiesFile, 'utf8'));
  stories.stories[3].tests = ['manual: recorded run'];
  fs.writeFileSync(storiesFile, JSON.stringify(stories));
  const result = run(root, '--report');
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /covered 4\/24/);
});
