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

test('the requirements and ceiling margin are generated from the artifact too', () => {
  const { renderSummary } = require('../../bench/run-all.cjs');
  const { artifact } = measured();
  const text = fs.readFileSync(hardware, 'utf8');
  const summary = /<!-- summary:begin -->\n([\s\S]*?)<!-- summary:end -->/.exec(text);
  assert.ok(summary, 'HARDWARE.md has the generated summary block');
  assert.equal(summary[1], renderSummary(artifact));
});

test("the CPU requirement is the worker's CPU limit in compose.yaml", () => {
  // Docker refuses to start a container whose CPU limit is above the CPUs it has
  // ("range of CPUs is from 0.01 to 16.00, as there are only 16 CPUs available").
  const { renderSummary } = require('../../bench/run-all.cjs');
  const limits = [...fs.readFileSync(path.join(root, 'compose.yaml'), 'utf8').matchAll(/^\s+cpus:\s*['"]?([\d.]+)/gm)].map((m) => m[1]);
  assert.equal(limits.length, 1, 'compose.yaml sets one CPU limit, on the worker');
  const row = renderSummary(measured().artifact).split('\n').find((l) => l.startsWith('| CPU |'));
  assert.ok(row.includes(`**${limits[0]} CPUs available to Docker**`), row);
  assert.doesNotMatch(row, /\*\*4 cores/, "the requirement is not V1-SPEC's provisional 4 cores");
});

test("the memory row states the worker's compose.yaml ceiling and that the other containers share Docker's memory", () => {
  const { renderSummary } = require('../../bench/run-all.cjs');
  const { artifact } = measured();
  const limits = [...fs.readFileSync(path.join(root, 'compose.yaml'), 'utf8').matchAll(/^\s+mem_limit:\s*['"]?(\S+?)['"]?$/gm)].map((m) => m[1]);
  assert.equal(limits.length, 1, 'compose.yaml sets one memory limit, on the worker');
  const others = Object.entries(artifact.idle.per_container_peak_mib).filter(([c]) => !/-worker-\d+$/.test(c)).reduce((s, [, v]) => s + v, 0);
  const row = renderSummary(artifact).split('\n').find((l) => l.startsWith('| Memory |'));
  assert.ok(row.includes('**8 GiB available to Docker**'), row);
  assert.ok(row.includes(`(\`mem_limit: ${limits[0]}\`)`), row);
  assert.ok(row.includes(`about ${others} MiB idle`), row);
  assert.doesNotMatch(row, /lets the worker reach its/, 'with exactly 8 GiB, the other containers take part of it');
});

test('no bench artifact records an absolute path', () => {
  const dir = path.join(root, 'docs/testing/evidence');
  for (const f of fs.readdirSync(dir).filter((n) => /^bench-.*\.json$/.test(n))) {
    const a = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
    for (const phase of [a.import, a.forecast, a.comparison?.pantry, a.comparison?.retail]) {
      for (const token of phase?.command?.split(' ') ?? []) assert.ok(!path.isAbsolute(token), `${f}: ${token}`);
    }
    assert.doesNotMatch(fs.readFileSync(path.join(dir, f), 'utf8'), /\/home\/|\/Users\/|[A-Za-z]:\\\\/, f);
  }
});

test('relativeCommands rewrites absolute paths inside the repository relative to apps/api, where the benches run', () => {
  const { relativeCommands } = require('../../bench/run-all.cjs');
  const out = path.join(root, 'artifacts/bench/import.json');
  const a = { import: { command: `taskset -c 0-5 uv run --frozen python scripts/bench_import.py --out ${out}` },
    forecast: { command: 'taskset -c 0-5 uv run --frozen python scripts/bench_forecast.py --part lock' },
    comparison: { pantry: { command: `x --out ${path.join(root, 'artifacts/bench/or-pantry.json')}` }, retail: { command: 'y' } } };
  relativeCommands(a);
  assert.equal(a.import.command, 'taskset -c 0-5 uv run --frozen python scripts/bench_import.py --out ../../artifacts/bench/import.json');
  assert.equal(a.forecast.command, 'taskset -c 0-5 uv run --frozen python scripts/bench_forecast.py --part lock');
  assert.equal(a.comparison.pantry.command, 'x --out ../../artifacts/bench/or-pantry.json');
});

test('outside the generated blocks, HARDWARE.md states no measured figure, only V1-SPEC figures', () => {
  const text = fs.readFileSync(hardware, 'utf8')
    .replace(/<!-- (summary|bench):begin -->[\s\S]*?<!-- \1:end -->/g, '');
  const SPEC = new Set(['8 GiB', '15 GB', '16 GB', '10 GB', '690 s', '330 s', '300 s', '6 CPUs']);
  const figures = [...text.matchAll(/\d[\d,.]*\s?(?:min\b|s\b|MiB|GiB|GB|cores?\b|CPUs?\b|rows\b|%)/g)].map((m) => m[0]);
  assert.deepEqual(figures.filter((f) => !SPEC.has(f)), []);
  assert.doesNotMatch(text, /load (average )?(was |near |of |up to )?\d/i);
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

test('every timed phase records the host load average at its start and end', () => {
  // The reference machine is shared, so a reader needs the load to judge each timing.
  const { artifact } = measured();
  const phases = { build: artifact.build, start: artifact.start, idle: artifact.idle, import: artifact.import,
    forecast: artifact.forecast, pantry: artifact.comparison.pantry, retail: artifact.comparison.retail };
  for (const [name, phase] of Object.entries(phases)) {
    for (const end of ['start', 'end']) {
      const l = phase.load?.[end];
      assert.ok(Array.isArray(l) && l.length === 3 && l.every((v) => Number.isFinite(v) && v >= 0), `${name} load.${end} is [1, 5, 15 min]`);
    }
  }
});

test('durations round before they split into minutes and seconds', () => {
  const { minutes } = require('../../bench/run-all.cjs');
  assert.equal(minutes(59.4), '59 s');
  assert.equal(minutes(59.6), '1 min 00 s');
  assert.equal(minutes(119.6), '2 min 00 s');
  assert.equal(minutes(179.5), '3 min 00 s');
  assert.equal(minutes(204.6), '3 min 25 s');
});
