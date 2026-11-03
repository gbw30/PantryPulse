import { describe, expect, it } from "vitest";
import { defaultPositions, resolveAtlasLayout } from "@/components/overview/atlas-layout";
import type { Site } from "@/components/overview/types";

const site = (id: string, role: Site["role"] = "BENEFICIARY"): Site => ({ id, role, name: id, shortName: id });
const sites = [site("a"), site("b"), site("hub", "HUB")];

describe("schematic placement preserves every site without inferring geography", () => {
  it("handles empty, singleton, beneficiaries and multiple hubs", () => {
    expect(defaultPositions([]).size).toBe(0);
    expect(defaultPositions([site("hub", "HUB")]).get("hub")).toEqual({ x: 0.5, y: 0.5, source: "default" });
    const resolved = defaultPositions([...sites, site("hub2", "HUB")]);
    expect(resolved.size).toBe(4);
    expect(resolved.get("hub")!.x).toBeCloseTo(0.38);
    expect(resolved.get("hub2")!.x).toBeCloseTo(0.62);
    for (const position of resolved.values()) {
      expect(position.x).toBeGreaterThanOrEqual(0);
      expect(position.x).toBeLessThanOrEqual(1);
      expect(position.y).toBeGreaterThanOrEqual(0);
      expect(position.y).toBeLessThanOrEqual(1);
    }
  });
  it("accepts boundary coordinates and ignores unknown sites and duplicate entries", () => {
    const result = resolveAtlasLayout(sites, [
      { siteId: "a", x: 0, y: 1 }, { siteId: "a", x: 0.8, y: 0.8 },
      { siteId: "unknown", x: 0.2, y: 0.2 },
    ]);
    expect(result.size).toBe(3);
    expect(result.get("a")).toEqual({ x: 0, y: 1, source: "configured" });
    expect(result.get("b")).toEqual(defaultPositions(sites).get("b"));
  });
  it.each([-0.1, 1.1, NaN, Infinity, -Infinity])("invalid coordinate %s falls back without dropping the site", (coordinate) => {
    for (const entry of [{ siteId: "a", x: coordinate, y: 0.5 }, { siteId: "a", x: 0.5, y: coordinate }]) {
      expect(resolveAtlasLayout(sites, [entry]).get("a")).toEqual(defaultPositions(sites).get("a"));
    }
  });
  it("does not mutate supplied sites or layout entries", () => {
    const input = structuredClone(sites);
    const entries = [{ siteId: "a", x: 0.2, y: 0.3 }];
    const before = structuredClone(entries);
    resolveAtlasLayout(input, entries);
    expect(input).toEqual(sites);
    expect(entries).toEqual(before);
  });
});
