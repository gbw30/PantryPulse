// covers: V1-A24
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const script = path.join(__dirname, '..', 'check-version-pin.cjs');
const COMPOSE = (api, web) => `services:\n  api:\n    image: ghcr.io/gbw30/pantrypulse-api:${api}\n  web:\n    image: ghcr.io/gbw30/pantrypulse-web:${web}\n`;

function tree(compose, readme) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'version-pin-'));
  fs.writeFileSync(path.join(root, 'compose.yaml'), compose);
  fs.writeFileSync(path.join(root, 'README.md'), readme);
  return root;
}
const run = (root) => spawnSync(process.execPath, [script, '--root', root], { encoding: 'utf8' });

test("the README's version pin equals the compose image tags", () => {
  const result = run(tree(COMPOSE('0.1.0', '0.1.0'), 'Version pin: `0.1.0` (`ghcr.io/gbw30/pantrypulse-api:0.1.0`, `ghcr.io/gbw30/pantrypulse-web:0.1.0`)\n'));
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /0\.1\.0/);
});

test('a mismatch exits 1 and names both versions', () => {
  const result = run(tree(COMPOSE('0.2.0', '0.2.0'), 'Version pin: `0.1.0` (`ghcr.io/gbw30/pantrypulse-api:0.1.0`)\n'));
  assert.equal(result.status, 1);
  assert.match(result.stdout + result.stderr, /README.*0\.1\.0.*compose\.yaml.*0\.2\.0/s);
});

test('an image reference in the README that differs from the pin exits 1', () => {
  const result = run(tree(COMPOSE('0.1.0', '0.1.0'), 'Version pin: `0.1.0`; pull `ghcr.io/gbw30/pantrypulse-web:0.0.9`\n'));
  assert.equal(result.status, 1);
  assert.match(result.stdout + result.stderr, /pantrypulse-web:0\.0\.9/);
});

test('a README without a pin, or compose images with two versions, exits 1', () => {
  assert.equal(run(tree(COMPOSE('0.1.0', '0.1.0'), '# PantryPulse\n')).status, 1);
  assert.equal(run(tree(COMPOSE('0.1.0', '0.1.1'), 'Version pin: `0.1.0`\n')).status, 1);
});

test('the real README and compose.yaml agree', () => {
  const result = spawnSync(process.execPath, [script], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
