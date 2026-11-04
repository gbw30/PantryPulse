// covers: V1-A02, V1-A24
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.join(__dirname, '..', '..', '..');
const version = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8')).version;

function config(env = {}) {
  const clean = { ...process.env, ...env };
  if (!('PP_WEB_PORT' in env)) delete clean.PP_WEB_PORT;
  const result = spawnSync('docker', ['compose', '-f', 'compose.yaml', 'config', '--format', 'json'], {
    cwd: root, env: clean, encoding: 'utf8', timeout: 60000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

test('local stack has exactly the six v1 services, built from named images', () => {
  const { services } = config();
  assert.deepEqual(Object.keys(services).sort(), ['api', 'migrate', 'postgres', 'seed', 'web', 'worker']);
  for (const name of ['migrate', 'seed', 'api', 'worker']) {
    assert.equal(services[name].image, `ghcr.io/gbw30/pantrypulse-api:${version}`, name);
    assert.ok(services[name].build, `${name} has a build section`);
  }
  assert.equal(services.web.image, `ghcr.io/gbw30/pantrypulse-web:${version}`);
  assert.ok(services.web.build, 'web has a build section');
});

test('only web publishes a port, on loopback, default 3000 and PP_WEB_PORT override', () => {
  for (const [env, published] of [[{}, '3000'], [{ PP_WEB_PORT: '3555' }, '3555']]) {
    const { services } = config(env);
    const withPorts = Object.entries(services).filter(([, s]) => s.ports?.length).map(([n]) => n);
    assert.deepEqual(withPorts, ['web']);
    assert.equal(services.web.ports.length, 1);
    assert.equal(services.web.ports[0].host_ip, '127.0.0.1');
    assert.equal(services.web.ports[0].published, published);
  }
});

test('api and worker wait for migrate and seed to complete', () => {
  const { services } = config();
  for (const name of ['api', 'worker']) {
    for (const dep of ['migrate', 'seed']) {
      assert.equal(services[name].depends_on?.[dep]?.condition, 'service_completed_successfully', `${name} -> ${dep}`);
    }
  }
});

test('postgres data volume never reuses the old pantrypulse_pgdata volume', () => {
  const { services, volumes } = config();
  assert.ok(!('pgdata' in (volumes ?? {})), 'volume key is not pgdata');
  for (const v of Object.values(volumes ?? {})) assert.notEqual(v.name, 'pantrypulse_pgdata');
  assert.ok(services.postgres.volumes?.some((v) => v.type === 'volume'), 'postgres has a named volume');
});

test('.gitattributes keeps shell scripts, Dockerfiles and entrypoint scripts LF', () => {
  const text = fs.readFileSync(path.join(root, '.gitattributes'), 'utf8');
  for (const rule of ['*.sh text eol=lf', 'Dockerfile* text eol=lf', '*.py text eol=lf']) {
    assert.ok(text.split('\n').some((line) => line.trim() === rule), `missing: ${rule}`);
  }
});
