/** Thin same-origin proxy. FastAPI remains authoritative for sessions, scope and all work. */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const maximumBody = 4 * 1024 * 1024;
type Context = { params: Promise<{ path: string[] }> };

function applicationOrigin(request: Request, current: URL) {
  if (process.env.PP_PUBLIC_ORIGIN) return new URL(process.env.PP_PUBLIC_ORIGIN).origin;
  // NextURL normalizes loopback addresses to "localhost". Preserve the actual
  // local Host authority without trusting forwarded-origin/protocol headers.
  const host = request.headers.get("host");
  if (current.hostname === "localhost" && host) {
    try {
      const local = new URL(`${current.protocol}//${host}`);
      if (local.host === host && ["localhost", "127.0.0.1", "[::1]"].includes(local.hostname)) {
        return local.origin;
      }
    } catch { /* Invalid Host never expands the accepted origin. */ }
  }
  return current.origin;
}

function failure(status: number, code: string, message: string) {
  return Response.json({ error: { code, message, details: {} }, request_id: crypto.randomUUID() }, {
    status, headers: { "Cache-Control": "no-store" },
  });
}

async function forward(request: Request, context: Context) {
  const { path } = await context.params;
  if (path.some((part) => !part || part === "." || part === ".." || part.includes("/") || part.includes("\\"))) {
    return failure(400, "INVALID_PATH", "Invalid API path.");
  }
  const current = new URL(request.url);
  // OR-DEC-014 [PROVISIONAL]: enforce same origin before forwarding any mutation.
  if (request.method !== "GET" && request.headers.get("origin") !== applicationOrigin(request, current)) {
    return failure(403, "ORIGIN_FORBIDDEN", "Mutation requires the application origin.");
  }
  const headers = new Headers({ Accept: "application/json", "X-Request-ID": crypto.randomUUID() });
  for (const name of ["content-type", "origin", "x-csrf-token", "idempotency-key"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const cookies = (request.headers.get("cookie") ?? "").split(";").map((part) => part.trim())
    .filter((part) => part.startsWith("pp_presenter=") || part.startsWith("pp_csrf="));
  if (cookies.length) headers.set("cookie", cookies.join("; "));
  if (process.env.PP_TRUSTED_PROXY_TOKEN) headers.set("X-PP-Proxy-Token", process.env.PP_TRUSTED_PROXY_TOKEN);
  const chunks: Uint8Array[] = [];
  let received = 0;
  if (request.method !== "GET" && request.body) {
    const reader = request.body.getReader();
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      received += value.byteLength;
      if (received > maximumBody) { await reader.cancel(); return failure(413, "PAYLOAD_TOO_LARGE", "Request exceeds 4 MiB."); }
      chunks.push(value);
    }
  }
  const backend = process.env.PP_API_BASE_URL ?? process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
  const destination = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, backend);
  destination.search = current.search;
  try {
    const result = await fetch(destination, {
      method: request.method, headers, cache: "no-store", redirect: "manual",
      body: request.method === "GET" ? undefined : Buffer.concat(chunks),
      signal: AbortSignal.timeout(10_000),
    });
    const responseHeaders = new Headers({ "Cache-Control": "no-store" });
    for (const name of ["content-type", "retry-after", "x-request-id", "x-next-cursor"]) {
      const value = result.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    for (const cookie of result.headers.getSetCookie()) responseHeaders.append("Set-Cookie", cookie);
    return new Response(result.body, { status: result.status, headers: responseHeaders });
  } catch {
    return failure(503, "API_UNAVAILABLE", "The API is unavailable. Saved work can be reopened when the connection returns.");
  }
}

export const GET = forward;
export const POST = forward;
