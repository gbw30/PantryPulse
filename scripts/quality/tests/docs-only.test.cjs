const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
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

test('the CLI reads one path per line on stdin and prints true or false', () => {
  const run = (input) => spawnSync(process.execPath, [script], { input, encoding: 'utf8' });
  assert.deepEqual([run('docs/a.md\nCLAUDE.md\n').stdout, run('docs/a.md\napps/api/app/main.py\n').stdout, run('').stdout],
    ['true\n', 'false\n', 'false\n']);
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
  assert.ok(found.size > 0, 'the scan found no docs/ reads at all, so it is not scanning');
  assert.deepEqual([...found].filter((file) => !TEST_READ.includes(file)), []);
});
