#!/usr/bin/env node
// Egress-logged journey (V1-A03, V1-A04). Installs the stack fresh under the lane's own Compose
// project, captures every outbound connection the stack makes (scripts/testing/egress-sniff.py on
// the project bridge), drives the A06–A16 journey over HTTP through the web's same-origin proxy
// on the two samples plus one import of user addresses (which geocodes through Census), then
// checks the generated password and proxy token never appear in the compose logs, the web's
// .next output or the Git tree. Writes artifacts/egress/report.json; exits 0 only on a clean run.
// Usage (from the repo root, with .env.lane loaded): node scripts/testing/egress-journey.cjs
// It runs `docker compose down -v` on COMPOSE_PROJECT_NAME first, so it refuses the default project.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const ALLOWED = ['geocoding.geo.census.gov'];
const WITH_KEY = ['routes.googleapis.com']; // only when the user saved their own Google key
const MIN_SECRET = 8;

/** JSON lines from egress-sniff.py; a malformed line is an error, never skipped. */
function parseCapture(text) {
  return text.split('\n').filter((l) => l.trim()).map((line, i) => {
    try { return JSON.parse(line); } catch { throw new Error(`capture line ${i + 1} is not JSON`); }
  });
}

/** The server name in a TLS ClientHello, or null (tolerates a ClientHello split across packets). */
function serverName(hex) {
  const b = Buffer.from(hex, 'hex');
  if (b[0] !== 0x16 || b[5] !== 0x01) return null;
  let p = 5 + 4 + 2 + 32;
  const skip = (n) => { p += n; return p <= b.length; };
  if (!skip(1 + b[p])) return null; // session id
  if (p + 2 > b.length || !skip(2 + b.readUInt16BE(p))) return null; // cipher suites
  if (p + 1 > b.length || !skip(1 + b[p])) return null; // compression methods
  p += 2; // extensions length
  while (p + 4 <= b.length) {
    const type = b.readUInt16BE(p);
    const len = b.readUInt16BE(p + 2);
    if (type === 0 && p + 9 <= b.length) {
      const nameLen = b.readUInt16BE(p + 7);
      return b.subarray(p + 9, p + 9 + nameLen).toString('ascii').toLowerCase();
    }
    p += 4 + len;
  }
  return null;
}

/** The question name and IPv4 answers of a DNS response, or null. */
function dnsAnswers(hex) {
  const b = Buffer.from(hex, 'hex');
  if (b.length < 12 || !(b[2] & 0x80)) return null;
  const name = (start) => {
    const labels = [];
    let p = start;
    let end = null;
    for (let hops = 0; p < b.length && hops < 64; hops++) {
      const len = b[p];
      if (len === 0) { end ??= p + 1; break; }
      if ((len & 0xc0) === 0xc0) { end ??= p + 2; p = b.readUInt16BE(p) & 0x3fff; continue; }
      labels.push(b.subarray(p + 1, p + 1 + len).toString('ascii'));
      p += 1 + len;
    }
    return { text: labels.join('.').toLowerCase(), end };
  };
  const question = name(12);
  let p = question.end + 4;
  const ips = [];
  for (let i = 0; i < b.readUInt16BE(6) && p + 10 <= b.length; i++) {
    p = name(p).end;
    const [type, rdlen] = [b.readUInt16BE(p), b.readUInt16BE(p + 8)];
    if (type === 1 && rdlen === 4) ips.push([...b.subarray(p + 10, p + 14)].join('.'));
    p += 10 + rdlen;
  }
  return { name: question.text, ips };
}

/** Every outbound destination the stack contacted, and those outside the allowlist. */
function classify(events, { googleKey }) {
  if (!events.some((e) => e.kind === 'start')) throw new Error('no capture: the sniffer never started');
  const allowed = new Set([...ALLOWED, ...(googleKey ? WITH_KEY : [])]);
  const dnsNames = {};
  for (const e of events.filter((x) => x.kind === 'dns')) {
    const answer = dnsAnswers(e.dns);
    for (const ip of answer?.ips ?? []) dnsNames[ip] = [...new Set([...(dnsNames[ip] ?? []), answer.name])].sort();
  }
  const flows = new Map();
  for (const e of events.filter((x) => ['connect', 'tls', 'udp'].includes(x.kind))) {
    const key = `${e.kind === 'udp' ? 'udp' : 'tcp'} ${e.src}:${e.sport}>${e.dst}:${e.dport}`;
    const f = flows.get(key) ?? { dst: e.dst, dport: e.dport, proto: e.kind === 'udp' ? 'udp' : 'tcp', sni: null };
    if (e.kind === 'tls') f.sni ??= serverName(e.tls);
    flows.set(key, f);
  }
  const byDestination = new Map();
  for (const f of flows.values()) {
    const destination = f.proto === 'udp' ? `${f.dst}:${f.dport}/udp` : `${f.sni ?? f.dst}:${f.dport}`;
    const d = byDestination.get(destination) ?? { destination, ip: f.dst, port: f.dport, proto: f.proto,
      server_name: f.sni, dns_names: dnsNames[f.dst] ?? [], allowed: f.proto === 'tcp' && allowed.has(f.sni), connections: 0 };
    d.connections += 1;
    byDestination.set(destination, d);
  }
  const destinations = [...byDestination.values()];
  const violations = destinations.filter((d) => !d.allowed).map((d) => ({ destination: d.destination,
    reason: d.proto === 'udp' ? 'outbound UDP (DNS past Docker\'s resolver included)' : d.server_name ? 'not in the allowlist' : 'no TLS server name to check' }));
  return { destinations, violations, dnsNames };
}

/** Which secrets (by name, never value) appear in `data` (a string or Buffer). */
function findSecrets(secrets, data, where) {
  return Object.entries(secrets)
    .filter(([, value]) => value && value.length >= MIN_SECRET && data.includes(value))
    .map(([secret]) => ({ secret, where }));
}

function scanDir(dir, secrets, where) {
  const findings = [];
  const walk = (d) => {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.isFile()) {
        const file = path.relative(dir, full).split(path.sep).join('/');
        findings.push(...findSecrets(secrets, fs.readFileSync(full), where).map((f) => ({ ...f, file })));
      }
    }
  };
  walk(dir);
  return findings;
}

/** Tracked and untracked-but-not-ignored files, plus every commit made since `since`. */
function scanGit(dir, secrets, since) {
  const git = (...args) => {
    const r = spawnSync('git', ['-C', dir, ...args], { maxBuffer: 1 << 30 });
    if (r.status !== 0) throw new Error(`git ${args[0]} failed: ${r.stderr}`);
    return r.stdout;
  };
  const files = [...new Set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').toString().split('\0').filter(Boolean))];
  const findings = [];
  for (const file of files) {
    const full = path.join(dir, file);
    if (!fs.statSync(full, { throwIfNoEntry: false })?.isFile()) continue; // deleted or a submodule
    findings.push(...findSecrets(secrets, fs.readFileSync(full), 'git working tree').map((f) => ({ ...f, file })));
  }
  const history = git('log', '--all', '-p', '--no-color', '--binary', `--since=${since.toISOString()}`);
  return [...findings, ...findSecrets(secrets, history, 'git history')];
}

// ---- the run ---------------------------------------------------------------------------------

/**
 * A compose override with the same build recipes and config as compose.yaml but lane-local image
 * tags, so a run never retags the ghcr.io/gbw30/pantrypulse-*:<version> images that another
 * install on this machine uses. Returns its path.
 */
function laneImages(project, dir) {
  const file = path.join(dir, 'compose.images.yaml');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(file, `services:\n${['migrate', 'seed', 'api', 'worker'].map((s) => `  ${s}: { image: ${project}-api:local }\n`).join('')}  web: { image: ${project}-web:local }\n`);
  return file;
}

const sh = (cmd, args, opts = {}) => spawnSync(cmd, args, { cwd: root, encoding: 'utf8', maxBuffer: 1 << 30, windowsHide: true, ...opts });
function must(cmd, args, opts) {
  const r = sh(cmd, args, opts);
  if (r.status !== 0) throw new Error(`${cmd} ${args.slice(0, 4).join(' ')} failed: ${(r.stderr || r.error?.message || '').slice(-2000)}`);
  return r.stdout;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** A browser-like client of the web's same-origin /api/v1 proxy: cookies, Origin and CSRF. */
function client(base) {
  const cookies = new Map();
  let csrf = null;
  async function call(method, url, { json, body, headers = {}, expect } = {}) {
    const res = await fetch(new URL(url, base), { method, redirect: 'manual', headers: {
      Origin: base, Cookie: [...cookies].map(([k, v]) => `${k}=${v}`).join('; '),
      ...(csrf && method !== 'GET' ? { 'X-CSRF-Token': csrf } : {}),
      ...(json ? { 'Content-Type': 'application/json' } : {}), ...headers,
    }, body: json ? JSON.stringify(json) : body });
    for (const c of res.headers.getSetCookie()) { const [kv] = c.split(';'); const i = kv.indexOf('='); cookies.set(kv.slice(0, i), kv.slice(i + 1)); }
    const text = await res.text();
    if (expect && !expect.includes(res.status)) throw new Error(`${method} ${url} → ${res.status}: ${text.slice(0, 500)}`);
    let data = text;
    try { data = JSON.parse(text); } catch { /* CSV or text */ }
    return { status: res.status, data, headers: res.headers };
  }
  return { call, setCsrf: (t) => { csrf = t; } };
}

async function until(what, timeoutMs, probe) {
  const end = Date.now() + timeoutMs;
  for (;;) {
    const value = await probe();
    if (value) return value;
    if (Date.now() > end) throw new Error(`${what}: no result within ${timeoutMs / 1000} s`);
    await sleep(2000);
  }
}

const TERMINAL = ['SUCCEEDED', 'FAILED', 'CANCELLED', 'EXPIRED'];
const METHODS = { PANTRY: ['NO_TRANSFERS', 'EQUAL_SHARE', 'MOST_URGENT_FIRST', 'CLASSICAL_GP', 'EGP_PI_INSPIRED'],
  RETAIL: ['NO_TRANSFERS', 'SOONEST_EXPIRY_FIRST', 'RETAIL_OPTIMIZED'] };
const key = () => `egress-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

async function job(api, accepted, what, timeoutMs) {
  const status = await until(what, timeoutMs, async () => {
    const r = await api.call('GET', accepted.status_url, { expect: [200] });
    return TERMINAL.includes(r.data.state) && r.data;
  });
  if (status.state !== 'SUCCEEDED') throw new Error(`${what} ended ${status.state}: ${JSON.stringify(status).slice(0, 500)}`);
  return status;
}

async function importFiles(api, { name, mode, files, asOf }) {
  const created = await api.call('POST', '/api/v1/imports', { json: { network: { name, mode, timezone: 'America/New_York' } }, expect: [201] });
  const id = created.data.import_id;
  for (const [file, text] of Object.entries(files)) {
    const r = await api.call('POST', `/api/v1/imports/${id}/files/${file}`, { body: text, headers: { 'Content-Type': 'text/csv' } });
    if (r.status !== 200) return { id, rejected: `${file}: ${r.status}`, detail: r.data };
  }
  const commit = await api.call('POST', `/api/v1/imports/${id}/commit`, { json: { as_of_date: asOf }, headers: { 'Idempotency-Key': key() } });
  if (commit.status !== 202) return { id, rejected: `commit: ${commit.status}`, detail: commit.data };
  const status = await until(`import ${name}`, 600_000, async () => {
    const r = await api.call('GET', `/api/v1/imports/${id}`, { expect: [200] });
    return ['done', 'failed'].includes(r.data.phase) && r.data;
  });
  return { id, status };
}

async function forecast(api, network) {
  const accepted = await api.call('POST', `/api/v1/networks/${network.id}/forecasts`, {
    json: { dataset_version_id: network.dataset_version_id }, headers: { 'Idempotency-Key': key() }, expect: [202] });
  await job(api, accepted.data, `forecast ${network.name}`, 600_000);
  const runs = await api.call('GET', `/api/v1/networks/${network.id}/forecasts`, { expect: [200] });
  const run = runs.data.runs?.find((r) => r.dataset_version_id === network.dataset_version_id) ?? runs.data.runs?.[0];
  if (!run) throw new Error(`no forecast run listed for ${network.name}: ${JSON.stringify(runs.data).slice(0, 300)}`);
  return { run, jobId: accepted.data.job_id };
}

async function compareAndExport(api, network, scenario, measure) {
  const accepted = await api.call('POST', `/api/v1/networks/${network.id}/comparisons`, {
    json: { scenario_id: scenario.id, methods: METHODS[network.mode], measure }, headers: { 'Idempotency-Key': key() }, expect: [202] });
  await job(api, accepted.data, `comparison ${network.name} ${measure}`, 900_000);
  const saved = (await api.call('GET', accepted.data.result_url, { expect: [200] })).data;
  const unverified = saved.result.methods.filter((m) => !m.verified).map((m) => `${m.method}: ${m.failure_reason}`);
  if (unverified.length) throw new Error(`unverified methods: ${unverified.join('; ')}`);
  const chosen = [...saved.result.methods].reverse().find((m) => m.transfers?.length);
  if (!chosen) throw new Error('no method moved stock, so there is nothing to export');
  const base = `/api/v1/networks/${network.id}/comparisons/${saved.id}/methods/${chosen.method}`;
  const actions = (await api.call('GET', `${base}/actions`, { expect: [200] })).data.actions;
  const csv = await api.call('POST', `${base}/export`, { json: { action_ids: actions.map((a) => a.id) }, expect: [200] });
  if (!String(csv.data).includes(saved.result.scenario_hash) || !String(csv.data).includes('simulated plan; no stock was reserved or moved')) {
    throw new Error('export lacks the scenario hash or the simulated-plan note');
  }
  return `${saved.result.methods.length} methods verified; ${chosen.method} exported ${actions.length} actions`;
}

async function journey(api, password, steps) {
  const step = async (name, fn) => {
    try { steps.push({ step: name, ok: true, detail: (await fn()) ?? '' }); }
    catch (e) { steps.push({ step: name, ok: false, detail: e.message }); throw e; }
  };
  await step('sign in as local', async () => {
    const login = await api.call('POST', '/api/v1/presenter/login', { json: { username: 'local', password }, expect: [200] });
    api.setCsrf(login.data.csrf_token);
  });
  await step('A06 templates and an example file', async () => {
    await api.call('GET', '/api/v1/templates?mode=PANTRY', { expect: [200] });
    await api.call('GET', '/api/v1/templates/locations.csv?kind=example&mode=PANTRY', { expect: [200] });
  });
  const fixtures = path.join(root, 'apps/api/tests/networks/fixtures/mini-network');
  const files = Object.fromEntries(['locations', 'products', 'inventory', 'demand_history', 'inbound']
    .map((n) => [n, fs.readFileSync(path.join(fixtures, `${n}.csv`), 'utf8')]));
  await step('A07 a malformed file is rejected and nothing is saved', async () => {
    const bad = { ...files, demand_history: files.demand_history.replace(/\n(\w+),(\w+),(\d{4})-(\d\d)-(\d\d)/, '\n$1,$2,$4/$5/$3') };
    const name = `Egress bad ${key()}`;
    const r = await importFiles(api, { name, mode: 'PANTRY', files: bad, asOf: '2026-11-04' });
    if (!r.rejected && r.status.phase !== 'failed') throw new Error(`a non-ISO date was accepted: ${JSON.stringify(r.status).slice(0, 300)}`);
    const saved = (await api.call('GET', '/api/v1/networks', { expect: [200] })).data.networks.filter((n) => n.name === name);
    if (saved.length) throw new Error('the rejected import created a network');
    return `${r.rejected ?? `phase failed, ${r.status.errors?.length ?? 0} errors listed`}; no network created`;
  });
  await step('A10 import of user addresses, then Census geocoding', async () => {
    // Two public-building addresses and one that cannot match (tests/integration/test_v1_backend_journey.py).
    const addressed = { ...files, locations: files.locations.replace(/\n?$/, '\n') +
      'P4,Pantry Four,pantry,73 W Flagler St,Miami,FL,33130,,,,,\nP5,Pantry Five,pantry,100 S Andrews Ave,Fort Lauderdale,FL,33301,,,,,\n' +
      'P6,Pantry Six,pantry,99999 Nonexistent Pantry Rd,Tallahassee,FL,32301,,,,,\n' };
    const r = await importFiles(api, { name: `Egress addresses ${key()}`, mode: 'PANTRY', files: addressed, asOf: '2026-11-04' });
    if (r.rejected || r.status.phase !== 'done') throw new Error(`import failed: ${r.rejected ?? JSON.stringify(r.status).slice(0, 500)}`);
    const enriched = await until('enrichment', 300_000, async () => {
      const e = await api.call('GET', `/api/v1/networks/${r.status.network_id}/enrichment`, { expect: [200] });
      return e.data.state !== 'running' && e.data;
    });
    const known = enriched.locations?.filter((l) => l.state === 'known').length;
    return `enrichment ${enriched.state}; ${known} locations with known attributes; ${enriched.unmatched?.length ?? 0} unmatched`;
  });
  const networks = (await api.call('GET', '/api/v1/networks', { expect: [200] })).data.networks;
  for (const mode of ['PANTRY', 'RETAIL']) {
    const network = networks.find((n) => n.is_sample && n.mode === mode);
    let run;
    await step(`A12 ${mode} sample forecast and its backtest`, async () => {
      if (!network) throw new Error(`no ${mode} sample network`);
      const f = await forecast(api, network);
      run = f.run;
      await api.call('GET', `/api/v1/forecasts/${f.jobId}/backtest`, { expect: [200] });
      return `forecast run ${run.id ?? run.forecast_run_id}`;
    });
    const runId = run.id ?? run.forecast_run_id;
    await step(`A13 ${mode} danger ranking and projection`, async () => {
      const { rows } = (await api.call('GET', `/api/v1/networks/${network.id}/danger?forecast_run_id=${runId}`, { expect: [200] })).data;
      if (!rows.length) throw new Error('the danger ranking is empty');
      const top = encodeURIComponent(rows[0].location_id);
      await api.call('GET', `/api/v1/networks/${network.id}/projection?forecast_run_id=${runId}&location_id=${top}`, { expect: [200] });
      return `${rows.length} ranked rows; projection of #1 ${rows[0].location_id}`;
    });
    const transfers = mode === 'PANTRY' ? ['HUB_ONLY', 'HUB_AND_PANTRY'] : ['HUB_ONLY'];
    for (const transfer of transfers) {
      const scenario = (await api.call('POST', `/api/v1/networks/${network.id}/scenarios`, { expect: [201], json: {
        dataset_version_id: network.dataset_version_id, forecast_run_id: runId, transfer_mode: transfer,
        ...(mode === 'PANTRY' ? { planning_days: 2 } : {}) } })).data;
      for (const measure of mode === 'PANTRY' ? ['UNITS'] : ['UNITS', 'USD']) {
        await step(`${mode === 'PANTRY' ? 'A14' : 'A15'} A16 ${mode} ${transfer} ${measure}: compare, decide, export`,
          () => compareAndExport(api, network, scenario, measure));
      }
    }
  }
}

async function main() {
  const project = process.env.COMPOSE_PROJECT_NAME;
  if (!project || project === 'pantrypulse') {
    console.error('Set COMPOSE_PROJECT_NAME to a disposable project (e.g. load .env.lane): this run starts with `docker compose down -v`.');
    process.exit(2);
  }
  const port = process.env.PP_WEB_PORT || '3000';
  const outDir = path.join(root, 'artifacts/egress');
  fs.mkdirSync(outDir, { recursive: true });
  const captureFile = path.join(outDir, 'capture.jsonl');
  fs.rmSync(captureFile, { force: true });
  const app = ['compose', '-f', 'compose.yaml', '-f', laneImages(project, outDir)];
  const capture = ['compose', '-p', `${project}-egress`, '-f', 'compose.test.yaml', '--profile', 'egress'];
  const report = { commit: must('git', ['rev-parse', 'HEAD']).trim(),
    dirty_paths: must('git', ['status', '--porcelain']).split('\n').filter(Boolean).map((l) => l.slice(3)),
    project, web_port: port, google_key_configured: false, started_at: new Date().toISOString() };
  const steps = [];
  let secrets = {};
  try {
    console.log('Building the images (build-time downloads are outside the capture)…');
    must('docker', [...app, 'build'], { stdio: 'inherit' });
    must('docker', [...app, 'down', '-v', '--remove-orphans']);
    must('docker', [...app, 'up', '--no-start']);
    const network = JSON.parse(must('docker', ['network', 'inspect', `${project}_default`]))[0];
    report.bridge = `br-${network.Id.slice(0, 12)}`;
    report.subnet = network.IPAM.Config[0].Subnet;
    must('docker', [...capture, 'up', '-d', 'egress-capture'], { env: { ...process.env, EGRESS_BRIDGE: report.bridge, EGRESS_SUBNET: report.subnet } });
    await until('the capture to start', 60_000, async () => fs.existsSync(captureFile) && fs.readFileSync(captureFile, 'utf8').includes('"start"'));
    report.install_started_at = new Date().toISOString();
    console.log('Starting the stack with the capture running…');
    must('docker', [...app, 'up', '-d', '--wait', '--wait-timeout', '900']);
    const login = fs.readFileSync(path.join(root, '.pantrypulse/local-login.txt'), 'utf8');
    secrets = { password: /^password: (.+)$/m.exec(login)?.[1], proxy_token: must('docker', [...app, 'exec', '-T', 'web', 'cat', '/run/pantrypulse/proxy-token']).trim() };
    if (!secrets.password || !secrets.proxy_token) throw new Error('could not read the generated password or proxy token');
    console.log('Driving the journey…');
    await journey(client(`http://127.0.0.1:${port}`), secrets.password, steps).catch((e) => console.error(`journey stopped: ${e.message}`));
  } catch (e) {
    steps.push({ step: 'install', ok: false, detail: e.message });
  } finally {
    sh('docker', [...capture, 'down', '--remove-orphans']);
  }
  report.finished_at = new Date().toISOString();
  report.journey = steps;
  report.egress = classify(parseCapture(fs.existsSync(captureFile) ? fs.readFileSync(captureFile, 'utf8') : ''), { googleKey: false });
  const findings = [];
  if (secrets.password) {
    findings.push(...findSecrets(secrets, must('docker', [...app, 'logs', '--no-color']), 'compose logs'));
    const next = fs.mkdtempSync(path.join(os.tmpdir(), 'pp-egress-next-'));
    try {
      must('docker', [...app, 'cp', 'web:/app/apps/web/.next', next]);
      findings.push(...scanDir(next, secrets, '.next output'));
    } finally { fs.rmSync(next, { recursive: true, force: true }); }
    findings.push(...scanGit(root, secrets, new Date(report.started_at)));
  }
  report.secrets = { checked: Object.keys(secrets).filter((k) => secrets[k]), sources: ['compose logs', '.next output', 'git working tree', 'git history since the run started'], findings };
  // Positive control: the address import geocodes, so a capture that saw no Census connection is blind.
  report.capture_saw_geocoding = report.egress.destinations.some((d) => d.server_name === ALLOWED[0]);
  report.pass = steps.length > 0 && steps.every((s) => s.ok) && report.capture_saw_geocoding &&
    report.egress.violations.length === 0 && findings.length === 0 && report.secrets.checked.length === 2;
  if (!report.capture_saw_geocoding) console.log('FAIL the capture saw no Census connection although the journey geocodes: it is blind');
  fs.writeFileSync(path.join(outDir, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
  for (const s of steps) console.log(`${s.ok ? 'ok  ' : 'FAIL'} ${s.step}${s.detail ? ` — ${s.detail}` : ''}`);
  for (const d of report.egress.destinations) console.log(`${d.allowed ? 'allowed ' : 'FLAGGED '} ${d.destination} (${d.connections} connections)`);
  for (const f of findings) console.log(`SECRET  ${f.secret} in ${f.where}${f.file ? `: ${f.file}` : ''}`);
  console.log(`${report.pass ? 'PASS' : 'FAIL'} — artifacts/egress/report.json. The stack is still up under ${project}; stop it with \`docker compose down -v\`.`);
  process.exitCode = report.pass ? 0 : 1;
}

if (require.main === module) main().catch((e) => { console.error(e); process.exitCode = 1; });
module.exports = { parseCapture, classify, findSecrets, scanDir, scanGit, serverName, dnsAnswers, laneImages };
