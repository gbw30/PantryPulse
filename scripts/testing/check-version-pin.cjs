#!/usr/bin/env node
// The README's version pin must equal the ghcr.io/gbw30/pantrypulse-*:<version> tags in compose.yaml
// (V1-SPEC §7, V1-A24), and every image reference in the README must use that version.
// Usage: node scripts/testing/check-version-pin.cjs [--root <dir>]
const fs = require('node:fs');
const path = require('node:path');

const args = process.argv.slice(2);
const root = path.resolve(args.includes('--root') ? args[args.indexOf('--root') + 1] : path.join(__dirname, '..', '..'));
const IMAGE = /ghcr\.io\/gbw30\/pantrypulse-[a-z]+:([^\s`"')]+)/g;

const compose = fs.readFileSync(path.join(root, 'compose.yaml'), 'utf8');
const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
const tags = [...new Set([...compose.matchAll(IMAGE)].map((m) => m[1]))];
const pin = /Version pin: `([^`]+)`/.exec(readme)?.[1];
const errors = [];
if (tags.length !== 1) errors.push(`compose.yaml must tag every pantrypulse image with one version, found: ${tags.join(', ') || 'none'}`);
if (!pin) errors.push('README.md has no "Version pin: `<version>`" line');
else if (tags.length === 1 && pin !== tags[0]) errors.push(`README.md pins ${pin} but compose.yaml tags ${tags[0]}`);
for (const m of readme.matchAll(IMAGE)) if (m[1] !== pin) errors.push(`README.md references ${m[0]}, not the pinned ${pin}`);
for (const e of errors) console.log(e);
if (!errors.length) console.log(`README.md and compose.yaml both pin ${pin}`);
process.exitCode = errors.length ? 1 : 0;
