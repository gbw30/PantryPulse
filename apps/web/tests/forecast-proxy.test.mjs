import assert from "node:assert/strict";
import { test } from "node:test";
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
  assert.equal((await GET(new Request("http://localhost:3000/api/v1/admin"))).status, 404);
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
