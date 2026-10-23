const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const cp = require('node:child_process');
const overlay = path.resolve(__dirname,'..','..','..');
const {execute,fingerprint}=require(path.join(overlay,'scripts','quality','run.cjs'));
function fixture(t,command='process.exit(0)',extra={}) {
  const parent=fs.realpathSync(process.env.PANTRYPULSE_TEST_TMP || os.tmpdir());
  const root=fs.mkdtempSync(path.join(parent,'pp kit quality '));
  t.after(()=>{const resolved=fs.realpathSync(root); assert.equal(path.dirname(resolved),parent); assert.ok(path.basename(resolved).startsWith('pp kit quality ')); fs.rmSync(resolved,{recursive:true});});
  assert.equal(cp.spawnSync('git',['init','--quiet'],{cwd:root,windowsHide:true}).status,0);
  fs.mkdirSync(path.join(root,'.claude'));
  fs.writeFileSync(path.join(root,'.gitignore'),'.claude/state/\n');
  fs.writeFileSync(path.join(root,'README.md'),'fixture');
  const item={name:'fixture gate',command:process.execPath,args:['-e',command]};
  const config={enabled:true,timeoutSeconds:3,gates:{quick:[item],full:[item],e2e:[item]},...extra};
  fs.writeFileSync(path.join(root,'.claude','quality-gate.json'),JSON.stringify(config));
  assert.equal(cp.spawnSync('git',['add','.'],{cwd:root,windowsHide:true}).status,0);
  assert.equal(cp.spawnSync('git',['-c','user.name=Toolkit Test','-c','user.email=toolkit@example.invalid','commit','--quiet','-m','fixture'],{cwd:root,windowsHide:true}).status,0);
  return root;
}
test('passing full gate includes quick and records stable content evidence',t=>{
  const root=fixture(t); const before=fingerprint(root); const result=execute(root,'full'); assert.equal(result.pass,true); assert.equal(result.results.length,2); assert.equal(fingerprint(root),before); assert.equal(result.treeSha256,before);
});
test('failed command is not called passed',t=>{const root=fixture(t,'process.exit(1)'); assert.equal(execute(root,'quick').pass,false);});
test('missing gate command fails closed',t=>{
  const root=fixture(t,'',{gates:{quick:[{name:'missing',command:'pantrypulse-command-does-not-exist',args:[]}]}}); assert.equal(execute(root,'quick').pass,false);
});
test('empty required group is unverified',t=>{const root=fixture(t,'',{gates:{quick:[]}}); assert.throws(()=>execute(root,'quick'),/Missing nonempty/);});
test('source mutation during checks invalidates green exit status',t=>{
  const root=fixture(t,"require('node:fs').writeFileSync('new-source.txt','changed')"); const result=execute(root,'quick'); assert.equal(result.pass,false); assert.equal(result.sourceUnchangedDuringRun,false);
});
test('untracked source content is included in fingerprint',t=>{
  const root=fixture(t); const a=fingerprint(root); fs.writeFileSync(path.join(root,'new.ts'),'one'); const b=fingerprint(root); fs.writeFileSync(path.join(root,'new.ts'),'two'); const c=fingerprint(root); assert.notEqual(a,b); assert.notEqual(b,c);
});
test('gate directory cannot escape repository',t=>{
  const root=fixture(t,'',{gates:{quick:[{name:'outside',cwd:'..',command:process.execPath,args:['-e','process.exit(0)']}]}}); assert.throws(()=>execute(root,'quick'),/outside worktree/);
});
test('timeout fails verification',t=>{
  const root=fixture(t,'setTimeout(()=>{},2000)',{timeoutSeconds:0.05}); assert.equal(execute(root,'quick').pass,false);
});
