const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  if (input.stop_hook_active) {
    console.error('PantryPulse: avoiding a Stop loop; any previous gate failure remains unresolved.');
  } else {
    const cwd = input.cwd || process.cwd();
    const result = cp.spawnSync('git', ['rev-parse','--show-toplevel'], {cwd,encoding:'utf8',timeout:5000,windowsHide:true});
    if (result.status !== 0) throw new Error('Cannot identify the active Git worktree.');
    const root = path.resolve(result.stdout.trim());
    const config = JSON.parse(fs.readFileSync(path.join(root,'.claude','quality-gate.json'),'utf8'));
    if (!config.enabled) console.error('PantryPulse Stop gate disabled: application validation is UNVERIFIED.');
    else {
      const runner = cp.spawnSync(process.execPath, [path.join(root,'scripts','quality','run.cjs'),'quick'], {cwd:root,encoding:'utf8',timeout:165000,windowsHide:true});
      if (runner.status !== 0 || runner.error) {
        console.error('PantryPulse quick gate failed. Fix the reported failure, rerun the gate and report evidence. A skipped second Stop is not a pass.');
        console.error((runner.stderr || runner.stdout || runner.error?.message || 'No diagnostic').slice(-6000));
        process.exitCode = 2;
      }
    }
  }
} catch (error) { console.error('PantryPulse Stop gate failed: '+error.message); process.exitCode = 2; }
