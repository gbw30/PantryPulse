#!/usr/bin/env node
// Maps every V1 acceptance ID in docs/testing/user-stories.json to the tests that cover it.
// A test covers an ID through an `@V1-Axx` tag in an e2e title (*.spec.ts) or a `# covers:` /
// `// covers:` header in the first lines of a test file. A story's "checks" list names checks
// ("<script> [args]", run with node) for criteria a test can't prove, such as a recorded run: the
// story is ok while every check exits 0 and pending while one fails, whatever its tests say.
// Under --enforce a story's "tests" entry must be a test file carrying the story's tag (--report
// still counts any entry), and a check script must exist; a pending story still passes.
// Usage: node scripts/testing/story-coverage.cjs --report|--enforce [--root <dir>]
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

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
const coverage = new Map(stories.map((s) => [s.id, mode === 'report' ? [...(s.tests ?? [])] : []]));
const tagged = new Map(); // test file -> the IDs it carries

for (const base of ['apps', 'scripts'].map((d) => path.join(root, d)).filter((d) => fs.existsSync(d))) {
  for (const file of walk(base)) {
    const text = fs.readFileSync(file, 'utf8');
    const found = SPEC.test(path.basename(file))
      ? [...text.matchAll(/@V1-A\d{2}/g)].map((m) => m[0].slice(1))
      : text.split('\n', 5).flatMap((line) => (/^\s*(#|\/\/)\s*covers:/.test(line) ? line.match(ID) ?? [] : []));
    tagged.set(path.relative(root, file).split(path.sep).join('/'), new Set(found));
    for (const id of new Set(found)) coverage.get(id)?.push(path.relative(root, file));
  }
}

const problems = [];
if (mode === 'enforce') {
  for (const s of stories) {
    for (const t of s.tests ?? []) {
      if (!tagged.get(t)?.has(s.id)) problems.push(`invalid ${s.id}: ${t} is not a test file tagged ${s.id}`);
    }
  }
}
const pending = new Map();
for (const s of stories) {
  for (const check of s.checks ?? []) {
    const [file, ...rest] = check.split(' ');
    if (!fs.existsSync(path.join(root, file))) { problems.push(`stale ${s.id}: ${file} does not exist`); continue; }
    const r = spawnSync(process.execPath, [path.join(root, file), ...rest], { cwd: root, encoding: 'utf8', timeout: 120_000 });
    if (r.status === 0) coverage.get(s.id)?.unshift(`${check} (passes)`);
    else pending.set(s.id, [...(pending.get(s.id) ?? []), `${check} exits ${r.status ?? r.signal}`]);
  }
}
for (const [id, tests] of coverage) {
  if (pending.has(id)) console.log(`pending ${id}: ${pending.get(id).join('; ')}${tests.length ? `; tests: ${tests.join(', ')}` : ''}`);
  else console.log(tests.length ? `ok ${id}: ${tests.join(', ')}` : `uncovered ${id}`);
}
for (const line of problems) console.log(line);
const uncovered = [...coverage].filter(([id, tests]) => !tests.length && !pending.has(id)).map(([id]) => id);
const ok = coverage.size - uncovered.length - pending.size;
console.log(`covered ${ok}/${coverage.size}${pending.size ? `; pending ${pending.size} (${[...pending.keys()].join(', ')})` : ''}`);
process.exit(mode === 'enforce' && (uncovered.length || problems.length) ? 1 : 0);
