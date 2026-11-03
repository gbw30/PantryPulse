const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "../..");
const required = [...Array.from({ length: 12 }, (_, i) => i + 1), 15, 16, 17, 18]
  .map((id) => `US-${String(id).padStart(2, "0")}`);

function validate(manifest, read = (file) => fs.readFileSync(path.join(root, file), "utf8")) {
  const errors = [];
  const seen = new Set();
  read(manifest.authority);
  for (const story of manifest.stories) {
    if (seen.has(story.id)) errors.push(`Duplicate ${story.id}`);
    seen.add(story.id);
    if (!required.includes(story.id)) errors.push(`Unknown story ${story.id}`);
    if (!read(story.source).includes(story.id)) errors.push(`${story.id}: missing source story`);
    if (!["partial", "blocked", "complete"].includes(story.status)) errors.push(`${story.id}: invalid status`);
    if (!story.acceptance?.length) errors.push(`${story.id}: missing V5 acceptance mapping`);
    for (const id of story.acceptance ?? []) {
      if (!read(manifest.authority).includes(id)) errors.push(`${story.id}: unknown acceptance ${id}`);
    }
    if (story.status !== "complete" && !story.gap) errors.push(`${story.id}: missing gap`);
    if (story.status === "complete" && (!story.e2e.length || story.gap)) errors.push(`${story.id}: complete requires E2E and no outstanding gap`);
    for (const file of [...story.unit, ...story.e2e]) read(file);
    if (story.e2e.length && !story.e2e.some((file) => read(file).includes(story.id))) errors.push(`${story.id}: no named E2E test`);
  }
  for (const id of required) if (!seen.has(id)) errors.push(`Missing ${id}`);
  return errors;
}

function main() {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "docs/testing/user-stories.json"), "utf8"));
  const errors = validate(manifest);
  if (errors.length) throw new Error(errors.join("\n"));
  const files = new Set(["docs/testing/user-stories.json", manifest.authority]);
  for (const story of manifest.stories) {
    for (const file of [story.source, ...story.unit, ...story.e2e]) files.add(file);
    process.stdout.write(`${story.id} ${story.status.toUpperCase().padEnd(8)} ${story.title}\n`);
  }
  const revision = spawnSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" });
  const report = {
    generatedAt: new Date().toISOString(),
    revision: revision.status === 0 ? revision.stdout.trim() : "unavailable",
    note: "Inventory of coverage, not a PASS report. File hashes identify uncommitted evidence too.",
    hashes: Object.fromEntries([...files].sort().map((file) => [file, crypto.createHash("sha256").update(fs.readFileSync(path.join(root, file))).digest("hex")])),
    stories: manifest.stories,
  };
  const dir = path.join(root, "artifacts/testing");
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "story-coverage.json"), JSON.stringify(report, null, 2) + "\n");
  const incomplete = manifest.stories.filter((story) => story.status !== "complete");
  process.stdout.write(`\n${incomplete.length}/${manifest.stories.length} stories still have product acceptance gaps. See artifacts/testing/story-coverage.json.\n`);
  if (process.argv.includes("--require-complete") && incomplete.length) process.exitCode = 1;
}

if (require.main === module) {
  try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
module.exports = { validate };
