const fs = require('node:fs');
try {
  JSON.parse(fs.readFileSync(0, 'utf8'));
  console.log(JSON.stringify({hookSpecificOutput:{hookEventName:'SessionStart',additionalContext:'PantryPulse: read CLAUDE.md and docs/pantrypulse/PROJECT-CONTRACT.md. Check assigned base SHA and task ownership before writing. Gate disabled means unverified. Preserve provenance, units and deterministic demo behavior.'}}));
} catch { console.error('PantryPulse SessionStart: invalid JSON input.'); process.exitCode = 1; }
