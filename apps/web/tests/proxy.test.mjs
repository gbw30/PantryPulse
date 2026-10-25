import test from "node:test";
import assert from "node:assert/strict";
import { NextRequest } from "next/server.js";
import { GET, POST } from "../src/app/api/v1/[...path]/route.ts";

const context = (path) => ({ params: Promise.resolve({ path }) });

test("loopback normalization preserves legitimate same-origin presenter requests", async (t) => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  let forwarded = false;
  globalThis.fetch = async (_url, init) => {
    forwarded = true;
    assert.equal(init.headers.get("origin"), "http://127.0.0.1:3012");
    assert.equal(init.headers.get("cookie"), "pp_presenter=opaque; pp_csrf=proof");
    assert.equal(init.headers.get("x-forwarded-origin"), null);
    return Response.json({ authenticated: true });
  };
  const request = new NextRequest("http://127.0.0.1:3012/api/v1/presenter/login", {
    method: "POST", body: "{}", headers: {
      Host: "127.0.0.1:3012", Origin: "http://127.0.0.1:3012",
      Cookie: "unrelated=secret; pp_presenter=opaque; pp_csrf=proof",
      "X-Forwarded-Origin": "https://attacker.invalid",
    },
  });
  assert.equal(new URL(request.url).hostname, "localhost");
  const response = await POST(request, context(["presenter", "login"]));
  assert.equal(response.status, 200);
  assert.equal(forwarded, true);
});

test("cross-origin mutations and forged loopback host remain forbidden", async () => {
  for (const [origin, host] of [
    ["https://attacker.invalid", "127.0.0.1:3012"],
    ["http://attacker.invalid", "attacker.invalid"],
  ]) {
    const request = new NextRequest("http://127.0.0.1:3012/api/v1/demo/seed", {
      method: "POST", body: "{}", headers: { Host: host, Origin: origin },
    });
    assert.equal((await POST(request, context(["demo", "seed"]))).status, 403);
  }
});

test("saved-list pagination and session cookies survive the thin proxy", async (t) => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async () => Response.json([], { headers: {
    "X-Next-Cursor": "opaque-page-cursor", "X-Request-ID": "request-one",
    "Set-Cookie": "pp_presenter=opaque; HttpOnly; SameSite=Strict; Path=/",
  } });
  const response = await GET(new NextRequest("http://127.0.0.1:3012/api/v1/scenarios?limit=1"),
    context(["scenarios"]));
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("x-next-cursor"), "opaque-page-cursor");
  assert.match(response.headers.get("set-cookie"), /HttpOnly/);
  assert.equal(response.headers.get("cache-control"), "no-store");
});
