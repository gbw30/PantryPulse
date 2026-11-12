// covers: V1-A21
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const tls = require('node:tls');
const { spawnSync } = require('node:child_process');
const { parseCapture, classify, findSecrets, scanDir, scanGit } = require('../egress-journey.cjs');

/** The first TLS record a real client sends to `servername` (its ClientHello). */
function clientHello(servername) {
  return new Promise((resolve, reject) => {
    const server = net.createServer((socket) => socket.once('data', (data) => {
      resolve(data.toString('hex'));
      socket.destroy();
      server.close();
    }));
    server.listen(0, '127.0.0.1', () => {
      tls.connect({ host: '127.0.0.1', port: server.address().port, servername }).on('error', () => {});
    });
    server.on('error', reject);
  });
}

let flow = 40000;
async function connection(sni, { dst = '148.129.75.136', dport = 443 } = {}) {
  const base = { src: '172.30.0.5', dst, sport: flow++, dport };
  const lines = [{ ...base, kind: 'connect' }];
  if (sni) lines.push({ ...base, kind: 'tls', tls: await clientHello(sni) });
  return lines;
}
const capture = (...groups) => parseCapture([{ kind: 'start' }, ...groups.flat()].map((e) => JSON.stringify({ t: 1, ...e })).join('\n'));

test('flags any destination outside the allowlist', async () => {
  const events = capture(
    await connection('geocoding.geo.census.gov'),
    await connection('api.census.gov'), // ACS rates come from the bundled table: never called
    await connection('telemetry.nextjs.org', { dst: '76.76.21.21' }),
    await connection('routes.googleapis.com', { dst: '142.250.1.95' }),
    await connection(null, { dst: '93.184.215.14', dport: 80 }), // no TLS server name to check
    [{ kind: 'udp', src: '172.30.0.5', dst: '142.250.1.95', sport: 5000, dport: 443 }],
  );
  const flagged = (googleKey) => classify(events, { googleKey }).violations.map((v) => v.destination);
  assert.deepEqual(flagged(false), ['api.census.gov:443', 'telemetry.nextjs.org:443',
    'routes.googleapis.com:443', '93.184.215.14:80', '142.250.1.95:443/udp']);
  // Google is allowed only when the user saved their own key.
  assert.deepEqual(flagged(true), ['api.census.gov:443', 'telemetry.nextjs.org:443',
    '93.184.215.14:80', '142.250.1.95:443/udp']);
  const { destinations } = classify(events, { googleKey: false });
  assert.deepEqual(destinations.filter((d) => d.allowed).map((d) => d.destination), ['geocoding.geo.census.gov:443']);
});

test('a capture with no start line, or a malformed line, is an error, not an empty pass', () => {
  assert.throws(() => classify(parseCapture(''), { googleKey: false }), /no capture/);
  assert.throws(() => parseCapture('{"kind":"start"}\nnot json'), /line 2/);
});

test('DNS answers name the addresses in the report', () => {
  // geocoding.geo.census.gov A 148.129.75.136, as the resolver answered it
  const name = Buffer.concat(['geocoding', 'geo', 'census', 'gov'].map((l) => Buffer.from([l.length, ...Buffer.from(l)])));
  const dns = Buffer.concat([Buffer.from('abcd81800001000100000000', 'hex'), name, Buffer.from([0, 0, 1, 0, 1]),
    Buffer.from('c00c000100010000003c0004', 'hex'), Buffer.from([148, 129, 75, 136])]).toString('hex');
  const events = capture([{ kind: 'dns', src: '192.168.65.7', dst: '192.168.65.6', sport: 53, dport: 41000, dns }]);
  assert.deepEqual(classify(events, { googleKey: false }).dnsNames, { '148.129.75.136': ['geocoding.geo.census.gov'] });
});

const SECRETS = { password: 'pw-Zk3vQ9xLm2Rt8YbN4', proxy_token: 'tok-Hq7Wc1Jp5Ds0Fg6Ke3Uv', google_key: 'AIzaSyFAKEFAKEFAKE0123456789' };

test('flags the password, proxy token or Google key in compose logs', () => {
  const logs = `api-1 | started\nseed-1 | password: ${SECRETS.password}\nweb-1 | ok`;
  assert.deepEqual(findSecrets(SECRETS, logs, 'compose logs'), [{ secret: 'password', where: 'compose logs' }]);
  assert.deepEqual(findSecrets(SECRETS, 'Open http://127.0.0.1:3000 — username: local', 'compose logs'), []);
});

test('flags a secret anywhere in the .next output', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'egress-next-'));
  fs.mkdirSync(path.join(dir, 'static/chunks'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'static/chunks/app.js'), `const t="${SECRETS.proxy_token}"`);
  fs.writeFileSync(path.join(dir, 'static/chunks/ok.js'), 'const t=1');
  assert.deepEqual(scanDir(dir, SECRETS, '.next'), [{ secret: 'proxy_token', where: '.next', file: 'static/chunks/app.js' }]);
});

test('flags a secret in tracked, untracked or newly committed Git files, never in ignored ones', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'egress-git-'));
  const git = (...args) => assert.equal(spawnSync('git', ['-c', 'user.email=t@e.st', '-c', 'user.name=t', '-C', root, ...args]).status, 0, args.join(' '));
  git('init', '-q');
  fs.writeFileSync(path.join(root, '.gitignore'), '.pantrypulse/\n');
  fs.mkdirSync(path.join(root, '.pantrypulse'));
  fs.writeFileSync(path.join(root, '.pantrypulse/local-login.txt'), `password: ${SECRETS.password}\n`);
  fs.writeFileSync(path.join(root, 'notes.md'), `key ${SECRETS.google_key}\n`);
  git('add', 'notes.md', '.gitignore');
  const since = new Date(Date.now() - 60_000);
  git('commit', '-qm', 'notes');
  fs.writeFileSync(path.join(root, 'notes.md'), 'clean\n'); // gone from the tree, still in history
  fs.writeFileSync(path.join(root, 'scratch.txt'), `t=${SECRETS.proxy_token}`);
  const findings = scanGit(root, SECRETS, since);
  assert.deepEqual(findings, [
    { secret: 'proxy_token', where: 'git working tree', file: 'scratch.txt' },
    { secret: 'google_key', where: 'git history' },
  ]);
  assert.ok(!JSON.stringify(findings).includes(SECRETS.google_key), 'a finding never repeats the secret');
});

test('the sniffer flags DNS that a container sends past Docker\'s resolver, and keeps resolver DNS for names', () => {
  // Docker's embedded resolver (127.0.0.11) never puts a container's query on the bridge, so
  // UDP to port 53 leaving the stack's subnet there is a direct lookup to an outside server.
  const py = String.raw`
import importlib.util, ipaddress, json, struct, sys
spec = importlib.util.spec_from_file_location("sniff", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def frame(src, dst, sport, dport):
    ip = bytes([0x45, 0, 0, 0, 0, 0, 0, 0, 64, 17, 0, 0])
    ip += ipaddress.ip_address(src).packed + ipaddress.ip_address(dst).packed
    return b"\x00" * 12 + b"\x08\x00" + ip + struct.pack("!HHHH", sport, dport, 16, 0) + b"\x00" * 8
subnet = ipaddress.ip_network("172.30.0.0/16")
cases = [("br-x", ("172.30.0.5", "203.0.113.9", 40001, 53)),
         ("services1", ("192.168.65.6", "192.168.65.7", 40002, 53))]
print(json.dumps([m.packet_event(frame(*a), iface, "br-x", subnet) for iface, a in cases]))
`;
  const run = spawnSync('python3', ['-I', '-c', py, path.join(__dirname, '..', 'egress-sniff.py')], { encoding: 'utf8' });
  assert.equal(run.status, 0, run.stderr);
  const [direct, resolver] = JSON.parse(run.stdout);
  assert.equal(direct.kind, 'udp');
  assert.equal(resolver.kind, 'dns');
  const { violations } = classify([{ kind: 'start' }, direct, resolver], { googleKey: false });
  assert.deepEqual(violations.map((v) => v.destination), ['203.0.113.9:53/udp']);
});
