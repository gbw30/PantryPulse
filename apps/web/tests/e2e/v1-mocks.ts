import { readFileSync } from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";
import type { components } from "../../../../packages/contracts/src/schema";

// Contract mocks for the v1 screens (W1-web). Every payload starts from a file in
// packages/contracts/examples/v1/, never a hand-typed body. Tests may clone and adjust an example to
// reach a state the example doesn't show; the result is still checked against the generated type.
// These mocks prove UI behavior against the contract, not the connected app.

export type Schemas = components["schemas"];
export const BASE = `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT ?? "3000"}`;
const EXAMPLES = path.resolve(__dirname, "../../../../packages/contracts/examples/v1");

/** A fresh deep copy of `packages/contracts/examples/v1/<name>.json`. */
export function example<K extends keyof Schemas>(name: K): Schemas[K] {
  return JSON.parse(readFileSync(path.join(EXAMPLES, `${String(name)}.json`), "utf8")) as Schemas[K];
}

export const envelope = (code: string, message = code.toLowerCase().replaceAll("_", " "), details: Record<string, unknown> = {}) =>
  ({ error: { code, message, details }, request_id: "00000000-0000-4000-8000-000000000999" });

export type Reply = { status?: number; body?: unknown; contentType?: string; headers?: Record<string, string> };
export type Call = { method: string; path: string; query: URLSearchParams; body: string | null };
type Routes = Record<string, Reply | ((call: Call) => Reply)>;

/**
 * Answers every `/api/v1/**` request from `routes`, keyed `"<METHOD> <path>"` (path without the
 * `/api/v1/` prefix or query). Unlisted routes get a 404 envelope, so a test never reaches a real API.
 * `presenter` (default true) sets the CSRF cookie and answers the session probe.
 */
export async function mockV1(page: Page, routes: Routes, { presenter = true } = {}) {
  const calls: Call[] = [];
  if (presenter) await page.context().addCookies([{ name: "pp_csrf", value: "token", url: BASE }]);
  await page.route("**/api/v1/**", (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const call: Call = { method: request.method(), path: url.pathname.replace(/^\/api\/v1\//, ""), query: url.searchParams, body: request.postData() };
    calls.push(call);
    const entry = routes[`${call.method} ${call.path}`];
    const reply: Reply = typeof entry === "function" ? entry(call)
      : entry ?? (presenter && call.path === "allocation-methodology" ? { body: {} } : { status: 404, body: envelope("NOT_FOUND") });
    const contentType = reply.contentType ?? "application/json";
    return route.fulfill({
      status: reply.status ?? 200, contentType, headers: reply.headers,
      body: typeof reply.body === "string" ? reply.body : JSON.stringify(reply.body ?? null),
    });
  });
  return calls;
}
