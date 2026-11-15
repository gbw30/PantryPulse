// covers: V1-A21
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const script = path.join(__dirname, '..', 'check-egress-evidence.cjs');
const git = (root, ...args) => {
  const r = spawnSync('git', ['-C', root, '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', ...args], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  return r.stdout.trim();
};

/** A repository whose last commit is the egress run's, with a clean report for it. */
function repo(change = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'egress-evidence-'));
  git(root, 'init', '-q');
  fs.mkdirSync(path.join(root, 'apps/api'), { recursive: true });
  fs.writeFileSync(path.join(root, 'apps/api/main.py'), 'x = 1\n');
  fs.writeFileSync(path.join(root, 'compose.yaml'), 'services: {}\n');
  // The web image's build inputs outside apps/ (apps/web/Dockerfile, built from the repository root).
  fs.writeFileSync(path.join(root, 'package.json'), '{}\n');
  fs.writeFileSync(path.join(root, 'package-lock.json'), '{}\n');
  fs.writeFileSync(path.join(root, '.dockerignore'), 'node_modules\n');
  fs.mkdirSync(path.join(root, 'packages/contracts'), { recursive: true });
  fs.writeFileSync(path.join(root, 'packages/contracts/index.ts'), 'export {};\n');
  fs.writeFileSync(path.join(root, 'README.md'), '# docs\n');
  git(root, 'add', '-A');
  git(root, 'commit', '-q', '-m', 'run');
  const report = {
    commit: git(root, 'rev-parse', 'HEAD'), dirty_paths: [], pass: true, capture_saw_geocoding: true,
    journey: [{ step: 'sign in as local', ok: true }],
    egress: { destinations: [{ destination: 'geocoding.geo.census.gov:443', allowed: true }], violations: [] },
    secrets: { checked: ['password', 'proxy_token', 'presenter_password_hash', 'google_key'],
      sources: ['compose logs', '.next output', 'API responses', 'git working tree', 'git history since the run started'], findings: [] },
    ...change,
  };
  fs.mkdirSync(path.join(root, 'docs/testing/evidence'), { recursive: true });
  fs.writeFileSync(path.join(root, 'docs/testing/evidence/egress-2026-11-15.json'), JSON.stringify(report));
  return root;
}
const run = (root) => spawnSync(process.execPath, [script, '--root', root], { encoding: 'utf8' });

test('a clean report for the current stack sources passes', () => {
  const result = run(repo());
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /^ok egress-2026-11-15\.json/m);
});

test('a report is stale once anything the stack is built from changes after its commit', () => {
  const root = repo();
  fs.writeFileSync(path.join(root, 'apps/api/main.py'), 'x = 2\n');
  git(root, 'commit', '-q', '-am', 'later code');
  const result = run(root);
  assert.equal(result.status, 1);
  assert.match(result.stdout, /stack sources changed since [0-9a-f]{7} \(apps\/api\/main\.py\)/);
});

test("the web image's build inputs outside apps/ make the report stale too", () => {
  for (const file of ['package.json', 'package-lock.json', 'packages/contracts/index.ts', '.dockerignore']) {
    const root = repo();
    fs.appendFileSync(path.join(root, file), '\n');
    git(root, 'commit', '-q', '-am', `later ${file}`);
    const result = run(root);
    assert.equal(result.status, 1, file);
    assert.match(result.stdout, new RegExp(`stack sources changed since [0-9a-f]{7} \\(${file.replace(/[.]/g, '\\.')}\\)`), file);
  }
});

test('a change outside the stack sources leaves the report current', () => {
  const root = repo();
  fs.appendFileSync(path.join(root, 'README.md'), 'more\n');
  git(root, 'commit', '-q', '-am', 'docs');
  assert.equal(run(root).status, 0);
});

test('a failed, partial or blind report never passes', () => {
  for (const [change, reason] of [
    [{ pass: false }, /did not pass/],
    [{ capture_saw_geocoding: false }, /never saw the Census connection/],
    [{ egress: { destinations: [], violations: [{ destination: 'x:443', reason: 'not in the allowlist' }] } }, /1 egress violation/],
    [{ secrets: { checked: ['password', 'proxy_token'], sources: ['compose logs'], findings: [] } }, /did not check presenter_password_hash, google_key/],
    [{ secrets: { checked: ['password', 'proxy_token', 'presenter_password_hash', 'google_key'], sources: ['compose logs'], findings: [] } }, /did not scan API responses/],
    [{ journey: [] }, /no journey steps/],
    [{ dirty_paths: ['apps/web/x.ts'] }, /uncommitted stack sources/],
    [{ dirty_paths: ['package-lock.json'] }, /uncommitted stack sources: package-lock\.json/],
    [{ dirty_paths: ['packages/contracts/index.ts'] }, /uncommitted stack sources: packages\/contracts\/index\.ts/],
  ]) {
    const result = run(repo(change));
    assert.equal(result.status, 1, JSON.stringify(change));
    assert.match(result.stdout, reason);
  }
});

test('no report at all is missing, never ok', () => {
  const root = repo();
  fs.rmSync(path.join(root, 'docs/testing/evidence/egress-2026-11-15.json'));
  const result = run(root);
  assert.equal(result.status, 1);
  assert.match(result.stdout, /missing: no docs\/testing\/evidence\/egress-\*\.json/);
});
