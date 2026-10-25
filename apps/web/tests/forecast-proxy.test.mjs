import assert from "node:assert/strict";
import { test } from "node:test";
import { NextRequest } from "next/server.js";
import { GET, POST } from "../src/app/api/v1/[...path]/route.ts";

test("proxy limits paths, origins, bytes and forwards only selected credentials", async (t) => {
  process.env.PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:8000";
  process.env.PP_TRUSTED_PROXY_TOKEN = "test-proxy-secret";
  t.after(() => {
    delete process.env.PANTRYPULSE_API_ORIGIN;
    delete process.env.PP_TRUSTED_PROXY_TOKEN;
  });
  const fetchMock = t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "http://127.0.0.1:8000/api/v1/forecasts");
    assert.equal(options.headers.get("x-forwarded-origin"), "http://localhost:3000");
    assert.equal(options.headers.get("x-pp-proxy-token"), "test-proxy-secret");
    assert.equal(options.headers.get("cookie"), "pp_presenter=opaque; pp_csrf=csrf");
    assert.equal(options.headers.has("authorization"), false);
    return new Response('{"job_id":"saved"}', { status: 202, headers: {
      "Content-Type": "application/json", "Location": "/api/v1/jobs/saved",
      "Set-Cookie": "pp_presenter=opaque; HttpOnly; Path=/; SameSite=Strict",
    } });
  });
  const missing = await GET(new Request("http://localhost:3000/api/v1/admin"));
  assert.equal(missing.status, 404);
  assert.deepEqual(await missing.json(), {
    error: { code: "NOT_FOUND", message: "not found", details: {} },
    request_id: missing.headers.get("x-request-id"),
  });
  assert.equal((await POST(new Request("http://localhost:3000/api/v1/forecasts", {
    method: "POST", headers: { Origin: "https://evil.example" }, body: "{}",
  }))).status, 403);
  assert.equal((await POST(new Request("http://localhost:3000/api/v1/forecasts", {
    method: "POST", headers: { Origin: "http://localhost:3000" }, body: "x".repeat(65537),
  }))).status, 413);
  const result = await POST(new Request("http://localhost:3000/api/v1/forecasts", {
    method: "POST", body: "{}", headers: {
      Origin: "http://localhost:3000", Cookie: "unrelated=secret; pp_presenter=opaque; pp_csrf=csrf",
      Authorization: "Bearer never-forward", "X-PP-Proxy-Token": "spoof",
    },
  }));
  assert.equal(result.status, 202);
  assert.equal(result.headers.get("Location"), "/api/v1/jobs/saved");
  assert.equal(result.headers.getSetCookie().length, 1);
  assert.equal(fetchMock.mock.calls.length, 1);
});

test("real NextRequest preserves browser origin despite loopback URL normalization", async (t) => {
  process.env.PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:8000";
  process.env.PP_TRUSTED_PROXY_TOKEN = "test-proxy-secret";
  t.after(() => {
    delete process.env.PANTRYPULSE_API_ORIGIN;
    delete process.env.PP_TRUSTED_PROXY_TOKEN;
  });
  const fetchMock = t.mock.method(globalThis, "fetch", async (_url, options) => {
    assert.ok(["http://127.0.0.1:3000", "https://demo.example"].includes(
      options.headers.get("x-forwarded-origin"),
    ));
    return Response.json({ ok: true });
  });
  const request = (origin, forwardedHost) => new NextRequest(
    "http://127.0.0.1:3000/api/v1/presenter/login", {
      method: "POST", body: "{}", headers: {
        Host: "127.0.0.1:3000", Origin: origin,
        "X-Forwarded-Host": forwardedHost ?? "ignored.example",
      },
    });
  const legitimate = request("http://127.0.0.1:3000");
  assert.equal(new URL(legitimate.url).hostname, "localhost");
  assert.equal((await POST(legitimate)).status, 200);
  assert.equal((await POST(request("http://localhost:3000"))).status, 403);
  assert.equal((await POST(request("https://evil.example", "evil.example"))).status, 403);
  const external = new NextRequest("https://localhost:3000/api/v1/presenter/login", {
    method: "POST", body: "{}", headers: { Host: "demo.example", Origin: "https://demo.example" },
  });
  assert.equal((await POST(external)).status, 200);
  assert.equal(fetchMock.mock.calls.length, 2);
});

test("planning proxy allowlist preserves bounded catalog paging and rejects arbitrary queries", async (t) => {
  process.env.PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:8000";
  process.env.PP_TRUSTED_PROXY_TOKEN = "test-proxy-secret";
  t.after(() => {
    delete process.env.PANTRYPULSE_API_ORIGIN;
    delete process.env.PP_TRUSTED_PROXY_TOKEN;
  });
  const fetchMock = t.mock.method(globalThis, "fetch", async () => Response.json({ ok: true }));
  const id = "00000000-0000-0000-0000-000000000001";
  for (const path of [`scenarios/${id}`, `comparisons/${id}`, `planning-assumptions/${id}`, "planning-catalog?before=2026-10-25T00%3A00%3A00Z"]) {
    assert.equal((await GET(new Request(`http://localhost:3000/api/v1/${path}`))).status, 200);
  }
  for (const path of ["planning-catalog?organization_id=other", `scenarios/${id}?before=x`, "planning-catalog?before=x&before=y", "planning-catalog/unsafe"]) {
    assert.equal((await GET(new Request(`http://localhost:3000/api/v1/${path}`))).status, 404);
  }
  assert.equal(fetchMock.mock.calls.length, 4);
});
