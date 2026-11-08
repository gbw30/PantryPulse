import { readFileSync } from "node:fs";
import path from "node:path";
import type { components } from "../../../../packages/contracts/src/schema";

export type Schemas = components["schemas"];
// jsdom gives import.meta.url a non-file scheme; vite-node still provides __dirname.
const EXAMPLES = path.resolve(__dirname, "../../../../packages/contracts/examples/v1");

/** A fresh deep copy of `packages/contracts/examples/v1/<name>.json` (never a hand-typed payload). */
export function example<K extends keyof Schemas>(name: K): Schemas[K] {
  return JSON.parse(readFileSync(path.join(EXAMPLES, `${String(name)}.json`), "utf8")) as Schemas[K];
}
