// W0-08 open risk: does the real Next standalone server stream a v1 import upload through the
// proxy, or buffer it first? Streams 150 MiB at 20 MiB/s (S4's rate) through the proxy to a
// byte-counting sink. Buffering shows as the sink's first byte arriving only after the client has
// sent everything, and as server RSS growing with the body. Linux only (reads /proc).
// Usage (repo root): NEXT_OUTPUT=standalone npm run build --workspace @pantrypulse/web
//                    node apps/web/scripts/check-upload-streaming.mjs
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { createServer } from "node:http";
import { setTimeout as sleep } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const MiB = 1024 * 1024;
const TOTAL = 150 * MiB;
const LIMIT_GROWTH = 64 * MiB;
const server = fileURLToPath(new URL("../.next/standalone/apps/web/server.js", import.meta.url));

const rss = (pid) => Number(/VmRSS:\s+(\d+)/.exec(readFileSync(`/proc/${pid}/status`, "utf8"))[1]) * 1024;

let received = 0;
let sent = 0;
let sentAtFirstByte = null;
const sink = createServer((request, response) => {
  request.on("data", (chunk) => { sentAtFirstByte ??= sent; received += chunk.length; });
  request.on("end", () => response.end(JSON.stringify({ bytes: received })));
});
await new Promise((resolve) => sink.listen(0, "127.0.0.1", resolve));

const port = 3990;
const child = spawn(process.execPath, [server], { stdio: "ignore", env: { ...process.env,
  PORT: String(port), HOSTNAME: "127.0.0.1",
  PANTRYPULSE_API_ORIGIN: `http://127.0.0.1:${sink.address().port}`, PP_TRUSTED_PROXY_TOKEN: "check-only" } });
try {
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; ; i++) {
    if (await fetch(`${base}/api/v1/health`).then(() => true, () => false)) break;
    if (i > 100) throw new Error("standalone server did not start");
    await sleep(200);
  }
  await sleep(500);
  const idle = rss(child.pid);
  let peak = idle;
  const sampler = setInterval(() => { peak = Math.max(peak, rss(child.pid)); }, 25);
  const body = new ReadableStream({ async pull(controller) {
    if (sent >= TOTAL) return controller.close();
    await sleep(50);
    sent += MiB;
    controller.enqueue(new Uint8Array(MiB).fill(97));
  } });
  const started = performance.now();
  const response = await fetch(`${base}/api/v1/imports/33333333-3333-4333-8333-333333333333/files/demand_history`, {
    method: "POST", duplex: "half", body,
    headers: { Origin: base, "Content-Type": "text/csv" },
  });
  const seconds = (performance.now() - started) / 1000;
  clearInterval(sampler);
  const result = { status: response.status, sent, received, sent_mib_at_first_byte: sentAtFirstByte / MiB, seconds: Number(seconds.toFixed(2)),
    idle_mib: Number((idle / MiB).toFixed(1)), peak_mib: Number((peak / MiB).toFixed(1)),
    growth_mib: Number(((peak - idle) / MiB).toFixed(1)), limit_growth_mib: LIMIT_GROWTH / MiB };
  console.log(JSON.stringify(result));
  const ok = response.status === 200 && received === TOTAL && sentAtFirstByte < TOTAL / 2 &&
    peak - idle < LIMIT_GROWTH;
  process.exitCode = ok ? 0 : 1;
} finally {
  child.kill();
  sink.close();
}
