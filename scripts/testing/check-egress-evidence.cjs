#!/usr/bin/env node
// Evidence check for V1-A03 (no outbound calls but Census) and V1-A04 (secrets never leak): the
// latest docs/testing/evidence/egress-*.json, written by scripts/testing/egress-journey.cjs, must be
// a clean, complete run for the stack as it is now. Exits 1 (the story stays pending) when the
// report is missing, failed, blind, partial, or older than the last change to what the stack is
// built from (STACK).
// Usage: node scripts/testing/check-egress-evidence.cjs [--root <dir>]
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const REQUIRED_SECRETS = ['password', 'proxy_token', 'presenter_password_hash', 'google_key'];
// What the images are built from: compose.yaml; the api context apps/api; the web context is the
// repository root, and apps/web/Dockerfile copies package.json, package-lock.json, packages/contracts
// and apps/web, filtered by the root .dockerignore.
const STACK = ['apps', 'compose.yaml', 'package.json', 'package-lock.json', 'packages/contracts', '.dockerignore'];

function problems(report, root) {
  const out = [];
  if (report.pass !== true) out.push('the run did not pass');
  if (!report.journey?.length) out.push('the report lists no journey steps');
  else if (!report.journey.every((s) => s.ok)) out.push('a journey step failed');
  if (report.capture_saw_geocoding !== true) out.push('the capture never saw the Census connection (blind capture)');
  const violations = report.egress?.violations?.length ?? NaN;
  if (violations !== 0) out.push(`${Number.isNaN(violations) ? 'no' : violations} egress violation${violations === 1 ? '' : 's'}`);
  const missing = REQUIRED_SECRETS.filter((s) => !report.secrets?.checked?.includes(s));
  if (missing.length) out.push(`the run did not check ${missing.join(', ')}`);
  if (!report.secrets?.sources?.includes('API responses')) out.push('the run did not scan API responses');
  if (report.secrets?.findings?.length !== 0) out.push(`${report.secrets?.findings?.length ?? 'unknown'} secret findings`);
  const dirty = (report.dirty_paths ?? []).filter((p) => STACK.some((s) => p === s || p.startsWith(`${s}/`)));
  if (dirty.length) out.push(`the run had uncommitted stack sources: ${dirty.join(', ')}`);
  const git = (...args) => spawnSync('git', ['-C', root, ...args], { encoding: 'utf8' });
  if (!/^[0-9a-f]{40}$/.test(report.commit ?? '') || git('cat-file', '-e', `${report.commit}^{commit}`).status !== 0) {
    out.push(`commit ${report.commit} is not in this repository`);
  } else {
    const changed = git('diff', '--name-only', report.commit, 'HEAD', '--', ...STACK);
    const files = changed.stdout.split('\n').filter(Boolean);
    if (changed.status !== 0) out.push(`cannot compare ${report.commit.slice(0, 7)} with HEAD: ${changed.stderr.trim()}`);
    else if (files.length) {
      out.push(`${files.length} stack sources changed since ${report.commit.slice(0, 7)} (${files.slice(0, 5).join(', ')}${files.length > 5 ? ', …' : ''}): re-run the egress journey`);
    }
  }
  return out;
}

function main() {
  const args = process.argv.slice(2);
  const root = path.resolve(args.includes('--root') ? args[args.indexOf('--root') + 1] : path.join(__dirname, '..', '..'));
  const dir = path.join(root, 'docs/testing/evidence');
  const reports = fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => /^egress-.*\.json$/.test(f)).sort() : [];
  if (!reports.length) {
    console.log('missing: no docs/testing/evidence/egress-*.json');
    process.exitCode = 1;
    return;
  }
  const name = reports.at(-1);
  let found;
  try { found = problems(JSON.parse(fs.readFileSync(path.join(dir, name), 'utf8')), root); } catch (e) { found = [`not JSON: ${e.message}`]; }
  console.log(found.length ? `pending ${name}: ${found.join('; ')}` : `ok ${name}`);
  process.exitCode = found.length ? 1 : 0;
}

if (require.main === module) main();
module.exports = { problems, REQUIRED_SECRETS };
