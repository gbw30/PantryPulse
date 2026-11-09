// covers: V1-A16
import { afterEach, expect, it, vi } from "vitest";
import { exampleUrl, networkApi } from "@/lib/network-api";

afterEach(() => vi.unstubAllGlobals());

function capture() {
  const urls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => { urls.push(url); return new Response("{}", { status: 200 }); }));
  return urls;
}

it("encodes ids taken from the page URL so they stay one path segment", async () => {
  const urls = capture();
  await networkApi.comparison("n-1", "../../settings/google-maps-key");
  await networkApi.actions("n-1", "a/b", "CLASSICAL_GP");
  expect(urls).toEqual([
    "/api/v1/networks/n-1/comparisons/..%2F..%2Fsettings%2Fgoogle-maps-key",
    "/api/v1/networks/n-1/comparisons/a%2Fb/methods/CLASSICAL_GP/actions",
  ]);
});

it("follows only a comparison result_url", async () => {
  const urls = capture();
  const good = "/api/v1/networks/8b2f4c1e-3a5d-4e6f-9a7b-1c2d3e4f5a60/comparisons/83a4b526-7091-42b3-8e4f-60718293a415";
  await networkApi.comparisonAt(good);
  expect(urls).toEqual([good]);
  await expect(networkApi.comparisonAt("/api/v1/settings/google-maps-key")).rejects.toThrow();
  expect(urls).toHaveLength(1);
});

it('refuses "." and ".." ids, which the browser would resolve to another path', async () => {
  const urls = capture();
  await expect(networkApi.backtest("..")).rejects.toThrow();
  await expect(networkApi.comparison("n-1", ".")).rejects.toThrow();
  expect(urls).toEqual([]);
});

it("an example request always names the network's mode, and an unavailable one says why (CR-w3-samples-3)", async () => {
  const urls: string[] = [];
  const unavailable = { error: { code: "TEMPLATE_EXAMPLE_UNAVAILABLE", message: "template example unavailable", details: {} }, request_id: "r-1" };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => { urls.push(url); return new Response(JSON.stringify(unavailable), { status: 404 }); }));
  expect(exampleUrl("locations", "RETAIL")).toBe("/api/v1/templates/locations.csv?kind=example&mode=RETAIL");
  expect(await networkApi.exampleUnavailableReason("locations", "RETAIL")).toBe("template example unavailable");
  expect(urls).toEqual(["/api/v1/templates/locations.csv?kind=example&mode=RETAIL"]);
});
