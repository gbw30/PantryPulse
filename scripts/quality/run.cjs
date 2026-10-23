const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const crypto = require('node:crypto');
function git(root, args) {
  const r = cp.spawnSync('git', args, {cwd:root,encoding:'utf8',windowsHide:true,timeout:10000,maxBuffer:20*1024*1024});
  if (r.status !== 0 || r.error) throw new Error('Git preflight failed: '+args.join(' '));
  return r.stdout;
}
function fingerprint(root) {
  root = path.resolve(root);
  const hash = crypto.createHash('sha256');
  const names = [...new Set(git(root,['ls-files','--cached','--others','--exclude-standard','-z']).split('\0').filter(Boolean))].sort();
  for (const name of names) {
    if (/^(?:\.claude\/state\/|artifacts\/|playwright-report\/|test-results\/)/.test(name)) continue;
    const absolute = path.resolve(root,name);
    if (!absolute.startsWith(root+path.sep)) throw new Error('File outside worktree.');
    hash.update(name+'\0');
    try {
      const stat = fs.lstatSync(absolute);
      if (stat.isSymbolicLink()) hash.update(fs.readlinkSync(absolute));
      else if (stat.isFile()) hash.update(fs.readFileSync(absolute));
      else hash.update('[non-file]');
    } catch (e) { if (e.code === 'ENOENT') hash.update('[deleted]'); else throw e; }
  }
  return hash.digest('hex');
}
function execute(root, mode) {
  root = path.resolve(root);
  const config = JSON.parse(fs.readFileSync(path.join(root,'.claude','quality-gate.json'),'utf8'));
  if (!['quick','full','e2e'].includes(mode)) throw new Error('Choose quick, full or e2e.');
  const groups = mode === 'full' ? ['quick','full'] : [mode];
  for (const group of groups) if (!Array.isArray(config.gates?.[group]) || !config.gates[group].length) throw new Error('Missing nonempty gate group: '+group);
  const before = fingerprint(root);
  const results = [];
  const gateStarted = Date.now();
  const budget = config.budgetSeconds?.[mode] || ({quick:120,full:600,e2e:300})[mode];
  for (const item of groups.flatMap(group => config.gates[group])) {
    if (!item.name || !item.command || !Array.isArray(item.args) || item.args.some(x => typeof x !== 'string')) throw new Error('Invalid gate entry.');
    const cwd = path.resolve(root,item.cwd || '.');
    if (cwd !== root && !cwd.startsWith(root+path.sep)) throw new Error('Gate cwd outside worktree.');
    if (!fs.existsSync(cwd)) throw new Error('Missing gate directory: '+item.cwd);
    let program = item.command;
    let args = item.args;
    let shell = false;
    // npm is a trusted .cmd wrapper on Windows. Reject shell metacharacters in all configured arguments.
    if (process.platform === 'win32' && program === 'npm') {
      if (args.some(a => !/^[a-zA-Z0-9_:.\/=-]+$/.test(a))) throw new Error('Unsafe Windows npm argument; use a JS wrapper.');
      program = 'npm.cmd'; shell = true;
    }
    const remaining = 1000*budget - (Date.now()-gateStarted);
    if (remaining <= 0) { console.error('FAIL total gate time budget exceeded.'); break; }
    const started = Date.now();
    const timeout = Math.max(1,Math.min(remaining,1000*(item.timeoutSeconds || config.timeoutSeconds || 90)));
    const r = cp.spawnSync(program,args,{cwd,encoding:'utf8',windowsHide:true,shell,timeout,maxBuffer:5*1024*1024,env:process.env});
    const pass = !r.error && r.status === 0;
    results.push({name:item.name,pass,exitCode:r.status,durationMs:Date.now()-started});
    console.error((pass ? 'PASS ' : 'FAIL ')+item.name);
    if (!pass) { console.error((r.stderr || r.stdout || r.error?.message || 'Unknown failure').slice(-6000)); break; }
  }
  const after = fingerprint(root);
  const pass = before === after && results.every(r => r.pass) && results.length === groups.flatMap(g => config.gates[g]).length;
  const evidence = {mode,pass,head:git(root,['rev-parse','HEAD']).trim(),treeSha256:after,sourceUnchangedDuringRun:before === after,generatedAt:new Date().toISOString(),results};
  const dest = path.join(root,'.claude','state','quality');
  fs.mkdirSync(dest,{recursive:true});
  fs.writeFileSync(path.join(dest,mode+'.json'),JSON.stringify(evidence,null,2)+'\n');
  if (before !== after) console.error('FAIL source changed during checks; rerun on a stable candidate.');
  return evidence;
}
if (require.main === module) {
  try {
    const root = git(process.cwd(),['rev-parse','--show-toplevel']).trim();
    process.exitCode = execute(root,process.argv[2]).pass ? 0 : 1;
  } catch (e) { console.error('UNVERIFIED: '+e.message); process.exitCode = 1; }
}
module.exports = {execute,fingerprint};
