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

test("local install reads the proxy token from the shared file, never the client", async (t) => {
  const { mkdtemp, writeFile, rm } = await import("node:fs/promises");
  const { join } = await import("node:path");
  const { tmpdir } = await import("node:os");
  const dir = await mkdtemp(join(tmpdir(), "pp-proxy-token-"));
  const file = join(dir, "proxy-token");
  await writeFile(file, "file-proxy-secret\n");
  process.env.PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:8000";
  process.env.PP_TRUSTED_PROXY_TOKEN_FILE = file;
  t.after(async () => {
    delete process.env.PANTRYPULSE_API_ORIGIN;
    delete process.env.PP_TRUSTED_PROXY_TOKEN_FILE;
    await rm(dir, { recursive: true, force: true });
  });
  const fetchMock = t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(options.headers.get("x-pp-proxy-token"), "file-proxy-secret");
    return Response.json({ status: "ok" });
  });
  const request = () => GET(new Request("http://localhost:3000/api/v1/health", {
    headers: { "X-PP-Proxy-Token": "spoof" },
  }));
  assert.equal((await request()).status, 200);
  await rm(file);
  assert.equal((await request()).status, 503);
  assert.equal(fetchMock.mock.calls.length, 1);
});

const importId = "33333333-3333-4333-8333-333333333333";
const MiB = 1024 * 1024;

function chunks(total, size = MiB) {
  let sent = 0;
  return new ReadableStream({ pull(controller) {
    if (sent >= total) return controller.close();
    const length = Math.min(size, total - sent);
    sent += length;
    controller.enqueue(new Uint8Array(length).fill(97));
  } });
}

function upload(body, headers = {}) {
  return new Request(`http://localhost:3000/api/v1/imports/${importId}/files/demand_history`, {
    method: "POST", body, duplex: "half",
    headers: { Origin: "http://localhost:3000", "Content-Type": "text/csv", "X-CSRF-Token": "csrf", ...headers },
  });
}

test("v1 import file upload streams past the 64 KB JSON cap with no timeout", async (t) => {
  process.env.PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:8000";
  process.env.PP_TRUSTED_PROXY_TOKEN = "test-proxy-secret";
  t.after(() => {
    delete process.env.PANTRYPULSE_API_ORIGIN;
    delete process.env.PP_TRUSTED_PROXY_TOKEN;
  });
  const fetchMock = t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, `http://127.0.0.1:8000/api/v1/imports/${importId}/files/demand_history`);
    assert.ok(options.body instanceof ReadableStream, "body is passed through as a stream");
    assert.equal(options.duplex, "half");
    assert.equal(options.signal, undefined, "no 20 s timeout on uploads");
    assert.equal(options.headers.get("content-type"), "text/csv");
    assert.equal(options.headers.get("x-csrf-token"), "csrf");
    let bytes = 0;
    for await (const chunk of options.body) bytes += chunk.byteLength;
    return Response.json({ name: "demand_history", bytes }, { status: 200 });
  });
  const response = await POST(upload(chunks(3 * MiB)));
  assert.equal(response.status, 200);
  assert.equal((await response.json()).bytes, 3 * MiB);
  assert.equal(fetchMock.mock.calls.length, 1);
});

test("v1 import file upload enforces the 160 MiB cap while streaming", async (t) => {
  process.env.PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:8000";
  process.env.PP_TRUSTED_PROXY_TOKEN = "test-proxy-secret";
  t.after(() => {
    delete process.env.PANTRYPULSE_API_ORIGIN;
    delete process.env.PP_TRUSTED_PROXY_TOKEN;
  });
  t.mock.method(globalThis, "fetch", async (_url, options) => {
    const reader = options.body.getReader();
    while (!(await reader.read()).done) { /* drain until the proxy errors the stream */ }
    return Response.json({}, { status: 200 });
  });
  const response = await POST(upload(chunks(160 * MiB + 1)));
  assert.equal(response.status, 413);
  assert.equal((await response.json()).error.code, "INPUT_TOO_LARGE");
  assert.equal((await POST(upload("x", { "Content-Length": String(160 * MiB + 1) }))).status, 413);
});

test("v1 import routes: only template names, only CSV bodies, plus create/commit/status", async (t) => {
  process.env.PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:8000";
  process.env.PP_TRUSTED_PROXY_TOKEN = "test-proxy-secret";
  t.after(() => {
    delete process.env.PANTRYPULSE_API_ORIGIN;
    delete process.env.PP_TRUSTED_PROXY_TOKEN;
  });
  const seen = [];
  t.mock.method(globalThis, "fetch", async (url) => {
    seen.push(url.slice("http://127.0.0.1:8000/api/v1/".length));
    return Response.json({}, { status: 200 });
  });
  const post = (path, body = "{}") => POST(new Request(`http://localhost:3000/api/v1/${path}`, {
    method: "POST", body, headers: { Origin: "http://localhost:3000" },
  }));
  assert.equal((await POST(upload("a,b\n", { "Content-Type": "application/json" }))).status, 422);
  assert.equal((await post(`imports/${importId}/files/secrets`, "x")).status, 404);
  assert.equal((await post("imports")).status, 200);
  assert.equal((await post(`imports/${importId}/commit`)).status, 200);
  assert.equal((await GET(new Request(`http://localhost:3000/api/v1/imports/${importId}`))).status, 200);
  assert.deepEqual(seen, ["imports", `imports/${importId}/commit`, `imports/${importId}`]);
});

test("every v1 route is forwarded; neighbours and stray queries are not", async (t) => {
  process.env.PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:8000";
  process.env.PP_TRUSTED_PROXY_TOKEN = "test-proxy-secret";
  t.after(() => {
    delete process.env.PANTRYPULSE_API_ORIGIN;
    delete process.env.PP_TRUSTED_PROXY_TOKEN;
  });
  const { PUT, DELETE } = await import("../src/app/api/v1/[...path]/route.ts");
  const handlers = { GET, POST, PUT, DELETE };
  const seen = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    seen.push(`${options.method} ${url.slice("http://127.0.0.1:8000/api/v1/".length)}`);
    return Response.json({}, { status: 200 });
  });
  const net = "44444444-4444-4444-8444-444444444444";
  const cmp = "55555555-5555-4555-8555-555555555555";
  const run = "66666666-6666-4666-8666-666666666666";
  const forwarded = [
    "GET networks", `GET networks/${net}`, "GET templates", "GET templates?mode=RETAIL",
    "GET templates/locations.csv?kind=example", `GET networks/${net}/enrichment`,
    `GET networks/${net}/routes`, "GET settings", `GET networks/${net}/danger?forecast_run_id=${run}`,
    `GET forecasts/${run}/backtest`, `GET networks/${net}/comparisons/${cmp}`,
    `GET networks/${net}/comparisons/${cmp}/methods/EQUAL_SHARE/actions`,
    `POST networks/${net}/enrichment/retry`, `POST networks/${net}/routes/google-preview`,
    `POST networks/${net}/routes/google-fetch`, `POST networks/${net}/scenarios`,
    `POST networks/${net}/forecasts`, `POST networks/${net}/comparisons`,
    `POST networks/${net}/comparisons/${cmp}/methods/RETAIL_OPTIMIZED/export`,
    `PUT networks/${net}/locations/Store%2012/attributes`, "PUT settings/google-maps-key",
    "DELETE settings/google-maps-key",
  ];
  const call = (route) => {
    const [method, path] = route.split(" ");
    return handlers[method](new Request(`http://localhost:3000/api/v1/${path}`, {
      method, headers: { Origin: "http://localhost:3000" },
      ...(["POST", "PUT"].includes(method) ? { body: "{}" } : {}),
    }));
  };
  for (const route of forwarded) assert.equal((await call(route)).status, 200, route);
  assert.deepEqual(seen, forwarded);
  for (const route of [
    "GET networks?organization_id=spoof", "GET templates/secrets.csv", `GET templates?mode=A&mode=B`,
    `GET networks/${net}/comparisons/${cmp}/methods/DROP_TABLES/actions`, "DELETE networks",
    `PUT networks/${net}`, "POST settings", `PUT networks/${net}/locations/a%2Fb/attributes`,
  ]) assert.equal((await call(route)).status, 404, route);
  const evil = await PUT(new Request("http://localhost:3000/api/v1/settings/google-maps-key", {
    method: "PUT", body: "{}", headers: { Origin: "https://evil.example" },
  }));
  assert.equal(evil.status, 403);
  assert.equal(seen.length, forwarded.length);
});
