const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const cp = require('node:child_process');
const overlay = path.resolve(__dirname,'..','..','..');
function hook(name,input,options={}) {
  return cp.spawnSync(process.execPath,[path.join(overlay,'.claude','hooks',name+'.cjs')],{input:typeof input==='string'?input:JSON.stringify(input),encoding:'utf8',windowsHide:true,...options});
}
function temporary(t) {
  const parent = fs.realpathSync(process.env.PANTRYPULSE_TEST_TMP || os.tmpdir());
  const dir = fs.mkdtempSync(path.join(parent,'pp kit hooks '));
  t.after(()=>{const resolved=fs.realpathSync(dir); assert.equal(path.dirname(resolved),parent); assert.ok(path.basename(resolved).startsWith('pp kit hooks ')); fs.rmSync(resolved,{recursive:true});});
  return dir;
}
function repository(t,enabled,exit,timeoutSeconds=2) {
  const root=temporary(t);
  assert.equal(cp.spawnSync('git',['init','--quiet'],{cwd:root,windowsHide:true}).status,0);
  fs.mkdirSync(path.join(root,'.claude'),{recursive:true});
  fs.mkdirSync(path.join(root,'scripts','quality'),{recursive:true});
  fs.copyFileSync(path.join(overlay,'scripts','quality','run.cjs'),path.join(root,'scripts','quality','run.cjs'));
  fs.writeFileSync(path.join(root,'.gitignore'),'.claude/state/\n');
  fs.writeFileSync(path.join(root,'README.md'),'fixture\n');
  const config={enabled,timeoutSeconds,gates:{quick:[{name:'fixture',command:process.execPath,args:['-e','process.exit('+exit+')']}]}};
  fs.writeFileSync(path.join(root,'.claude','quality-gate.json'),JSON.stringify(config));
  assert.equal(cp.spawnSync('git',['add','.'],{cwd:root,windowsHide:true}).status,0);
  assert.equal(cp.spawnSync('git',['-c','user.name=Toolkit Test','-c','user.email=toolkit@example.invalid','commit','--quiet','-m','fixture'],{cwd:root,windowsHide:true}).status,0);
  return root;
}
test('SessionStart emits the documented event context object',()=>{
  const r=hook('session-context',{hook_event_name:'SessionStart'}); assert.equal(r.status,0);
  const body=JSON.parse(r.stdout); assert.equal(body.hookSpecificOutput.hookEventName,'SessionStart'); assert.match(body.hookSpecificOutput.additionalContext,/PantryPulse/);
});
test('normal edit stays silent and does not auto-approve',()=>{
  const r=hook('pre-tool',{tool_name:'Write',cwd:process.cwd(),tool_input:{file_path:'src/index.ts'}}); assert.equal(r.status,0); assert.equal(r.stdout,'');
});
test('private environment file is denied while example file is allowed',()=>{
  const deny=hook('pre-tool',{tool_name:'Edit',cwd:process.cwd(),tool_input:{file_path:'.env.local'}});
  assert.equal(JSON.parse(deny.stdout).hookSpecificOutput.permissionDecision,'deny');
  const ok=hook('pre-tool',{tool_name:'Write',cwd:process.cwd(),tool_input:{file_path:'.env.example'}}); assert.equal(ok.status,0); assert.equal(ok.stdout,'');
});
test('Git metadata write is denied',()=>{
  const r=hook('pre-tool',{tool_name:'Write',cwd:process.cwd(),tool_input:{file_path:'.git/config'}}); assert.equal(JSON.parse(r.stdout).hookSpecificOutput.permissionDecision,'deny');
});
test('dangerous command is denied and safe command has no approval decision',()=>{
  for (const command of ['git reset --hard','git push --force origin main','rm -rf build','claude --dangerously-skip-permissions']) {
    const r=hook('pre-tool',{tool_name:'Bash',tool_input:{command}}); assert.equal(JSON.parse(r.stdout).hookSpecificOutput.permissionDecision,'deny',command);
  }
  const ok=hook('pre-tool',{tool_name:'PowerShell',tool_input:{command:'git status --short'}}); assert.equal(ok.status,0); assert.equal(ok.stdout,'');
});
test('invalid PreToolUse input fails with exit 2',()=>{assert.equal(hook('pre-tool','not json').status,2);});
test('disabled Stop gate explicitly reports unverified',t=>{
  const root=repository(t,false,1); const r=hook('stop-gate',{cwd:root,stop_hook_active:false}); assert.equal(r.status,0); assert.match(r.stderr,/UNVERIFIED/);
});
test('enabled passing Stop gate succeeds in a path with spaces',t=>{
  const root=repository(t,true,0); const r=hook('stop-gate',{cwd:root,stop_hook_active:false}); assert.equal(r.status,0,r.stderr);
  assert.equal(JSON.parse(fs.readFileSync(path.join(root,'.claude','state','quality','quick.json'))).pass,true);
});
test('enabled failing Stop gate blocks, repeat avoids loop without claiming pass',t=>{
  const root=repository(t,true,1); const fail=hook('stop-gate',{cwd:root,stop_hook_active:false}); assert.equal(fail.status,2); assert.match(fail.stderr,/FAIL fixture/);
  const repeat=hook('stop-gate',{cwd:root,stop_hook_active:true}); assert.equal(repeat.status,0); assert.match(repeat.stderr,/unresolved/);
});
test('Stop gate falls back to the project directory when the given cwd no longer exists',t=>{
  // Generous budget: this test checks the cwd fallback, not gate timing on a loaded machine.
  const root=repository(t,true,0,30); const missing=path.join(temporary(t),'deleted start folder');
  const r=hook('stop-gate',{cwd:missing,stop_hook_active:false},{env:{...process.env,CLAUDE_PROJECT_DIR:root}});
  assert.equal(r.status,0,r.stderr);
});
test('Stop gate still fails closed when no usable worktree can be found',t=>{
  const outside=temporary(t); const missing=path.join(outside,'deleted start folder');
  const env={...process.env}; delete env.CLAUDE_PROJECT_DIR;
  const r=hook('stop-gate',{cwd:missing,stop_hook_active:false},{env,cwd:outside});
  assert.equal(r.status,2); assert.match(r.stderr,/Cannot identify the active Git worktree/);
});
