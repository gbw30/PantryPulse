/** Thin same-origin transport. FastAPI owns authentication, validation and admission. */
import { readFile } from "node:fs/promises";

/** The proxy secret from the environment, or from the file the local install's seed generated. */
async function proxyToken() {
  const file = process.env.PP_TRUSTED_PROXY_TOKEN_FILE;
  if (process.env.PP_TRUSTED_PROXY_TOKEN || !file) return process.env.PP_TRUSTED_PROXY_TOKEN;
  return (await readFile(file, "utf8").catch(() => "")).trim() || undefined;
}

// W0-08 decision: 143 MB maximum-envelope history file plus headroom, counted while streaming.
const UPLOAD_CAP = 160 * 1024 * 1024;
const TEMPLATE_FILES = "locations|products|inventory|demand_history|routes|inbound|donation_history";
const METHODS = "NO_TRANSFERS|EQUAL_SHARE|MOST_URGENT_FIRST|CLASSICAL_GP|EGP_PI_INSPIRED|SOONEST_EXPIRY_FIRST|RETAIL_OPTIMIZED";

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
  const upload = request.method === "POST" &&
    new RegExp(`^imports/${uuid}/files/(${TEMPLATE_FILES})$`).test(path);
  const net = `networks/${uuid}`;
  const comparison = `${net}/comparisons/${uuid}/methods/(${METHODS})`;
  // v1 routes (W0-08 frozen contract); location IDs are user CSV IDs: one path segment, no encoded slash.
  const v1 = {
    GET: ["networks", "templates", "settings", `${net}`, `templates/(${TEMPLATE_FILES})\\.csv`,
      `${net}/(enrichment|routes|danger|locations|projection)`, `forecasts/${uuid}/backtest`, `${net}/comparisons/${uuid}`,
      `${comparison}/actions`],
    POST: [`${net}/enrichment/retry`, `${net}/routes/google-(preview|fetch)`,
      `${net}/(scenarios|forecasts|comparisons)`, `${comparison}/export`],
    PUT: [`${net}/locations/(?:(?!%2[fF]|%5[cC])[^/]){1,192}/attributes`, "settings/google-maps-key"],
    DELETE: ["settings/google-maps-key"],
  }[request.method] ?? [];
  const allowed = upload || v1.some((route) => new RegExp(`^${route}$`).test(path)) || (request.method === "GET"
    ? ["health", "forecast-catalog", "planning-catalog", "operational-catalog", "supplies", "scenarios", "dashboard/summary", "allocation-methodology"].includes(path) ||
      new RegExp(`^(jobs|forecasts|scenarios|comparisons|planning-assumptions|receipts|supplies|plans|shortages|imports)/${uuid}$`).test(path) ||
      new RegExp(`^inventory/sites/${uuid}/products/${uuid}$`).test(path) ||
      new RegExp(`^allocation-jobs/${uuid}/results$`).test(path) ||
      new RegExp(`^legacy-planning/(scenarios|plans|comparisons)/${uuid}$`).test(path)
    : request.method === "POST" && (["forecasts", "scenarios", "comparisons", "planning-assumptions", "presenter/login", "presenter/logout", "receipts", "supplies", "products", "imports/demand", "imports/demand/csv", "imports/donation-coverage", "imports"].includes(path) ||
      new RegExp(`^imports/${uuid}/commit$`).test(path) ||
      new RegExp(`^jobs/${uuid}/(retry|cancel)$`).test(path) ||
      new RegExp(`^receipts/${uuid}/(revisions|post|reconcile)$`).test(path) ||
      new RegExp(`^inventory/lots/${uuid}/declarations$`).test(path) ||
      new RegExp(`^supplies/${uuid}/confirmation$`).test(path) ||
      new RegExp(`^scenarios/${uuid}/(plans|compare-methods)$`).test(path) ||
      new RegExp(`^plans/${uuid}/review$`).test(path) ||
      new RegExp(`^inventory/sites/${uuid}/products/${uuid}/adjustments$`).test(path)));
  // Query keys each GET route accepts, each at most once; any other query is refused.
  const queryKeys = request.method !== "GET" ? undefined : ([
    ["planning-catalog", ["before", "before_id"]], ["templates", ["mode"]],
    [`templates/(${TEMPLATE_FILES})\\.csv`, ["kind", "mode"]], [`${net}/danger`, ["forecast_run_id"]],
    [`${net}/projection`, ["forecast_run_id", "location_id"]],
  ] as const).find(([route]) => new RegExp(`^${route}$`).test(path))?.[1] as readonly string[] | undefined;
  const keys = [...incoming.searchParams.keys()];
  const query = !incoming.search ||
    (!!queryKeys && keys.every((key) => queryKeys.includes(key)) && new Set(keys).size === keys.length);
  if (!allowed || !query) return failure("NOT_FOUND", 404);
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
  if (request.method !== "GET" && origin !== browserOrigin) {
    return failure("ORIGIN_FORBIDDEN", 403);
  }
  const base = process.env.PANTRYPULSE_API_ORIGIN;
  const proxySecret = await proxyToken();
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
  const contentType = path === "imports/demand/csv" || upload ? request.headers.get("content-type") ?? "" : "application/json";
  if (upload && !/^text\/csv\s*(;|$)/i.test(contentType)) return failure("INVALID_UPLOAD_CONTENT_TYPE", 422);
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
  let stream: ReadableStream<Uint8Array> | undefined;
  let tooLarge = false;
  if (upload) {
    // Pass the file through without buffering; the API enforces the same cap itself.
    if (Number(request.headers.get("content-length") ?? 0) > UPLOAD_CAP) return failure("INPUT_TOO_LARGE", 413);
    let size = 0;
    stream = request.body?.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, controller) {
        size += chunk.byteLength;
        if (size <= UPLOAD_CAP) return controller.enqueue(chunk);
        tooLarge = true;
        controller.error(new Error("INPUT_TOO_LARGE"));
      },
    }));
  } else if (request.method === "POST" || request.method === "PUT") {
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
      method: request.method, headers, body: (stream ?? body) as BodyInit | undefined,
      redirect: "error", cache: "no-store",
      ...(upload ? { duplex: "half" } : { signal: AbortSignal.timeout(20000) }),
    } as RequestInit & { duplex?: "half" });
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
    return tooLarge ? failure("INPUT_TOO_LARGE", 413) : failure("BACKEND_UNAVAILABLE", 503);
  }
}

export async function GET(request: Request) { return proxy(request); }
export async function POST(request: Request) { return proxy(request); }
export async function PUT(request: Request) { return proxy(request); }
export async function DELETE(request: Request) { return proxy(request); }
