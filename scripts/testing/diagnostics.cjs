const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

function filesBelow(root, relative = "") {
  const excluded = new Set([".git", "node_modules", ".next", ".next-e2e", ".venv", "artifacts", "test-results", "playwright-report", "__pycache__", ".claude", ".pytest_cache"]);
  return fs.readdirSync(path.join(root, relative), { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(relative, entry.name);
    if (entry.isDirectory()) return excluded.has(entry.name) ? [] : filesBelow(root, file);
    return entry.isFile() ? [file.replaceAll("\\", "/")] : [];
  });
}

function headings(source) {
  const counts = new Map();
  const anchors = new Set();
  for (const match of source.matchAll(/^#{1,6}\s+(.+?)\s*#*$/gm)) {
    const base = match[1].toLowerCase().replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
      .replace(/<[^>]*>/g, "").replace(/[^\p{L}\p{N}_\s-]/gu, "").replace(/\s/g, "-");
    const count = counts.get(base) ?? 0;
    counts.set(base, count + 1);
    anchors.add(count ? `${base}-${count}` : base);
  }
  for (const match of source.matchAll(/(?:id|name)=["']([^"']+)["']/g)) anchors.add(match[1]);
  return anchors;
}

function diagnose(root) {
  root = path.resolve(root);
  const files = filesBelow(root);
  if (fs.existsSync(path.join(root, ".claude/quality-gate.json"))) files.push(".claude/quality-gate.json");
  const findings = [];
  const add = (code, file, line, message) => findings.push({ code, file, line, message });
  let linksChecked = 0;
  for (const file of files.filter((file) => file.endsWith(".md"))) {
    const original = fs.readFileSync(path.join(root, file), "utf8");
    // Keep line numbers while ignoring examples inside fenced code blocks.
    const source = original.replace(/(^|\n)(`{3,}|~{3,})[^\n]*\n[\s\S]*?\n\2[^\n]*(?=\n|$)/g, (block) => block.replace(/[^\n]/g, " "));
    for (const match of source.matchAll(/!?\[[^\]\n]*\]\((?:<([^>]+)>|([^\s)]+))(?:\s+"[^"]*")?\)/g)) {
      const href = match[1] ?? match[2];
      if (/^(?:[a-z][\w+.-]*:|\/\/)/i.test(href)) continue;
      const line = source.slice(0, match.index).split("\n").length;
      let decoded;
      try { decoded = decodeURIComponent(href); } catch { add("INVALID_LINK", file, line, href); continue; }
      const [target, anchor] = decoded.split("#", 2);
      const absolute = target ? path.resolve(path.dirname(path.join(root, file)), target) : path.join(root, file);
      linksChecked++;
      if (!fs.existsSync(absolute)) {
        add("MISSING_LINK_TARGET", file, line, href);
      } else if (anchor && absolute.endsWith(".md") && !headings(fs.readFileSync(absolute, "utf8")).has(anchor)) {
        add("MISSING_HEADING", file, line, href);
      }
    }
  }
  const gateFile = ".claude/quality-gate.json";
  if (fs.existsSync(path.join(root, gateFile))) {
    const gate = JSON.parse(fs.readFileSync(path.join(root, gateFile), "utf8"));
    for (const [group, checks] of Object.entries(gate.gates ?? {})) for (const check of checks) {
      const cwd = path.resolve(root, check.cwd ?? ".");
      if (check.command === "npm" && check.args?.[0] === "run") {
        const manifest = path.join(cwd, "package.json");
        const scripts = fs.existsSync(manifest) ? JSON.parse(fs.readFileSync(manifest, "utf8")).scripts : {};
        if (!scripts?.[check.args[1]]) add("MISSING_GATE_SCRIPT", gateFile, 1, `${group}/${check.name}: ${check.cwd}: npm run ${check.args[1]}`);
      }
      for (const arg of check.args ?? []) {
        if (arg.startsWith("tests/") && !fs.existsSync(path.join(cwd, arg))) add("MISSING_GATE_TEST", gateFile, 1, `${group}/${check.name}: ${arg}`);
      }
    }
  }
  const conflicts = files.filter((file) => /\.(?:md|py|ts|tsx|json|ya?ml|cjs|mjs)$/.test(file)).flatMap((file) => {
    const source = fs.readFileSync(path.join(root, file), "utf8");
    // A complete conflict block avoids flagging explanatory marker examples.
    return /^<<<<<<< .+\r?\n[\s\S]*?^=======\r?\n[\s\S]*?^>>>>>>> .+$/m.test(source) ? [file] : [];
  });
  for (const file of conflicts) add("MERGE_CONFLICT", file, 1, "Unresolved merge conflict block");
  return {
    generatedAt: new Date().toISOString(), root, filesScanned: files.length,
    markdownFiles: files.filter((file) => file.endsWith(".md")).length, linksChecked,
    note: "Local file/link/gate diagnostics only. Missing headings need review for nonstandard Markdown. Historical docs are included; this does not test external URLs or certify feature behavior.",
    sourceFingerprint: crypto.createHash("sha256").update(files.filter((file) => /\.(?:md|json|ts|tsx|py|cjs|mjs|ya?ml)$/.test(file)).sort().map((file) => `${file}\0${crypto.createHash("sha256").update(fs.readFileSync(path.join(root, file))).digest("hex")}`).join("\n")).digest("hex"),
    findings,
  };
}

if (require.main === module) {
  try {
    const args = process.argv.slice(2);
    const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
    const root = option("--root", path.resolve(__dirname, "../.."));
    const report = diagnose(root);
    const output = path.resolve(option("--output", path.join(root, "artifacts/testing/diagnostics.json")));
    fs.mkdirSync(path.dirname(output), { recursive: true });
    fs.writeFileSync(output, JSON.stringify(report, null, 2) + "\n");
    console.log(`${report.filesScanned} files; ${report.markdownFiles} Markdown files; ${report.linksChecked} local links; ${report.findings.length} findings. Report: ${output}`);
    for (const finding of report.findings.slice(0, 30)) console.log(`${finding.code} ${finding.file}:${finding.line} ${finding.message}`);
    if (report.findings.length) process.exitCode = 1;
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
module.exports = { diagnose, headings };
