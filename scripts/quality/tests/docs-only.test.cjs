const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const script = path.join(__dirname, '..', 'docs-only.cjs');
const { isDocsOnly, TEST_READ } = require(script);
const ROOT = path.join(__dirname, '..', '..', '..');

test('Markdown under docs/ or at the root, read by no test, is docs-only', () => {
  assert.equal(isDocsOnly(['docs/plans/v1/decisions/W4-change-requests.md', 'docs/pantrypulse/BOARD.md']), true);
  assert.equal(isDocsOnly(['CLAUDE.md', 'INSTALLATION.md']), true);
});

test('anything else runs the full job', () => {
  const cases = {
    'no files': [],
    'a code file beside docs': ['docs/pantrypulse/BOARD.md', 'apps/web/src/app/page.tsx'],
    'evidence JSON under docs/': ['docs/optimization/evidence/budget-sweep-v2.json'],
    'Markdown outside docs/ and the root': ['apps/web/tests/e2e/fixtures/v1-connected/README.md'],
    'agent and rule Markdown': ['.claude/rules/web.md'],
    'sample data README': ['data/samples/README.md'],
    'the root README (the quickstart W5 checks)': ['README.md'],
    'an uppercase extension': ['docs/NOTES.MD'],
    'a blank line': [''],
  };
  for (const [name, files] of Object.entries(cases)) assert.equal(isDocsOnly(files), false, name);
  for (const file of TEST_READ) assert.equal(isDocsOnly([file]), false, file);
});

// The CLI diffs BASE..HEAD itself. A rename must count its old path: moving a file a test reads
// (docs/plans/v1/README.md) to a new docs/ name is not docs-only.
test('the CLI classifies BASE..HEAD from git, counting both sides of a rename', () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'docs-only-'));
  const git = (...args) => {
    const r = spawnSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@example.invalid', ...args], { cwd: repo, encoding: 'utf8' });
    assert.equal(r.status, 0, r.stderr);
    return r.stdout.trim();
  };
  const write = (rel, text) => {
    fs.mkdirSync(path.dirname(path.join(repo, rel)), { recursive: true });
    fs.writeFileSync(path.join(repo, rel), text);
  };
  const run = (...args) => spawnSync(process.execPath, [script, ...args], { cwd: repo, encoding: 'utf8' });
  git('init', '-q');
  write('docs/plans/v1/README.md', 'Wave plan\n'.repeat(20));
  write('docs/notes.md', 'notes\n');
  git('add', '.');
  git('commit', '-qm', 'base');
  const base = git('rev-parse', 'HEAD');
  write('docs/notes.md', 'more notes\n');
  git('commit', '-qam', 'docs edit');
  assert.equal(run(base, 'HEAD').stdout, 'true\n');
  git('mv', 'docs/plans/v1/README.md', 'docs/plans/v1/OVERVIEW.md');
  git('commit', '-qm', 'rename a file a test reads');
  assert.equal(run('HEAD^1', 'HEAD').stdout, 'false\n');
  // Missing arguments or a bad revision fail, so the workflow step fails and `full` runs.
  assert.notEqual(run().status, 0);
  assert.notEqual(run(base, 'no-such-rev').status, 0);
});

// A test or script that starts reading a docs/ Markdown file must list it in TEST_READ, or a PR
// changing only that file would skip the job that runs the reader.
test('every docs/ Markdown path quoted in code is in TEST_READ', () => {
  const dirs = ['apps/api/app', 'apps/api/scripts', 'apps/api/tests', 'apps/web/src', 'apps/web/tests', 'scripts', '.github', 'packages'];
  const code = /\.(py|ts|tsx|js|cjs|mjs|sh|ya?ml)$/;
  const quoted = /['"`]([^'"`\n]*docs\/[A-Za-z0-9_./-]+\.md)['"`]/g;
  const found = new Set();
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === 'node_modules' || entry.name === '.venv' || entry.name === '.next') continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (code.test(entry.name) && full !== __filename) {
        for (const match of fs.readFileSync(full, 'utf8').matchAll(quoted)) found.add(match[1].replace(/^.*?(?=docs\/)/, ''));
      }
    }
  };
  for (const dir of dirs) if (fs.existsSync(path.join(ROOT, dir))) walk(path.join(ROOT, dir));
  // A known reader (apps/api/tests/test_v1_contract.py) proves the scan reaches the test trees.
  assert.ok(found.has('docs/plans/v1/README.md'), 'the scan missed a known reader, so it is not scanning');
  assert.deepEqual([...found].filter((file) => !TEST_READ.includes(file)), []);
});
