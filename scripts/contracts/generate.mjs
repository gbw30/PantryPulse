import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const root = fileURLToPath(new URL("../../", import.meta.url));

export async function generate({ check = false } = {}) {
  const temporary = await mkdtemp(path.join(tmpdir(), "pantrypulse-contracts-"));
  try {
    const output = path.join(temporary, "openapi.json");
    const api = path.join(root, "apps", "api");
    const python = process.env.PANTRYPULSE_PYTHON || path.join(api, ".venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
    if (!existsSync(python)) throw new Error("Run uv sync --frozen --directory apps/api first");
    execFileSync(python, ["-m", "scripts.export_openapi", "--output", output], {
      cwd: api, stdio: "pipe", timeout: 30000,
    });
    const source = await readFile(output, "utf8");
    const types = astToString(await openapiTS(JSON.parse(source)));
    for (const [name, content] of [["openapi.json", source], ["schema.d.ts", types]]) {
      const target = path.join(root, "packages", "contracts", name);
      if (check) {
        const previous = await readFile(target, "utf8").catch(() => "");
        if (previous !== content) throw new Error(`Contract drift: ${name}; run npm run contracts:generate`);
      } else {
        await writeFile(target, content);
      }
    }
    console.log(check ? "Generated contracts match the API." : "Generated OpenAPI and TypeScript contracts.");
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await generate();
}
