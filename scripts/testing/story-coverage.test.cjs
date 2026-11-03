const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { validate } = require("./story-coverage.cjs");
const root = path.resolve(__dirname, "../..");
const manifest = () => JSON.parse(fs.readFileSync(path.join(root, "docs/testing/user-stories.json"), "utf8"));

test("every documented story and V5 acceptance mapping has inspectable evidence or a gap", () => {
  assert.deepEqual(validate(manifest()), []);
});
test("missing or duplicated stories cannot silently disappear from the inventory", () => {
  const input = manifest();
  input.stories[0] = input.stories[1];
  const errors = validate(input);
  assert.ok(errors.includes("Missing US-01"));
  assert.ok(errors.includes("Duplicate US-02"));
});
test("marking a blocked story complete requires browser evidence and no outstanding gap", () => {
  const input = manifest();
  input.stories.find((story) => story.id === "US-15").status = "complete";
  assert.ok(validate(input).some((error) => error.includes("complete requires E2E")));
});
test("stale evidence paths fail instead of counting as coverage", () => {
  const input = manifest();
  input.stories[0].unit.push("missing-test.ts");
  assert.throws(() => validate(input), /ENOENT/);
});
test("a source or acceptance ID absent from the actual documentation fails", () => {
  const input = manifest();
  input.stories[0].acceptance = ["V5-A99"];
  assert.ok(validate(input).some((error) => error.includes("unknown acceptance V5-A99")));
});
