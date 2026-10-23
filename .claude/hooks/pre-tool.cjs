const fs = require('node:fs');
const path = require('node:path');
try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  let reason = '';
  if (['Edit','Write'].includes(input.tool_name)) {
    const supplied = input.tool_input?.file_path;
    if (typeof supplied !== 'string' || !supplied) throw new Error('missing file_path');
    const file = path.resolve(input.cwd || process.cwd(), supplied);
    const parts = file.split(/[\\/]/);
    const leaf = parts.at(-1).toLowerCase();
    if ((/^\.env(?:\.|$)/i.test(leaf) && !['.env.example','.env.sample'].includes(leaf)) || /\.(pem|key)$/i.test(leaf)) reason = 'Use an environment example or secret manager; this hook blocks writing credential files.';
    if (parts.some(p => p.toLowerCase() === '.git')) reason = 'Do not edit Git internal files.';
  }
  if (['Bash','PowerShell'].includes(input.tool_name)) {
    const command = String(input.tool_input?.command || '');
    if (/--dangerously-skip-permissions|git\s+(?:[^;\n]*\s)?reset\s+--hard|git\s+push\b[^;\n]*(?:--force|-f\b)|rm\s+-rf\b/i.test(command)) reason = 'Destructive or permission-bypass command blocked. Return a safe, reviewable alternative to the lead.';
  }
  if (reason) console.log(JSON.stringify({hookSpecificOutput:{hookEventName:'PreToolUse',permissionDecision:'deny',permissionDecisionReason:reason}}));
} catch { console.error('PantryPulse PreToolUse: invalid hook input; action not authorized by this hook.'); process.exitCode = 2; }
// This is a heuristic accident guard. Shell aliases, interpreters, MCP tools and OS access need separate permissions/isolation.
