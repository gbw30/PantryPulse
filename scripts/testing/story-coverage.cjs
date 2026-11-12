#!/usr/bin/env node
// Maps every V1 acceptance ID in docs/testing/user-stories.json to the tests that cover it.
// A test covers an ID through an `@V1-Axx` tag in an e2e title (*.spec.ts) or a `# covers:` /
// `// covers:` header in the first lines of a test file. A story's non-empty "tests" list
// (e.g. a recorded manual run) also counts.
// Usage: node scripts/testing/story-coverage.cjs --report|--enforce [--root <dir>]
const fs = require('node:fs');
const path = require('node:path');

const args = process.argv.slice(2);
const mode = args.includes('--enforce') ? 'enforce' : args.includes('--report') ? 'report' : null;
const rootIndex = args.indexOf('--root');
const root = path.resolve(rootIndex >= 0 ? args[rootIndex + 1] : path.join(__dirname, '..', '..'));
if (!mode) {
  console.error('usage: story-coverage.cjs --report|--enforce [--root <dir>]');
  process.exit(2);
}

const SKIP = new Set(['node_modules', '.venv', '.next', '.next-e2e', '.git', '.claude', 'artifacts', 'test-results', 'playwright-report', '__pycache__']);
const SPEC = /\.spec\.[cm]?[jt]sx?$/;
const TEST = /(\.test\.[cm]?[jt]sx?|^test_.*\.py|_test\.py)$/;
const ID = /V1-A\d{2}/g;

function* walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (SPEC.test(entry.name) || TEST.test(entry.name)) yield full;
  }
}

const stories = JSON.parse(fs.readFileSync(path.join(root, 'docs/testing/user-stories.json'), 'utf8')).stories;
const coverage = new Map(stories.map((s) => [s.id, [...(s.tests ?? [])]]));

for (const base of ['apps', 'scripts'].map((d) => path.join(root, d)).filter((d) => fs.existsSync(d))) {
  for (const file of walk(base)) {
    const text = fs.readFileSync(file, 'utf8');
    const found = SPEC.test(path.basename(file))
      ? [...text.matchAll(/@V1-A\d{2}/g)].map((m) => m[0].slice(1))
      : text.split('\n', 5).flatMap((line) => (/^\s*(#|\/\/)\s*covers:/.test(line) ? line.match(ID) ?? [] : []));
    for (const id of new Set(found)) coverage.get(id)?.push(path.relative(root, file));
  }
}

// Under --enforce, a listed evidence check ("<path> [args]") must name a file that exists.
const stale = mode !== 'enforce' ? [] : stories.flatMap((s) => (s.tests ?? [])
  .map((t) => t.split(' ')[0]).filter((file) => !fs.existsSync(path.join(root, file))).map((file) => `stale ${s.id}: ${file} does not exist`));
const uncovered = [...coverage].filter(([, tests]) => tests.length === 0).map(([id]) => id);
for (const [id, tests] of coverage) console.log(tests.length ? `ok ${id}: ${tests.join(', ')}` : `uncovered ${id}`);
for (const line of stale) console.log(line);
console.log(`covered ${coverage.size - uncovered.length}/${coverage.size}`);
process.exit(mode === 'enforce' && (uncovered.length || stale.length) ? 1 : 0);
