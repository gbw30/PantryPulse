import { describe, expect, it } from "vitest";
import { emptyFixtureSnapshot, emptyFixtureSource, overviewSourceFor, pendingSource, staticFixtureSnapshot, staticFixtureSource, unavailableSource } from "@/components/overview/static-fixture";

describe("simulated overview adapter (not a backend forecast)", () => {
  it("exposes seven consecutive local dates, six beneficiaries, one hub and explicit units", () => {
    const snapshot = staticFixtureSnapshot;
    expect(snapshot.provenance.classification).toBe("SIMULATED");
    expect(snapshot.provenance.label).toContain("not model output");
    expect(snapshot.sites.filter((site) => site.role === "BENEFICIARY")).toHaveLength(6);
    expect(snapshot.sites.filter((site) => site.role === "HUB")).toHaveLength(1);
    expect(snapshot.products.map((product) => product.unitPlural)).toEqual(["meals", "bottles"]);
    expect(snapshot.dates).toHaveLength(7);
    for (let i = 1; i < snapshot.dates.length; i++) {
      expect(Date.parse(snapshot.dates[i]) - Date.parse(snapshot.dates[i - 1])).toBe(86_400_000);
    }
    for (const site of snapshot.sites) for (const product of snapshot.products) {
      const projection = snapshot.projections[site.id][product.id];
      if (projection.kind === "projected") {
        expect(projection.targetUnits).toHaveLength(7);
        expect(projection.donationOutlook).toHaveLength(7);
        expect(projection.servedUnits).toHaveLength(7);
        expect(projection.unmetUnits).toHaveLength(7);
        projection.targetUnits.forEach((target, day) => {
          expect(projection.servedUnits[day] + projection.unmetUnits[day]).toBe(target);
          expect(projection.servedUnits[day]).toBeGreaterThanOrEqual(0);
          expect(projection.unmetUnits[day]).toBeGreaterThanOrEqual(0);
        });
        expect(projection.eligibleStockAtHorizonEnd).toBeGreaterThanOrEqual(0);
        expect(projection.servedUnits.reduce((a, b) => a + b, 0) + projection.eligibleStockAtHorizonEnd)
          .toBeLessThanOrEqual(projection.eligibleStockNow + projection.donationOutlook.reduce((a, b) => a + b, 0));
      } else if (site.role === "HUB") expect(projection.kind).toBe("hub");
    }
  });
  it("preserves hand-derived Riverbend meals deficits and Pine Ridge's recovery", () => {
    const river = staticFixtureSnapshot.projections.riverbend["shelf-stable-meals"];
    const pine = staticFixtureSnapshot.projections["pine-ridge"]["shelf-stable-meals"];
    expect(river.kind).toBe("projected");
    if (river.kind !== "projected" || pine.kind !== "projected") throw new Error("Expected projections");
    // 40 opening + 10 morning donations - 70 demand = 20 unmet, no stock debt.
    expect(river.servedUnits[0]).toBe(50);
    expect(river.unmetUnits).toEqual([20, 57, 58, 55, 70, 51, 50]);
    expect(pine.unmetUnits).toEqual([14, 0, 0, 0, 0, 0, 0]);
    expect(staticFixtureSnapshot.projections["pine-ridge"]["bottled-water"].kind).toBe("insufficient_data");
  });
  it("an empty snapshot preserves known sites but invents no projections", async () => {
    expect(await emptyFixtureSource.load(new AbortController().signal)).toBe(emptyFixtureSnapshot);
    expect(emptyFixtureSnapshot.sites).toHaveLength(7);
    for (const products of Object.values(emptyFixtureSnapshot.projections)) {
      for (const projection of Object.values(products)) expect(projection.kind).toBe("not_evaluated");
    }
  });
  it("rejects aborted loads and exposes real adapter errors", async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(staticFixtureSource.load(controller.signal)).rejects.toHaveProperty("name", "AbortError");
    await expect(emptyFixtureSource.load(controller.signal)).rejects.toHaveProperty("name", "AbortError");
    await expect(unavailableSource.load(new AbortController().signal)).rejects.toThrow("configured to fail");
    const pendingController = new AbortController();
    const promise = pendingSource.load(pendingController.signal);
    pendingController.abort();
    await expect(promise).rejects.toHaveProperty("name", "AbortError");
  });
  it.each([undefined, "unknown", "toString", "__proto__", "constructor"])("unknown preview %s selects the honest default", (preview) => {
    expect(overviewSourceFor(preview)).toEqual({ source: staticFixtureSource, preview: null });
  });
  it.each(["empty", "loading", "unavailable"])("selects the %s preview explicitly", (preview) => {
    expect(overviewSourceFor(preview).preview).toBe(preview);
  });
});
