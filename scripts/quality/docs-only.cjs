#!/usr/bin/env node
// Decides whether a PR changes only documentation, so CI can skip the `full` job (Gabriel, 2026-11-11).
// Usage: git diff --name-only BASE HEAD | node scripts/quality/docs-only.cjs   -> prints true or false.
// Docs-only means every changed file is Markdown under docs/ or at the repo root, and no test or script
// reads it. The root README is excluded because W5-PK05 adds a check on its quickstart. A new reader of a
// docs/ Markdown file must be added to TEST_READ; scripts/quality/tests/docs-only.test.cjs enforces that.
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
  const files = require('node:fs').readFileSync(0, 'utf8').split('\n').filter(Boolean);
  console.log(String(isDocsOnly(files)));
}
