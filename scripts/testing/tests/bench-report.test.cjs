// covers: V1-A09, V1-A17, V1-A19
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.join(__dirname, '..', '..', '..');
const hardware = path.join(root, 'docs/pantrypulse/HARDWARE.md');

function measured() {
  const text = fs.readFileSync(hardware, 'utf8');
  const block = /<!-- bench:begin -->\n([\s\S]*?)<!-- bench:end -->/.exec(text);
  assert.ok(block, 'HARDWARE.md has the generated measurement block');
  const link = /\]\((\.\.\/testing\/evidence\/bench-[^)]+\.json)\)/.exec(block[1]);
  assert.ok(link, 'the block links its JSON artifact');
  const artifact = JSON.parse(fs.readFileSync(path.join(path.dirname(hardware), link[1]), 'utf8'));
  return { block: block[1], link: link[1], artifact };
}

test('HARDWARE.md states each required measurement, and every number is the artifact\'s own', () => {
  const { renderTable } = require('../../bench/run-all.cjs');
  const { block, link, artifact } = measured();
  assert.equal(block, renderTable(artifact, link));
  const number = (v, name) => assert.ok(Number.isFinite(v) && v > 0, `${name} is measured`);
  number(artifact.build.seconds, 'first-run build time');
  number(artifact.idle.memory_mib, 'idle RAM');
  for (const [name, phase] of [['forecast', artifact.forecast], ['pantry comparison', artifact.comparison.pantry],
    ['retail comparison', artifact.comparison.retail], ['import', artifact.import]]) {
    number(phase.peak_rss_mib, `${name} peak RAM`);
    number(phase.cpu_avg_cores, `${name} CPU`);
    number(phase.wall_s, `${name} time`);
  }
  number(artifact.import.report.seconds.total, 'A09 import time');
  // A09 is the bench's own maximum: 4,500,000 demand rows before w5-data D02, 4,455,000 after it
  // (hubs carry no demand history, CR-w5-data-1).
  const { generated, loaded } = artifact.import.report;
  assert.equal(loaded.net_demand_history, generated.demand_history, 'every generated demand row loaded');
  assert.ok(loaded.net_demand_history >= 4_455_000, 'A09 is the maximum envelope');
  assert.equal(loaded.net_batches, generated.batches, 'every generated batch loaded');
});

test('every measurement is tied to a real commit and a timestamp', () => {
  const { artifact } = measured();
  assert.match(artifact.commit, /^[0-9a-f]{40}$/);
  const found = spawnSync('git', ['cat-file', '-e', `${artifact.commit}^{commit}`], { cwd: root });
  assert.equal(found.status, 0, `${artifact.commit} is a commit in this repository`);
  for (const phase of ['build', 'start', 'idle', 'import', 'forecast']) {
    assert.ok(!Number.isNaN(Date.parse(artifact[phase].started_at)), `${phase} has a timestamp`);
  }
  for (const mode of ['pantry', 'retail']) assert.ok(!Number.isNaN(Date.parse(artifact.comparison[mode].started_at)));
});
