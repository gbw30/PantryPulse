// covers: V1-A21
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const tls = require('node:tls');
const { spawnSync } = require('node:child_process');
const http = require('node:http');
const { parseCapture, classify, findSecrets, scanDir, scanGit, client } = require('../egress-journey.cjs');

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

test('outbound IPv6 from the stack is flagged, whatever it carries', () => {
  const events = capture([{ kind: 'ipv6', src: 'fd00::5', dst: '2606:4700::1111', next_header: 6 }]);
  const { destinations, violations } = classify(events, { googleKey: true });
  assert.deepEqual(destinations.map((d) => d.allowed), [false]);
  assert.deepEqual(violations, [{ destination: '[2606:4700::1111]/ipv6', reason: 'outbound IPv6' }]);
});

test('the client keeps every API response body, so the secret scan can read them', async () => {
  const server = http.createServer((req, res) => res.end(JSON.stringify({ echoed: req.url })));
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  try {
    const api = client(`http://127.0.0.1:${server.address().port}`);
    await api.call('GET', '/api/v1/a', { expect: [200] });
    await api.call('GET', '/api/v1/b', { expect: [200] });
    assert.deepEqual(api.responses, ['{"echoed":"/api/v1/a"}', '{"echoed":"/api/v1/b"}']);
  } finally { server.close(); }
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

test('the sniffer records only the stack bridge: direct DNS and global IPv6 are flagged, nothing else is kept', () => {
  // Docker's embedded resolver (127.0.0.11) never puts a container's query on the bridge, so UDP to
  // port 53 leaving the stack's subnet there is a direct lookup to an outside server. Off the bridge
  // nothing is recorded: with host networking on native Linux that traffic is every host process's.
  const py = String.raw`
import importlib.util, ipaddress, json, struct, sys
spec = importlib.util.spec_from_file_location("sniff", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def v4(src, dst, sport, dport):
    ip = bytes([0x45, 0, 0, 0, 0, 0, 0, 0, 64, 17, 0, 0])
    ip += ipaddress.ip_address(src).packed + ipaddress.ip_address(dst).packed
    return b"\x00" * 12 + b"\x08\x00" + ip + struct.pack("!HHHH", sport, dport, 16, 0) + b"\x00" * 8
def v6(src, dst):
    ip = bytes([0x60, 0, 0, 0, 0, 8, 17, 64]) + ipaddress.ip_address(src).packed + ipaddress.ip_address(dst).packed
    return b"\x00" * 12 + b"\x86\xdd" + ip + struct.pack("!HHHH", 40000, 443, 8, 0)
subnet = ipaddress.ip_network("172.30.0.0/16")
def mac(frame, first):  # the bridge always carries Ethernet; Docker's random MACs can start with any byte
    return bytes([first]) + frame[1:]
cases = [("br-x", v4("172.30.0.5", "203.0.113.9", 40001, 53)),
         ("services1", v4("192.168.65.6", "192.168.65.7", 40002, 53)),
         ("eth0", v4("10.0.0.2", "1.1.1.1", 40003, 53)),
         ("br-x", v6("fd00::5", "2606:4700::1111")),
         ("br-x", v6("fe80::5", "fe80::1")),
         ("br-x", v6("fe80::5", "ff02::16")),
         ("eth0", v6("2001:db8::5", "2606:4700::1111")),
         ("br-x", mac(v4("172.30.0.5", "203.0.113.9", 40004, 5353), 0x6a)),
         ("br-x", mac(b"\x00" * 12 + b"\x08\x06" + bytes(28), 0x45))]
print(json.dumps([m.packet_event(frame, iface, "br-x", subnet) for iface, frame in cases]))
`;
  const run = spawnSync('python3', ['-I', '-c', py, path.join(__dirname, '..', 'egress-sniff.py')], { encoding: 'utf8' });
  assert.equal(run.status, 0, run.stderr);
  const [direct, resolver, host, global6, linkLocal, multicast, host6, macSix, arpMacFour] = JSON.parse(run.stdout);
  assert.equal(macSix?.kind, 'udp', 'an IPv4 frame whose MAC starts 0x6_ is IPv4, never IPv6');
  assert.equal(arpMacFour, null, 'an ARP frame whose MAC starts 0x4_ is not IPv4');
  assert.equal(direct.kind, 'udp');
  assert.deepEqual([resolver, host, linkLocal, multicast, host6], [null, null, null, null, null]);
  assert.equal(global6.kind, 'ipv6');
  assert.equal(global6.dst, '2606:4700::1111');
  const { violations } = classify([{ kind: 'start' }, direct, global6], { googleKey: false });
  assert.deepEqual(violations.map((v) => v.destination).sort(), ['203.0.113.9:53/udp', '[2606:4700::1111]/ipv6']);
});
