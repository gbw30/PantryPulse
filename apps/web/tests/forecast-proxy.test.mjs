import { NextRequest } from "next/server.js";
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

test("inventory snapshot GET forwards only its exact allowlisted route", async (t) => {
  process.env.PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:8000";
  process.env.PP_TRUSTED_PROXY_TOKEN = "test-proxy-secret";
  t.after(() => {
    delete process.env.PANTRYPULSE_API_ORIGIN;
    delete process.env.PP_TRUSTED_PROXY_TOKEN;
  });
  const path = "/api/v1/inventory/sites/11111111-1111-4111-8111-111111111111/products/22222222-2222-4222-8222-222222222222";
  const fetchMock = t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, `http://127.0.0.1:8000${path}`);
    assert.equal(options.method, "GET");
    assert.equal(options.headers.get("cookie"), "pp_presenter=opaque");
    return Response.json({ usable_quantity: "12" });
  });
  const response = await GET(new Request(`http://localhost:3000${path}`, {
    headers: { Cookie: "pp_presenter=opaque; unrelated=never-forward" },
  }));
  assert.equal(response.status, 200);
  assert.equal((await response.json()).usable_quantity, "12");
  assert.equal((await GET(new Request(`http://localhost:3000${path}?organization_id=spoof`))).status, 404);
  assert.equal((await POST(new Request(`http://localhost:3000${path}`, { method: "POST" }))).status, 404);
  assert.equal(fetchMock.mock.calls.length, 1);
});

test("stock adjustment proxy forwards command headers and rejects wrong origin", async (t) => {
  process.env.PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:8000";
  process.env.PP_TRUSTED_PROXY_TOKEN = "test-proxy-secret";
  t.after(() => {
    delete process.env.PANTRYPULSE_API_ORIGIN;
    delete process.env.PP_TRUSTED_PROXY_TOKEN;
  });
  const path = "/api/v1/inventory/sites/11111111-1111-4111-8111-111111111111/products/22222222-2222-4222-8222-222222222222/adjustments";
  const fetchMock = t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, `http://127.0.0.1:8000${path}`);
    assert.equal(options.method, "POST");
    assert.equal(options.headers.get("x-csrf-token"), "csrf");
    assert.equal(options.headers.get("idempotency-key"), "physical-count-001");
    assert.equal(options.headers.get("cookie"), "pp_presenter=opaque");
    return Response.json({ status: "APPLIED" });
  });
  const response = await POST(new Request(`http://localhost:3000${path}`, {
    method: "POST", body: "{}", headers: {
      Origin: "http://localhost:3000", "X-CSRF-Token": "csrf",
      "Idempotency-Key": "physical-count-001", Cookie: "pp_presenter=opaque",
    },
  }));
  assert.equal(response.status, 200);
  assert.equal((await POST(new Request(`http://localhost:3000${path}`, {
    method: "POST", headers: { Origin: "https://evil.example" },
  }))).status, 403);
  assert.equal((await GET(new Request(`http://localhost:3000${path}`))).status, 404);
  assert.equal(fetchMock.mock.calls.length, 1);
});

test("CSV import proxy preserves multipart boundary and rejects JSON uploads", async (t) => {
  process.env.PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:8000";
  process.env.PP_TRUSTED_PROXY_TOKEN = "test-proxy-secret";
  t.after(() => {
    delete process.env.PANTRYPULSE_API_ORIGIN;
    delete process.env.PP_TRUSTED_PROXY_TOKEN;
  });
  const fetchMock = t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "http://127.0.0.1:8000/api/v1/imports/demand/csv");
    assert.match(options.headers.get("content-type"), /^multipart\/form-data; boundary=/);
    assert.match(new TextDecoder().decode(options.body), /history.csv/);
    assert.equal(options.headers.get("x-csrf-token"), "csrf");
    return Response.json({ operation: "demand-import" }, { status: 201 });
  });
  const form = new FormData();
  form.set("source_id", "11111111-1111-4111-8111-111111111111");
  form.set("file", new Blob(["day,requested\n2026-10-24,10\n"]), "history.csv");
  const url = "http://localhost:3000/api/v1/imports/demand/csv";
  assert.equal((await POST(new Request(url, { method: "POST", body: form, headers: {
    Origin: "http://localhost:3000", "X-CSRF-Token": "csrf", "Idempotency-Key": "import-001",
  } }))).status, 201);
  assert.equal((await POST(new Request(url, { method: "POST", body: "{}", headers: {
    Origin: "http://localhost:3000", "Content-Type": "application/json",
  } }))).status, 422);
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
