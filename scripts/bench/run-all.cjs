#!/usr/bin/env node
// Hardware measurements for HARDWARE.md and the README (V1-A09, A17, A19). One run, on the machine
// the numbers describe:
//   1. `docker compose build --no-cache` and the first `docker compose up --wait` of the lane's stack;
//   2. the idle stack's RAM and CPU (`docker stats`, 30 s after 60 s idle) and its disk use;
//   3. the maximum-envelope benches, each pinned to 6 CPUs (the worker's cap) with peak RSS and CPU
//      time from getrusage: apps/api/scripts/bench_import.py (A09, 100 × 500 × 90 days),
//      bench_forecast.py --part lock (A17, 50,000 series) and scripts/or/bench_v1.py per mode
//      (A17, 100 × 500, every method). They run natively against PP_TEST_DATABASE_URL because
//      bench_v1.py needs git, which the API image doesn't have; the code is the worker's own.
// Writes docs/testing/evidence/bench-<date>.json, then regenerates the measurement block of
// docs/pantrypulse/HARDWARE.md from it (the summary and bench blocks). Usage, with .env.lane loaded:
// node scripts/bench/run-all.cjs, or `node scripts/bench/run-all.cjs --render <artifact.json>` to
// regenerate HARDWARE.md from an existing artifact without measuring.
// It runs `docker compose down -v` on COMPOSE_PROJECT_NAME, so it refuses the default project.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { laneImages } = require('../testing/egress-journey.cjs');

const root = path.resolve(__dirname, '../..');
const api = path.join(root, 'apps/api');
const hardware = path.join(root, 'docs/pantrypulse/HARDWARE.md');
const MiB = 1024 * 1024;
const FORECAST_CEILING_S = 300; // the forecast job's ceiling (CLAUDE.md: forecast 270/300 s)

function minutes(seconds) {
  const s = Math.round(seconds); // round first, so 119.6 is 2 min 00 s, never 1 min 60 s
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s`;
}
const gib = (mib) => `${(mib / 1024).toFixed(1)} GiB`;
const when = (iso) => iso.replace(/\.\d+Z$/, 'Z');
// Host load average [1, 5, 15 min]: the reference machine is shared, so each timing carries it.
const loadavg = () => os.loadavg().map((v) => Math.round(v * 10) / 10);

/** The measurement block of HARDWARE.md, generated from the artifact alone. */
function renderTable(a, link) {
  const m = a.machine;
  const bench = (p) => `${minutes(p.wall_s)}; peak RAM ${p.peak_rss_mib} MiB; CPU ${p.cpu_avg_cores.toFixed(1)} cores on average`;
  const verified = (c) => {
    const checked = c.report.methods.filter((x) => x.union_check);
    return `${c.report.methods.filter((x) => x.verified).length}/${c.report.methods.length} method results verified; ` +
      `union check passed on ${checked.filter((x) => x.union_check.passed).length}/${checked.length}`;
  };
  const rows = [
    ['First-run build, `docker compose build --no-cache` (base images already downloaded)', minutes(a.build.seconds), a.build.started_at, a.build.load],
    ['First start, `docker compose up --wait` (migrate, seed, web ready)', minutes(a.start.seconds), a.start.started_at, a.start.load],
    ['Idle stack, all services', `RAM ${a.idle.memory_mib} MiB (peak ${a.idle.memory_peak_mib} MiB); CPU ${a.idle.cpu_percent}% of one core`, a.idle.started_at, a.idle.load],
    ['Disk after first start', `images ${gib(a.disk.images_mib)}; database ${a.disk.database_mib} MiB`, a.disk.measured_at, null],
    [`A09 import, ${a.import.report.generated.locations} × ${a.import.report.generated.products} × 90 days (${a.import.report.loaded.net_demand_history.toLocaleString('en-US')} demand rows, ${a.import.report.loaded.net_batches.toLocaleString('en-US')} batches)`,
      `job steps ${minutes(a.import.report.seconds.total)} (validate ${minutes(a.import.report.seconds.step)}, prepare ${minutes(a.import.report.seconds.prepare)}, publish ${minutes(a.import.report.seconds.publish)}); run ${bench(a.import)}`, a.import.started_at, a.import.load],
    [`A17 forecast, ${a.forecast.report.series.toLocaleString('en-US')} series × ${a.forecast.report.days ?? 90} days, through the queue and publisher`, bench(a.forecast), a.forecast.started_at, a.forecast.load],
    ...['pantry', 'retail'].map((mode) => {
      const c = a.comparison[mode];
      const walls = Object.entries(c.report.comparison_wall_s).map(([k, v]) => `${k.toLowerCase()} ${minutes(v)}`).join(', ');
      return [`A17 ${mode === 'pantry' ? 'Pantry' : 'Retail'} comparison, ${c.report.size.locations} × ${c.report.size.products}, every method (${walls})`,
        `${bench(c)}; ${verified(c)}`, c.started_at, c.load];
    }),
  ];
  return [
    `Measured on ${m.cpu}, ${m.cpus} logical CPUs, ${gib(m.ram_mib)} RAM, ${m.os}; Docker ${m.docker_version} with ${m.docker_cpus} CPUs and ${gib(m.docker_memory_mib)} for Docker. ` +
      `Commit \`${a.commit.slice(0, 7)}\`${a.dirty_paths.length ? ` plus ${a.dirty_paths.length} uncommitted paths, ${a.dirty_paths.some((p) => p.startsWith('apps/')) ? 'some under `apps/`' : 'none under `apps/`'} (listed in the artifact)` : ''}. Artifact: [${path.basename(link)}](${link}). Host load is the machine's 1-minute load average, across its ${m.cpus} logical CPUs (the artifact also has the 5- and 15-minute averages).`,
    '',
    '| Measure | Result | Started (UTC) | Host load, 1 min (start → end) |',
    '|---|---|---|---|',
    ...rows.map(([measure, result, at, load]) => `| ${measure} | ${result} | ${when(at)} | ${load ? `${load.start[0]} → ${load.end[0]}` : '—'} |`),
    '',
    optimizers(a),
    '',
    `- **Host load:** the 1-minute load average was at most ${peakLoad([a.build, a.start, a.idle])} during the build, first start and idle sampling, and at most ${peakLoad(benches(a))} during the benches.`,
    `- **Bench versions** (the commit that last changed each): ${Object.entries(a.bench_versions ?? {}).map(([f, c]) => `\`${path.basename(f)}\` \`${c.slice(0, 7)}\``).join(', ')}. The import bench generated ${a.import.report.generated.locations} locations × ${a.import.report.generated.products} products × 90 days.`,
    '',
  ].join('\n');
}

const benches = (a) => [a.import, a.forecast, a.comparison.pantry, a.comparison.retail];
const peakLoad = (phases) => Math.max(...phases.flatMap((p) => [p.load.start[0], p.load.end[0]]));
const cores = (n) => n.toFixed(1);

/** The optimizer outcome of both comparisons, counted from the artifact. */
function optimizers(a) {
  const all = ['pantry', 'retail'].flatMap((mode) => a.comparison[mode].report.methods.map((m) => ({ mode, ...m })));
  const solved = all.filter((m) => m.native_status);
  const counts = solved.map((m) => m.product_status_counts);
  const allOptimal = counts.every((c) => Object.keys(c).every((k) => k === 'OPTIMAL' || k === 'not at risk; not optimized'));
  const checked = all.filter((m) => m.union_check);
  const products = a.comparison.pantry.report.size.products;
  const atRisk = [...new Set(counts.map((c) => c.OPTIMAL ?? 0))];
  return `${allOptimal ? 'All optimizer products ended `OPTIMAL`' : 'Not every optimizer product ended `OPTIMAL` (see the artifact)'}. ` +
    `${all.every((m) => m.verified) ? 'Every method result, baselines included, was verified' : 'Not every method result was verified'}, and the per-product union check passed on ` +
    `${checked.filter((m) => m.union_check.passed).length} of ${checked.length} results across the Pantry units run and the Retail units and USD runs. ` +
    (atRisk.length === 1
      ? `In each optimizer run, ${atRisk[0]} of the ${products} products were at risk and optimized; the other ${products - atRisk[0]} are "not at risk; not optimized" by design (decisions/W0-optimizer-decomposition.md).`
      : `The number of products at risk and optimized differs by run (${atRisk.join(', ')} of ${products}); see the artifact.`);
}

/** The worker's `cpus:` or `mem_limit:` in compose.yaml (the only service that sets either). Docker needs at least
 * that many CPUs to start it. */
function workerLimit(key) {
  const limits = [...fs.readFileSync(path.join(root, 'compose.yaml'), 'utf8').matchAll(new RegExp(`^\\s+${key}:\\s*['"]?(\\S+?)['"]?$`, 'gm'))].map((m) => m[1]);
  if (limits.length !== 1) throw new Error(`expected one ${key}: in compose.yaml, found ${limits.length}`);
  return limits[0];
}

/** Rewrites absolute paths inside the repository in each bench command relative to apps/api, where the benches run. */
function relativeCommands(a) {
  for (const phase of [a.import, a.forecast, a.comparison?.pantry, a.comparison?.retail]) {
    if (phase?.command) phase.command = phase.command.split(' ').map((t) => (t.startsWith(`${root}${path.sep}`) ? path.relative(api, t) : t)).join(' ');
  }
  return a;
}

/** The Requirements table and the ceiling margin of HARDWARE.md, generated from the artifact alone. */
function renderSummary(a) {
  const m = a.machine;
  const steps = benches(a);
  const named = { import: a.import, forecast: a.forecast, 'Pantry comparison': a.comparison.pantry, 'Retail comparison': a.comparison.retail };
  const [largest, peak] = Object.entries(named).reduce((x, y) => (y[1].peak_rss_mib > x[1].peak_rss_mib ? y : x));
  const [lo, hi] = (/taskset -c (\d+)-(\d+)/.exec(a.import.command) ?? []).slice(1).map(Number);
  const cpus = workerLimit('cpus');
  const memLimit = workerLimit('mem_limit');
  const others = Object.entries(a.idle.per_container_peak_mib).filter(([c]) => !/-worker-\d+$/.test(c)).reduce((s, [, v]) => s + v, 0);
  const label = (image) => (/-api[:@]/.test(image) ? 'API' : /-web[:@]/.test(image) ? 'web' : /postgres/.test(image) ? 'PostgreSQL' : image);
  const comparisons = ['pantry', 'retail'].flatMap((mode) => Object.entries(a.comparison[mode].report.comparison_wall_s)
    .map(([measure, s]) => ({ mode, measure, s, ceilings: a.comparison[mode].report.ceilings_s })));
  const slowest = comparisons.reduce((x, y) => (y.s > x.s ? y : x));
  const size = a.comparison[slowest.mode].report.size;
  return [
    '| Resource | Requirement | From the measurements |',
    '|---|---|---|',
    `| CPU | **${cpus} CPUs available to Docker**: compose.yaml limits the worker to ${cpus} CPUs (\`cpus: ${cpus}\`), and Docker does not start a container whose limit is above the CPUs it has. V1-SPEC's provisional figure is 4 cores; a lower limit is not offered yet | Docker had ${m.docker_cpus} CPUs, and the benches ran under \`taskset\` on ${hi - lo + 1}. Idle, the stack's containers used ${cores(a.idle.cpu_percent / 100)} of a core in total. Each bench process averaged ${cores(Math.min(...steps.map((p) => p.cpu_avg_cores)))}–${cores(Math.max(...steps.map((p) => p.cpu_avg_cores)))} cores; PostgreSQL's CPU during the benches is not included. Single-core speed sets how long a comparison takes (see the ceiling margin below). |`,
    `| Memory | **8 GiB available to Docker**: V1-SPEC's provisional figure; what was measured fits well within it | Idle, the stack's containers peaked at ${a.idle.memory_peak_mib} MiB together. The largest bench process (the ${largest}) peaked at ${peak.peak_rss_mib.toLocaleString('en-US')} MiB, its largest child process's RSS. PostgreSQL's memory during the benches is not included, so these two are not a measured total. The worker's own ceiling, from V1-SPEC §9, is 8 GiB (\`mem_limit: ${memLimit}\`). With exactly 8 GiB for Docker, the other containers (about ${others} MiB idle) share it, so the worker can't reach its full ceiling; the measured peaks stay far below it. Less memory may work but is untested. The 16 GB machine recommendation is not measured. |`,
    `| Disk | **About 15 GB free**: provisional, only partly measured | Images ${gib(a.disk.images_mib)} (${Object.entries(a.disk.images).map(([i, mib]) => `${label(i)} ${mib.toLocaleString('en-US')} MiB`).join(', ')}) and a ${a.disk.database_mib} MiB database after the first start. Not measured: Docker's build cache, the database after a maximum-size import, and the Chronos profile's provisional +10 GB. |`,
    `| Time | First run: build ${minutes(a.build.seconds)}, then first start ${minutes(a.start.seconds)} | Base images were already on the machine, so a clean machine adds their download. The build has no cache mounts, so \`--no-cache\` downloads every npm and Python package again; it depends on load and connection speed (the host's 1-minute load went from ${a.build.load.start[0]} to ${a.build.load.end[0]} during the build). |`,
    '',
    `**Ceiling margin.** At ${size.locations} × ${size.products}, the slowest comparison was ${slowest.mode === 'pantry' ? 'Pantry' : 'Retail'} in ${slowest.measure.toLowerCase()}: every method together took ${minutes(slowest.s)} of the ${slowest.ceilings.comparison} s comparison ceiling${slowest.s < slowest.ceilings.method ? `, so each method stayed under the ${slowest.ceilings.method} s per-method ceiling` : ''}, on this laptop's CPU. Each bench averages about one core, so a CPU with about half this one's single-core speed could approach the ceiling. That is unverified; it is the first thing to check on slower hardware. The forecast used ${minutes(a.forecast.wall_s)} of its ${FORECAST_CEILING_S} s ceiling, and the import's job steps took ${minutes(a.import.report.seconds.total)}.`,
    '',
  ].join('\n');
}

// ---- the run ---------------------------------------------------------------------------------

const sh = (cmd, args, opts = {}) => spawnSync(cmd, args, { cwd: root, encoding: 'utf8', maxBuffer: 1 << 30, windowsHide: true, ...opts });
function must(cmd, args, opts) {
  const r = sh(cmd, args, opts);
  if (r.status !== 0) throw new Error(`${cmd} ${args.slice(0, 5).join(' ')} failed: ${(r.stderr || r.error?.message || '').slice(-2000)}`);
  return r.stdout;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const now = () => new Date().toISOString();

function timed(fn) {
  const started_at = now();
  const start = loadavg();
  const t = process.hrtime.bigint();
  fn();
  return { started_at, seconds: Math.round(Number(process.hrtime.bigint() - t) / 1e8) / 10, load: { start, end: loadavg() } };
}

/** `docker stats` memory ("512.3MiB / 7.6GiB") in MiB. */
function mib(text) {
  const [, value, unit] = /([\d.]+)\s*([KMGT]?i?B)/.exec(text.split('/')[0]) ?? [];
  return Number(value) * ({ B: 1 / MiB, KiB: 1 / 1024, kB: 1 / 1024, MiB: 1, MB: 1, GiB: 1024, GB: 1024, TiB: 1024 * 1024 }[unit] ?? NaN);
}

async function sampleStats(containers, seconds) {
  const samples = [];
  const end = Date.now() + seconds * 1000;
  while (Date.now() < end) {
    const rows = must('docker', ['stats', '--no-stream', '--format', '{{json .}}', ...containers]).trim().split('\n').map((l) => JSON.parse(l));
    samples.push({ memory: rows.reduce((s, r) => s + mib(r.MemUsage), 0), cpu: rows.reduce((s, r) => s + parseFloat(r.CPUPerc), 0), rows });
    await sleep(1000);
  }
  const avg = (k) => samples.reduce((s, x) => s + x[k], 0) / samples.length;
  const perContainer = {};
  for (const s of samples) for (const r of s.rows) perContainer[r.Name] = Math.max(perContainer[r.Name] ?? 0, Math.round(mib(r.MemUsage)));
  return { samples: samples.length, memory_mib: Math.round(avg('memory')), memory_peak_mib: Math.round(Math.max(...samples.map((s) => s.memory))),
    cpu_percent: Math.round(avg('cpu')), per_container_peak_mib: perContainer };
}

// Runs a command under taskset (the worker's 6 CPUs) and reports its children's peak RSS and CPU time.
const RUSAGE = 'import json,resource,subprocess,sys,time\nt=time.perf_counter()\nc=subprocess.run(sys.argv[2:]).returncode\nr=resource.getrusage(resource.RUSAGE_CHILDREN)\n' +
  'json.dump({"returncode":c,"wall_s":time.perf_counter()-t,"cpu_s":r.ru_utime+r.ru_stime,"peak_rss_kib":r.ru_maxrss},open(sys.argv[1],"w"))';

function bench(name, args, scratch, env = {}) {
  console.log(`Running ${name}…`);
  const started_at = now();
  const start = loadavg();
  const usage = path.join(scratch, `${name}.rusage.json`);
  const stdout = path.join(scratch, `${name}.stdout`);
  const out = fs.openSync(stdout, 'w');
  const r = spawnSync(path.join(api, '.venv/bin/python'), ['-c', RUSAGE, usage, 'taskset', '-c', '0-5', 'uv', 'run', '--frozen', 'python', ...args],
    { cwd: api, stdio: ['ignore', out, 'inherit'], env: { ...process.env, ...env } });
  fs.closeSync(out);
  const load = { start, end: loadavg() };
  const u = JSON.parse(fs.readFileSync(usage, 'utf8'));
  if (r.status !== 0 || u.returncode !== 0) throw new Error(`${name} failed (exit ${u.returncode}); see ${stdout}`);
  return { started_at, command: ['taskset -c 0-5 uv run --frozen python', ...args].join(' '), wall_s: Math.round(u.wall_s * 10) / 10,
    cpu_s: Math.round(u.cpu_s), cpu_avg_cores: Math.round((u.cpu_s / u.wall_s) * 10) / 10, peak_rss_mib: Math.round(u.peak_rss_kib / 1024), load, stdout };
}

/** Rewrites HARDWARE.md's two generated blocks from artifact `a` (stored at `file`). */
function writeHardware(a, file) {
  const link = path.relative(path.dirname(hardware), file).split(path.sep).join('/');
  const block = (text, name, body) => {
    const re = new RegExp(`<!-- ${name}:begin -->\\n[\\s\\S]*?<!-- ${name}:end -->`);
    if (!re.test(text)) throw new Error(`HARDWARE.md has no ${name} block`);
    return text.replace(re, () => `<!-- ${name}:begin -->\n${body}<!-- ${name}:end -->`);
  };
  const text = fs.readFileSync(hardware, 'utf8');
  fs.writeFileSync(hardware, block(block(text, 'summary', renderSummary(a)), 'bench', renderTable(a, link)));
}

async function main() {
  const at = process.argv.indexOf('--render');
  if (at >= 0) { // regenerate HARDWARE.md from an existing artifact, without measuring
    const file = path.resolve(process.argv[at + 1]);
    const a = JSON.parse(fs.readFileSync(file, 'utf8'));
    const before = JSON.stringify(a);
    if (JSON.stringify(relativeCommands(a)) !== before) fs.writeFileSync(file, `${JSON.stringify(a, null, 2)}\n`);
    writeHardware(a, file);
    console.log(`Rewrote HARDWARE.md from ${path.relative(root, file)}.`);
    return;
  }
  const project = process.env.COMPOSE_PROJECT_NAME;
  const db = process.env.PP_TEST_DATABASE_URL ?? '';
  if (!project || project === 'pantrypulse' || !/_test(\?|$)/.test(db)) {
    console.error('Load .env.lane first: needs a disposable COMPOSE_PROJECT_NAME (this run starts with `docker compose down -v`) and a *_test PP_TEST_DATABASE_URL.');
    process.exit(2);
  }
  const scratch = path.join(root, 'artifacts/bench');
  fs.mkdirSync(scratch, { recursive: true });
  const app = ['compose', '-f', 'compose.yaml', '-f', laneImages(project, scratch)];
  const info = JSON.parse(must('docker', ['info', '--format', '{{json .}}']));
  const a = {
    schema: 'pantrypulse-bench-v1', recorded_at: now(),
    commit: must('git', ['rev-parse', 'HEAD']).trim(),
    dirty_paths: must('git', ['status', '--porcelain']).split('\n').filter(Boolean).map((l) => l.slice(3)),
    // The commit that last changed each bench, since a bench's size can change (e.g. w5-data D02).
    bench_versions: Object.fromEntries(['apps/api/scripts/bench_import.py', 'apps/api/scripts/bench_forecast.py', 'scripts/or/bench_v1.py']
      .map((f) => [f, must('git', ['log', '-1', '--format=%H', '--', f]).trim()])),
    machine: { cpu: /model name\s*:\s*(.+)/.exec(fs.readFileSync('/proc/cpuinfo', 'utf8'))?.[1] ?? os.cpus()[0].model, cpus: os.cpus().length,
      ram_mib: Math.round(os.totalmem() / MiB), os: `${info.OperatingSystem} (kernel ${info.KernelVersion})`,
      docker_version: info.ServerVersion, docker_cpus: info.NCPU, docker_memory_mib: Math.round(info.MemTotal / MiB) },
    note: 'Timings on synthetic, seeded data at the maximum envelope; never accuracy evidence.',
  };

  must('docker', [...app, 'down', '-v', '--remove-orphans']);
  console.log('Building with --no-cache…');
  a.build = timed(() => must('docker', [...app, 'build', '--no-cache']));
  console.log('First start…');
  a.start = timed(() => must('docker', [...app, 'up', '-d', '--wait', '--wait-timeout', '900']));
  const containers = must('docker', [...app, 'ps', '-q']).trim().split('\n');
  console.log('Idle: 60 s settle, then 30 s of samples…');
  await sleep(60_000);
  const idleStart = { started_at: now(), load: { start: loadavg() } };
  a.idle = { ...idleStart, ...(await sampleStats(containers, 30)) };
  a.idle.load.end = loadavg();
  const images = must('docker', [...app, 'config', '--images']).trim().split('\n');
  a.disk = { measured_at: now(), images: Object.fromEntries(images.map((i) => [i, Math.round(Number(must('docker', ['image', 'inspect', '-f', '{{.Size}}', i])) / MiB)])),
    database_mib: Math.round(Number(must('docker', [...app, 'exec', '-T', 'postgres', 'du', '-sb', '/var/lib/postgresql/data']).split(/\s/)[0]) / MiB) };
  a.disk.images_mib = Object.values(a.disk.images).reduce((s, v) => s + v, 0);
  must('docker', [...app, 'stop']);

  const imports = fs.mkdtempSync(path.join(os.tmpdir(), 'pp-bench-imports-'));
  try {
    a.import = bench('import', ['scripts/bench_import.py', '--out', path.relative(api, path.join(scratch, 'import.json'))], scratch, { PP_IMPORT_DIR: imports });
    a.import.report = JSON.parse(fs.readFileSync(path.join(scratch, 'import.json'), 'utf8'));
  } finally { fs.rmSync(imports, { recursive: true, force: true }); }
  a.forecast = bench('forecast', ['scripts/bench_forecast.py', '--part', 'lock', '--series', '50000'], scratch);
  const printed = fs.readFileSync(a.forecast.stdout, 'utf8');
  a.forecast.report = JSON.parse(printed.slice(printed.search(/^\{/m)));
  if (a.forecast.report.state !== 'SUCCEEDED') throw new Error(`the forecast bench ended ${a.forecast.report.state}: ${a.forecast.report.error}`);
  a.comparison = {};
  for (const mode of ['pantry', 'retail']) {
    const out = path.join(scratch, `or-${mode}.json`);
    a.comparison[mode] = bench(`comparison-${mode}`, ['../../scripts/or/bench_v1.py', '--mode', mode, '--out', path.relative(api, out)], scratch);
    a.comparison[mode].report = JSON.parse(fs.readFileSync(out, 'utf8'))[mode.toUpperCase()] ?? JSON.parse(fs.readFileSync(out, 'utf8'));
  }
  for (const phase of [a.import, a.forecast, a.comparison.pantry, a.comparison.retail]) delete phase.stdout;

  const file = path.join(root, `docs/testing/evidence/bench-${a.recorded_at.slice(0, 10)}.json`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(a, null, 2)}\n`);
  writeHardware(a, file);
  console.log(renderTable(a, path.relative(path.dirname(hardware), file).split(path.sep).join('/')));
  console.log(`Wrote ${path.relative(root, file)} and the HARDWARE.md block. The stack is stopped; \`docker compose down -v\` removes it.`);
}

if (require.main === module) main().catch((e) => { console.error(e); process.exitCode = 1; });
module.exports = { renderTable, renderSummary, minutes, relativeCommands };
