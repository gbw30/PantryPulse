#!/usr/bin/env node
// Maps every V1 acceptance ID in docs/testing/user-stories.json to the tests that cover it.
// A test covers an ID through an `@V1-Axx` tag in an e2e title (*.spec.ts) or a `# covers:` /
// `// covers:` header in the first lines of a test file. A story's "checks" list names checks
// ("<script> [args]", run with node) for criteria a test can't prove, such as a recorded run: the
// story is ok while every check exits 0, whatever its tests say. A check reports "not recorded
// yet" by exiting 1 with nothing on stderr: the story is pending. Anything else is broken: another
// exit code, a signal, a timeout (PP_STORY_CHECK_TIMEOUT_MS, default 120 s), a spawn error, or exit 1
// with stderr output (Node exits 1 on an uncaught exception, so exit 1 alone can't mean pending).
// Under --enforce a story's "tests" entry must be a test file carrying the story's tag (--report
// still counts any entry), a check script must exist and no check may be broken; a pending story
// still passes.
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
const timeout = Number(process.env.PP_STORY_CHECK_TIMEOUT_MS) || 120_000;
// The error line of a stack trace, else the first line.
const excerpt = (text) => { const lines = text.split('\n').map((l) => l.trim()).filter(Boolean); return lines.find((l) => /^\w*Error\b/.test(l)) ?? lines[0]; };
const pending = new Map();
const broken = new Map();
const add = (map, id, text) => map.set(id, [...(map.get(id) ?? []), text]);
for (const s of stories) {
  for (const check of s.checks ?? []) {
    const [file, ...rest] = check.split(' ');
    if (!fs.existsSync(path.join(root, file))) { problems.push(`stale ${s.id}: ${file} does not exist`); continue; }
    const r = spawnSync(process.execPath, [path.join(root, file), ...rest], { cwd: root, encoding: 'utf8', timeout });
    const stderr = (r.stderr ?? '').trim();
    if (r.error?.code === 'ETIMEDOUT') add(broken, s.id, `${check} timed out after ${timeout} ms`);
    else if (r.error) add(broken, s.id, `${check} could not run: ${r.error.message}`);
    else if (r.status === 0) coverage.get(s.id)?.unshift(`${check} (passes)`);
    else if (r.status === 1 && !stderr) add(pending, s.id, `${check} exits 1`);
    else if (r.status === null) add(broken, s.id, `${check} killed by ${r.signal}`);
    else add(broken, s.id, `${check} exits ${r.status}${stderr ? ` with stderr: ${excerpt(stderr)}` : ''}`);
  }
}
for (const id of broken.keys()) pending.delete(id);
for (const [id, tests] of coverage) {
  if (broken.has(id)) console.log(`broken ${id}: ${broken.get(id).join('; ')}`);
  else if (pending.has(id)) console.log(`pending ${id}: ${pending.get(id).join('; ')}${tests.length ? `; tests: ${tests.join(', ')}` : ''}`);
  else console.log(tests.length ? `ok ${id}: ${tests.join(', ')}` : `uncovered ${id}`);
}
for (const line of problems) console.log(line);
const uncovered = [...coverage].filter(([id, tests]) => !tests.length && !pending.has(id) && !broken.has(id)).map(([id]) => id);
const ok = coverage.size - uncovered.length - pending.size - broken.size;
const list = (name, map) => (map.size ? `; ${name} ${map.size} (${[...map.keys()].join(', ')})` : '');
console.log(`covered ${ok}/${coverage.size}${list('pending', pending)}${list('broken', broken)}`);
process.exit(mode === 'enforce' && (uncovered.length || problems.length || broken.size) ? 1 : 0);
