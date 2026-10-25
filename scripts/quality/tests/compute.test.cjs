const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

test('compute helper preserves tasks and enforces resource/admission guards', () => {
  const shell = process.platform === 'win32' ? 'powershell.exe' : 'pwsh';
  const result = spawnSync(shell, [
    '-NoProfile', '-File', path.join(__dirname, 'compute-windows.tests.ps1'),
  ], { encoding: 'utf8', windowsHide: true, timeout: 30000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /11 compute guard cases passed/);
});
