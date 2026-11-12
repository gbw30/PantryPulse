#!/usr/bin/env node
// Recorded-evidence check for the acceptance criteria only a person can run (V1-A01 clean install,
// V1-A18 README walkthrough, V1-A24 pull path). Each run is a JSON record in
// docs/testing/evidence/runs/ (format: docs/testing/README.md) whose evidence files exist and whose
// commit is in this repository. Exits 1 until every required run has a passing record.
// Usage: node scripts/testing/check-recorded-runs.cjs [--root <dir>] [V1-A01 V1-A18 V1-A24]
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const OSES = ['windows-11', 'ubuntu-24.04'];
// Each ID needs a passing run on each OS, on this install path ("any" = build or pull).
const REQUIRED = { 'V1-A01': 'any', 'V1-A18': 'any', 'V1-A24': 'pull' };

function validate(record, file, root) {
  const errors = [];
  if (!(record.id in REQUIRED)) errors.push(`unknown id ${record.id}`);
  if (!OSES.includes(record.os)) errors.push(`os must be one of ${OSES.join(', ')}`);
  if (!['build', 'pull'].includes(record.path)) errors.push('path must be build or pull');
  if (!['pass', 'fail'].includes(record.result)) errors.push('result must be pass or fail');
  if (!/^[0-9a-f]{40}$/.test(record.commit ?? '') ||
      spawnSync('git', ['-C', root, 'cat-file', '-e', `${record.commit}^{commit}`]).status !== 0) {
    errors.push(`commit ${record.commit} is not in this repository`);
  }
  if (Number.isNaN(Date.parse(record.started_at))) errors.push('started_at is not a timestamp');
  if (!(record.elapsed_seconds > 0)) errors.push('elapsed_seconds must be positive');
  if (!record.docker_version) errors.push('docker_version is missing');
  if (!record.evidence?.length) errors.push('evidence lists no file');
  for (const e of record.evidence ?? []) {
    if (!fs.existsSync(path.join(path.dirname(file), e))) errors.push(`evidence ${e} does not exist`);
  }
  return errors;
}

function main() {
  const args = process.argv.slice(2);
  const at = args.indexOf('--root');
  const root = path.resolve(at >= 0 ? args.splice(at, 2)[1] : path.join(__dirname, '..', '..'));
  const ids = args.length ? args : Object.keys(REQUIRED);
  const dir = path.join(root, 'docs/testing/evidence/runs');
  const valid = [];
  let failed = false;
  for (const name of fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => f.endsWith('.json')).sort() : []) {
    const file = path.join(dir, name);
    let record;
    try { record = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { console.log(`invalid ${name}: not JSON`); failed = true; continue; }
    const errors = validate(record, file, root);
    for (const e of errors) console.log(`invalid ${name}: ${e}`);
    if (errors.length) failed = true; else valid.push(record);
  }
  for (const id of ids) {
    for (const os of OSES) {
      const want = `${id} ${os}${REQUIRED[id] === 'any' ? '' : ` (${REQUIRED[id]})`}`;
      const ok = valid.some((r) => r.id === id && r.os === os && r.result === 'pass' && (REQUIRED[id] === 'any' || r.path === REQUIRED[id]));
      console.log(`${ok ? 'ok' : 'missing'} ${want}`);
      if (!ok) failed = true;
    }
  }
  process.exitCode = failed ? 1 : 0;
}

main();
