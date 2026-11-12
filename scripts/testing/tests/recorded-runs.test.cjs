// covers: V1-A01, V1-A18, V1-A24
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const script = path.join(__dirname, '..', 'check-recorded-runs.cjs');

function repo() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'recorded-runs-'));
  const git = (...args) => spawnSync('git', ['-c', 'user.email=t@e.st', '-c', 'user.name=t', '-C', root, ...args], { encoding: 'utf8' });
  git('init', '-q');
  git('commit', '-q', '--allow-empty', '-m', 'base');
  const commit = git('rev-parse', 'HEAD').stdout.trim();
  const dir = path.join(root, 'docs/testing/evidence/runs');
  fs.mkdirSync(dir, { recursive: true });
  const record = (name, fields) => {
    const r = { id: 'V1-A01', os: 'windows-11', path: 'build', commit, docker_version: '29.0.1', started_at: '2026-11-20T10:00:00Z',
      elapsed_seconds: 640, result: 'pass', evidence: [`${name}.png`], ...fields };
    for (const file of r.evidence) fs.writeFileSync(path.join(dir, file), 'x');
    fs.writeFileSync(path.join(dir, `${name}.json`), JSON.stringify(r));
    return r;
  };
  return { root, dir, record, commit };
}
const run = (root, ...ids) => spawnSync(process.execPath, [script, '--root', root, ...ids], { encoding: 'utf8' });

function complete(record) {
  for (const os of ['windows-11', 'ubuntu-24.04']) {
    record(`a01-${os}`, { id: 'V1-A01', os });
    record(`a18-${os}`, { id: 'V1-A18', os, evidence: [`a18-${os}-notes.md`] });
    record(`a24-${os}`, { id: 'V1-A24', os, path: 'pull' });
  }
}

test('with no recorded runs the check fails and names each missing run', () => {
  const { root } = repo();
  const result = run(root);
  assert.equal(result.status, 1);
  for (const want of ['V1-A01 windows-11', 'V1-A01 ubuntu-24.04', 'V1-A18 windows-11', 'V1-A24 ubuntu-24.04 (pull)']) {
    assert.ok(result.stdout.includes(`missing ${want}\n`), want);
  }
});

test('a passing run per OS for A01 and A18, and a pull-path run per OS for A24, passes', () => {
  const { root, record } = repo();
  complete(record);
  const result = run(root);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /ok V1-A24 windows-11 \(pull\)/);
});

test('a failed run, a build-path A24 run or a missing evidence file does not count', () => {
  const { root, dir, record } = repo();
  complete(record);
  record('a01-ubuntu-24.04', { id: 'V1-A01', os: 'ubuntu-24.04', result: 'fail' });
  record('a24-windows-11', { id: 'V1-A24', os: 'windows-11', path: 'build' });
  fs.rmSync(path.join(dir, 'a18-windows-11-notes.md'));
  const result = run(root);
  assert.equal(result.status, 1);
  assert.match(result.stdout, /missing V1-A01 ubuntu-24\.04/);
  assert.match(result.stdout, /missing V1-A24 windows-11 \(pull\)/);
  assert.match(result.stdout, /a18-windows-11\.json: evidence a18-windows-11-notes\.md does not exist/);
});

test('a commit that is not in the repository, or a malformed record, is reported', () => {
  const { root, dir, record } = repo();
  complete(record);
  record('a01-windows-11', { id: 'V1-A01', os: 'windows-11', commit: 'f'.repeat(40) });
  fs.writeFileSync(path.join(dir, 'broken.json'), '{');
  const result = run(root, 'V1-A01');
  assert.equal(result.status, 1);
  assert.match(result.stdout, /a01-windows-11\.json: commit f{40} is not in this repository/);
  assert.match(result.stdout, /broken\.json: not JSON/);
});
