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

test('seed generates the login and proxy token into files; no env var or shell carries them', () => {
  const { services, volumes } = config({ PP_WEB_PORT: '3555' });
  assert.deepEqual(services.seed.command, ['uv', 'run', '--frozen', 'python', 'scripts/local_bootstrap.py']);
  assert.equal(services.seed.environment.PP_WEB_PORT, '3555');
  for (const [name, s] of Object.entries(services)) {
    const argv = [...(s.entrypoint ?? []), ...(s.command ?? [])].join(' ');
    assert.doesNotMatch(argv, /\beval\b|\bsh -c\b/, `${name} runs no shell`);
    for (const key of ['PP_TRUSTED_PROXY_TOKEN', 'PP_PRESENTER_PASSWORD_HASH']) {
      assert.ok(!(key in (s.environment ?? {})), `${name} has no ${key}`);
    }
  }
  const tokenFile = services.seed.environment.PP_TRUSTED_PROXY_TOKEN_FILE;
  assert.ok(tokenFile);
  const tokenDir = path.posix.dirname(tokenFile);
  for (const name of ['seed', 'api', 'web']) {
    assert.equal(services[name].environment.PP_TRUSTED_PROXY_TOKEN_FILE, tokenFile, name);
    const mount = services[name].volumes?.find((v) => v.target === tokenDir);
    assert.equal(mount?.type, 'volume', `${name} mounts the token volume`);
    assert.ok(mount.source in volumes, `${name} token volume is declared`);
    assert.equal(Boolean(mount.read_only), name !== 'seed', `${name} read_only`);
  }
  const loginFile = services.seed.environment.PP_LOCAL_LOGIN_FILE;
  const login = services.seed.volumes?.find((v) => v.target === path.posix.dirname(loginFile));
  assert.equal(login?.type, 'bind');
  assert.equal(login.source, path.join(root, '.pantrypulse'));
  for (const name of ['api', 'web', 'worker', 'migrate']) {
    assert.ok(!services[name].volumes?.some((v) => v.target === login.target), `${name} cannot see the login file`);
  }
  // The folder ships in the repo so Docker never creates it as root on Linux.
  assert.ok(fs.existsSync(path.join(root, '.pantrypulse', '.gitkeep')));
  const orgId = fs.readFileSync(path.join(root, 'apps/api/scripts/seed_local.py'), 'utf8')
    .match(/LOCAL_ORGANIZATION_ID = UUID\("([0-9a-f-]+)"\)/)[1];
  assert.equal(services.api.environment.PP_PRESENTER_ORGANIZATION_ID, orgId);
  assert.equal(services.api.environment.PP_PRESENTER_USERNAME, 'local');
});

test('api and worker share the imports volume; web never sees uploaded files', () => {
  const { services, volumes } = config();
  assert.ok(volumes.imports, 'named imports volume');
  for (const name of ['api', 'worker']) {
    const mount = services[name].volumes.find((v) => v.source === 'imports');
    assert.ok(mount, `${name} mounts imports`);
    assert.equal(mount.target, '/var/lib/pantrypulse/imports');
    assert.notEqual(mount.read_only, true, `${name} can write imports`);
    assert.equal(services[name].environment.PP_IMPORT_DIR, '/var/lib/pantrypulse/imports');
  }
  assert.ok(!services.web.volumes.some((v) => v.source === 'imports'));
});
