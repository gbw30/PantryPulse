#!/usr/bin/env node
// Decides whether a PR changes only documentation, so CI can skip the `full` job (Gabriel, 2026-11-11).
// Usage: node scripts/quality/docs-only.cjs BASE HEAD   -> prints true or false; exits 1 if git fails.
// Docs-only means every changed file is Markdown under docs/ or at the repo root, and no test or script
// reads it. The root README is excluded because W5-PK05 adds a check on its quickstart. A new reader of a
// docs/ Markdown file must be added to TEST_READ; scripts/quality/tests/docs-only.test.cjs enforces that
// for quoted literal paths.
// shortcut: the guard misses readers that build the path from parts, glob docs/ or read root Markdown;
// none exist today (verified 2026-11-11). Upgrade the guard if a test starts reading docs that way.
const TEST_READ = [
  'docs/plans/v1/README.md', // apps/api/tests/test_v1_contract.py
  'docs/forecasting/QUALIFICATION-PROTOCOL.md', // apps/api/scripts/evaluate_retail_forecasting.py
  'docs/optimization/DECISION-REGISTER.md', // scripts/or/check-decision-markers.py
];

const isDoc = (file) => file.endsWith('.md') && file !== 'README.md' && !TEST_READ.includes(file)
  && (file.startsWith('docs/') || !file.includes('/'));

const isDocsOnly = (files) => files.length > 0 && files.every(isDoc);

module.exports = { isDocsOnly, TEST_READ };

if (require.main === module) {
  const [base, head] = process.argv.slice(2);
  if (!base || !head) {
    console.error('usage: docs-only.cjs BASE HEAD');
    process.exit(1);
  }
  // --no-renames lists a renamed file's old path too, so moving a file a test reads is never docs-only.
  const diff = require('node:child_process').spawnSync('git', ['diff', '--no-renames', '--name-only', base, head], { encoding: 'utf8' });
  if (diff.status !== 0) {
    console.error(diff.stderr || `git diff failed (${diff.error ?? diff.status})`);
    process.exit(1);
  }
  console.log(String(isDocsOnly(diff.stdout.split('\n').filter(Boolean))));
}
