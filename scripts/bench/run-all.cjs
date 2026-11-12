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
// docs/pantrypulse/HARDWARE.md from it. Usage, with .env.lane loaded: node scripts/bench/run-all.cjs
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

const minutes = (s) => (s < 60 ? `${s.toFixed(0)} s` : `${Math.floor(s / 60)} min ${String(Math.round(s % 60)).padStart(2, '0')} s`);
const gib = (mib) => `${(mib / 1024).toFixed(1)} GiB`;
const when = (iso) => iso.replace(/\.\d+Z$/, 'Z');

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
    ['First-run build, `docker compose build --no-cache` (base images already downloaded)', minutes(a.build.seconds), a.build.started_at],
    ['First start, `docker compose up --wait` (migrate, seed, web ready)', minutes(a.start.seconds), a.start.started_at],
    ['Idle stack, all services', `RAM ${a.idle.memory_mib} MiB (peak ${a.idle.memory_peak_mib} MiB); CPU ${a.idle.cpu_percent}% of one core`, a.idle.started_at],
    ['Disk after first start', `images ${gib(a.disk.images_mib)}; database ${a.disk.database_mib} MiB`, a.disk.measured_at],
    [`A09 import, ${a.import.report.generated.locations} × ${a.import.report.generated.products} × 90 days (${a.import.report.loaded.net_demand_history.toLocaleString('en-US')} demand rows, ${a.import.report.loaded.net_batches.toLocaleString('en-US')} batches)`,
      `job steps ${minutes(a.import.report.seconds.total)} (validate ${minutes(a.import.report.seconds.step)}, prepare ${minutes(a.import.report.seconds.prepare)}, publish ${minutes(a.import.report.seconds.publish)}); run ${bench(a.import)}`, a.import.started_at],
    [`A17 forecast, ${a.forecast.report.series.toLocaleString('en-US')} series × ${a.forecast.report.days ?? 90} days, through the queue and publisher`, bench(a.forecast), a.forecast.started_at],
    ...['pantry', 'retail'].map((mode) => {
      const c = a.comparison[mode];
      const walls = Object.entries(c.report.comparison_wall_s).map(([k, v]) => `${k.toLowerCase()} ${minutes(v)}`).join(', ');
      return [`A17 ${mode === 'pantry' ? 'Pantry' : 'Retail'} comparison, ${c.report.size.locations} × ${c.report.size.products}, every method (${walls})`,
        `${bench(c)}; ${verified(c)}`, c.started_at];
    }),
  ];
  return [
    `Measured on ${m.cpu}, ${m.cpus} logical CPUs, ${gib(m.ram_mib)} RAM, ${m.os}; Docker ${m.docker_version} with ${m.docker_cpus} CPUs and ${gib(m.docker_memory_mib)} for Docker. ` +
      `Commit \`${a.commit.slice(0, 7)}\`${a.dirty_paths.length ? ` plus ${a.dirty_paths.length} uncommitted paths, ${a.dirty_paths.some((p) => p.startsWith('apps/')) ? 'some under `apps/`' : 'none under `apps/`'} (listed in the artifact)` : ''}. Artifact: [${path.basename(link)}](${link}).`,
    '',
    '| Measure | Result | Started (UTC) |',
    '|---|---|---|',
    ...rows.map(([measure, result, at]) => `| ${measure} | ${result} | ${when(at)} |`),
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
  const t = process.hrtime.bigint();
  fn();
  return { started_at, seconds: Math.round(Number(process.hrtime.bigint() - t) / 1e8) / 10 };
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
  const usage = path.join(scratch, `${name}.rusage.json`);
  const stdout = path.join(scratch, `${name}.stdout`);
  const out = fs.openSync(stdout, 'w');
  const r = spawnSync(path.join(api, '.venv/bin/python'), ['-c', RUSAGE, usage, 'taskset', '-c', '0-5', 'uv', 'run', '--frozen', 'python', ...args],
    { cwd: api, stdio: ['ignore', out, 'inherit'], env: { ...process.env, ...env } });
  fs.closeSync(out);
  const u = JSON.parse(fs.readFileSync(usage, 'utf8'));
  if (r.status !== 0 || u.returncode !== 0) throw new Error(`${name} failed (exit ${u.returncode}); see ${stdout}`);
  return { started_at, command: ['taskset -c 0-5 uv run --frozen python', ...args].join(' '), wall_s: Math.round(u.wall_s * 10) / 10,
    cpu_s: Math.round(u.cpu_s), cpu_avg_cores: Math.round((u.cpu_s / u.wall_s) * 10) / 10, peak_rss_mib: Math.round(u.peak_rss_kib / 1024), stdout };
}

async function main() {
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
  a.idle = { started_at: now(), ...(await sampleStats(containers, 30)) };
  const images = must('docker', [...app, 'config', '--images']).trim().split('\n');
  a.disk = { measured_at: now(), images: Object.fromEntries(images.map((i) => [i, Math.round(Number(must('docker', ['image', 'inspect', '-f', '{{.Size}}', i])) / MiB)])),
    database_mib: Math.round(Number(must('docker', [...app, 'exec', '-T', 'postgres', 'du', '-sb', '/var/lib/postgresql/data']).split(/\s/)[0]) / MiB) };
  a.disk.images_mib = Object.values(a.disk.images).reduce((s, v) => s + v, 0);
  must('docker', [...app, 'stop']);

  const imports = fs.mkdtempSync(path.join(os.tmpdir(), 'pp-bench-imports-'));
  try {
    a.import = bench('import', ['scripts/bench_import.py', '--out', path.join(scratch, 'import.json')], scratch, { PP_IMPORT_DIR: imports });
    a.import.report = JSON.parse(fs.readFileSync(path.join(scratch, 'import.json'), 'utf8'));
  } finally { fs.rmSync(imports, { recursive: true, force: true }); }
  a.forecast = bench('forecast', ['scripts/bench_forecast.py', '--part', 'lock', '--series', '50000'], scratch);
  const printed = fs.readFileSync(a.forecast.stdout, 'utf8');
  a.forecast.report = JSON.parse(printed.slice(printed.search(/^\{/m)));
  if (a.forecast.report.state !== 'SUCCEEDED') throw new Error(`the forecast bench ended ${a.forecast.report.state}: ${a.forecast.report.error}`);
  a.comparison = {};
  for (const mode of ['pantry', 'retail']) {
    const out = path.join(scratch, `or-${mode}.json`);
    a.comparison[mode] = bench(`comparison-${mode}`, ['../../scripts/or/bench_v1.py', '--mode', mode, '--out', out], scratch);
    a.comparison[mode].report = JSON.parse(fs.readFileSync(out, 'utf8'))[mode.toUpperCase()] ?? JSON.parse(fs.readFileSync(out, 'utf8'));
  }
  for (const phase of [a.import, a.forecast, a.comparison.pantry, a.comparison.retail]) delete phase.stdout;

  const file = path.join(root, `docs/testing/evidence/bench-${a.recorded_at.slice(0, 10)}.json`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(a, null, 2)}\n`);
  const link = path.relative(path.dirname(hardware), file).split(path.sep).join('/');
  const text = fs.readFileSync(hardware, 'utf8');
  fs.writeFileSync(hardware, text.replace(/<!-- bench:begin -->\n[\s\S]*?<!-- bench:end -->/, `<!-- bench:begin -->\n${renderTable(a, link)}<!-- bench:end -->`));
  console.log(renderTable(a, link));
  console.log(`Wrote ${path.relative(root, file)} and the HARDWARE.md block. The stack is stopped; \`docker compose down -v\` removes it.`);
}

if (require.main === module) main().catch((e) => { console.error(e); process.exitCode = 1; });
module.exports = { renderTable, minutes };
