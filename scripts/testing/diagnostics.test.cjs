const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { diagnose, headings } = require("./diagnostics.cjs");

function removeOwnTemp(root) {
  const resolved = path.resolve(root);
  if (path.dirname(resolved) !== path.resolve(os.tmpdir()) || !path.basename(resolved).startsWith("pantrypulse-")) throw new Error("Unexpected temporary directory");
  fs.rmSync(resolved, { recursive: true });
}

test("heading anchors preserve duplicates and explicit HTML anchors", () => {
  assert.deepEqual([...headings('# One\n## One\n## Status: current\n<a id="custom"></a>')], ["one", "one-1", "status-current", "custom"]);
});
test("local link diagnostics distinguish actual missing files/headings from code examples and remote links", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pantrypulse-doc-diagnostics-"));
  try {
    fs.writeFileSync(path.join(root, "README.md"), '# Home\n[OK](target.md#real)\n[Missing](absent.md)\n[Wrong](target.md#absent)\n[Remote](https://example.com)\n```md\n[Example](not-real.md)\n```\n');
    fs.writeFileSync(path.join(root, "target.md"), "# Real\n");
    const report = diagnose(root);
    assert.deepEqual(report.findings.map((f) => [f.code, f.line]), [["MISSING_LINK_TARGET", 3], ["MISSING_HEADING", 4]]);
    assert.equal(report.linksChecked, 3);
  } finally {
    // Delete only the concrete temporary directory created by this test.
    removeOwnTemp(root);
  }
});
test("gate diagnostics fail for a missing npm script and missing Python test", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pantrypulse-gate-diagnostics-"));
  try {
    fs.mkdirSync(path.join(root, ".claude"));
    fs.writeFileSync(path.join(root, "package.json"), JSON.stringify({ scripts: { good: "echo ok" } }));
    fs.writeFileSync(path.join(root, ".claude/quality-gate.json"), JSON.stringify({ gates: { full: [
      { name: "bad", command: "npm", args: ["run", "absent"] },
      { name: "python", command: "uv", args: ["run", "pytest", "tests/absent.py"] },
      { name: "good", command: "npm", args: ["run", "good"] },
    ] } }));
    assert.deepEqual(diagnose(root).findings.map((f) => f.code), ["MISSING_GATE_SCRIPT", "MISSING_GATE_TEST"]);
  } finally { removeOwnTemp(root); }
});
