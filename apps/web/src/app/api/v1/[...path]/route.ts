/** Thin same-origin transport. FastAPI owns authentication, validation and admission. */

function failure(code: string, status: number) {
  const requestId = crypto.randomUUID();
  return Response.json({ error: { code, message: code.toLowerCase().replaceAll("_", " "),
    details: {} }, request_id: requestId }, { status, headers: {
    "Cache-Control": "no-store", "X-Request-ID": requestId,
  } });
}

async function proxy(request: Request) {
  const incoming = new URL(request.url);
  const path = incoming.pathname.slice("/api/v1/".length);
  const uuid = "[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}";
  const allowed = request.method === "GET"
    ? ["health", "forecast-catalog", "planning-catalog", "operational-catalog", "supplies", "scenarios", "dashboard/summary", "allocation-methodology"].includes(path) ||
      new RegExp(`^(jobs|forecasts|scenarios|comparisons|planning-assumptions|receipts|supplies|plans|shortages)/${uuid}$`).test(path) ||
      new RegExp(`^inventory/sites/${uuid}/products/${uuid}$`).test(path) ||
      new RegExp(`^allocation-jobs/${uuid}/results$`).test(path) ||
      new RegExp(`^legacy-planning/(scenarios|plans|comparisons)/${uuid}$`).test(path)
    : request.method === "POST" && (["forecasts", "scenarios", "comparisons", "planning-assumptions", "presenter/login", "presenter/logout", "receipts", "supplies", "products", "imports/demand", "imports/demand/csv", "imports/donation-coverage"].includes(path) ||
      new RegExp(`^jobs/${uuid}/(retry|cancel)$`).test(path) ||
      new RegExp(`^receipts/${uuid}/(revisions|post|reconcile)$`).test(path) ||
      new RegExp(`^inventory/lots/${uuid}/declarations$`).test(path) ||
      new RegExp(`^supplies/${uuid}/confirmation$`).test(path) ||
      new RegExp(`^scenarios/${uuid}/(plans|compare-methods)$`).test(path) ||
      new RegExp(`^plans/${uuid}/review$`).test(path) ||
      new RegExp(`^inventory/sites/${uuid}/products/${uuid}/adjustments$`).test(path));
  const paging = path === "planning-catalog" && request.method === "GET" &&
    [...incoming.searchParams.keys()].every((key) => ["before", "before_id"].includes(key)) &&
    incoming.searchParams.getAll("before").length <= 1 &&
    incoming.searchParams.getAll("before_id").length <= 1;
  if (!allowed || (incoming.search && !paging)) return failure("NOT_FOUND", 404);
  const origin = request.headers.get("origin");
  // NextRequest normalizes loopback URLs to localhost and may use the server's
  // bind hostname. Host retains the browser-facing authority. Never trust a
  // client-supplied X-Forwarded-Host to change this CSRF boundary.
  let browserOrigin: string;
  try {
    // Parse a new authority so a default external port cannot retain an internal
    // server port (setting URL.host alone would preserve that port).
    browserOrigin = new URL(`${incoming.protocol}//${request.headers.get("host") ?? incoming.host}`).origin;
  } catch {
    return failure("ORIGIN_FORBIDDEN", 403);
  }
  if (request.method === "POST" && origin !== browserOrigin) {
    return failure("ORIGIN_FORBIDDEN", 403);
  }
  const base = process.env.PANTRYPULSE_API_ORIGIN;
  const proxySecret = process.env.PP_TRUSTED_PROXY_TOKEN;
  if (!base || !proxySecret) return failure("BACKEND_NOT_CONFIGURED", 503);
  let target: URL;
  try {
    target = new URL(base);
    if (!["http:", "https:"].includes(target.protocol) || target.username || target.password ||
        target.pathname !== "/" || target.search || target.hash) {
      return failure("BACKEND_NOT_CONFIGURED", 503);
    }
  } catch {
    return failure("BACKEND_NOT_CONFIGURED", 503);
  }
  const contentType = path === "imports/demand/csv" ? request.headers.get("content-type") ?? "" : "application/json";
  if (path === "imports/demand/csv" && !/^multipart\/form-data;\s*boundary=/i.test(contentType)) {
    return failure("INVALID_UPLOAD_CONTENT_TYPE", 422);
  }
  const headers = new Headers({ "Content-Type": contentType,
    "X-Forwarded-Origin": origin ?? browserOrigin, "X-PP-Proxy-Token": proxySecret });
  for (const name of ["x-csrf-token", "idempotency-key"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const cookies = (request.headers.get("cookie") ?? "").split(";")
    .map((value) => value.trim()).filter((value) => /^(pp_presenter|pp_csrf)=/.test(value));
  if (cookies.length) headers.set("cookie", cookies.join("; "));
  let body: Uint8Array | undefined;
  if (request.method === "POST") {
    const reader = request.body?.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    if (reader) {
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        size += chunk.value.byteLength;
        if (size > (path === "planning-assumptions" ? 524288 : 65536)) {
          await reader.cancel();
          return failure("INPUT_TOO_LARGE", 413);
        }
        chunks.push(chunk.value);
      }
    }
    body = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
  }
  try {
    const upstream = await fetch(`${target.origin}/api/v1/${path}${incoming.search}`, {
      method: request.method, headers, body: body as BodyInit | undefined,
      redirect: "error", cache: "no-store", signal: AbortSignal.timeout(20000),
    });
    const responseHeaders = new Headers({ "Cache-Control": "no-store" });
    for (const name of ["content-type", "location", "x-request-id", "retry-after"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    for (const cookie of upstream.headers.getSetCookie()) {
      responseHeaders.append("Set-Cookie", cookie);
    }
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return failure("BACKEND_UNAVAILABLE", 503);
  }
}

export async function GET(request: Request) { return proxy(request); }
export async function POST(request: Request) { return proxy(request); }
