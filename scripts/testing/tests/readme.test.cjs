// covers: V1-A18, V1-A19
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..', '..', '..');
const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
const quickstart = readme.slice(0, readme.indexOf('\n## ', readme.indexOf('## Quickstart') + 1));

test('the quickstart covers the V1-SPEC §9 steps for a stranger', () => {
  for (const text of [
    'Windows 11', 'Docker Desktop', 'WSL 2', 'Ubuntu 24.04', 'Docker Engine', 'git clone', 'docker compose up --build',
    'Open http://127.0.0.1:3000 — username: local — password: see .pantrypulse/local-login.txt',
    'Sample data — fictional', '/import', 'docker compose down -v', 'PP_WEB_PORT', '8 GiB', 'docs/pantrypulse/HARDWARE.md',
  ]) assert.ok(quickstart.includes(text), `quickstart mentions ${text}`);
  assert.match(quickstart, /macOS[^.]*untested/);
  assert.match(quickstart, /down -v[^\n]*\n?[^\n]*(deletes|erases)/, 'start over carries a warning');
});

test('the README lists the W2-06 known limits', () => {
  for (const text of ['64 characters', 'abandoned imports', 'one worker', 'row count', 'retry backoff']) {
    assert.ok(readme.includes(text), `known limits mention ${text}`);
  }
});

test("the README's first-run time is HARDWARE.md's measurement", () => {
  const { minutes } = require('../../bench/run-all.cjs');
  const hardware = fs.readFileSync(path.join(root, 'docs/pantrypulse/HARDWARE.md'), 'utf8');
  const link = /\]\((\.\.\/testing\/evidence\/bench-[^)]+\.json)\)/.exec(hardware)[1];
  const a = JSON.parse(fs.readFileSync(path.join(root, 'docs/pantrypulse', link), 'utf8'));
  assert.ok(quickstart.includes(minutes(a.build.seconds)), `quickstart states the measured build time ${minutes(a.build.seconds)}`);
  assert.ok(quickstart.includes(minutes(a.start.seconds)), `quickstart states the measured first start ${minutes(a.start.seconds)}`);
});

test('research and impact wording stays within research-claims-check', () => {
  for (const banned of [/exact reproduction/i, /the paper's model/i, /reduces poverty/i, /saves \d+ meals/i, /fairer distribution/i,
    /AI approves/i, /auto-?orders?/i, /implements EGP-PI(?!-inspired)/i]) assert.doesNotMatch(readme, banned);
  assert.match(readme, /10\.1111\/itor\.70252/);
  assert.match(readme, /EGP-PI-inspired/);
  assert.match(readme, /simulated/i);
});
