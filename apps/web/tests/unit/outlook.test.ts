import { describe, expect, it } from "vitest";
import { buildOutlook, coverFor, formatMeals } from "@/app/design-lab/outlook-data";

describe("US-05 / US-08: illustrative design-lab arithmetic", () => {
  it("applies Riverbend's 80 meal proposal on Tuesday exactly once and leaves residual unmet", () => {
    const outlook = buildOutlook("riverbend", "Riverbend")!;
    expect(outlook.firstShortageDay).toBe("Tue 20");
    expect(outlook.transferDay).toBe("Tue 20");
    expect(outlook.transferQty).toBe(80);
    expect(outlook.endWithout).toBe(-120);
    expect(outlook.endWith).toBe(-40);
    expect(outlook.points.find((p) => p.day === "Mon 19")).toMatchObject({ withoutRoute: 14, withRoute: 14 });
    expect(outlook.points.find((p) => p.day === "Tue 20")).toMatchObject({ withoutRoute: -8, withRoute: 72 });
    const future = outlook.points.filter((p) => p.withoutRoute !== undefined);
    expect(future).toHaveLength(8); // shared observed/forecast anchor + 7 future days
    for (const point of future) {
      expect(point.range![0]).toBeLessThanOrEqual(point.withoutRoute!);
      expect(point.range![1]).toBeGreaterThanOrEqual(point.withoutRoute!);
      expect(point.withRoute! - point.withoutRoute!).toBe(["Sun 18", "Mon 19"].includes(point.day) ? 0 : 80);
    }
    expect(outlook.summary).toContain("ends 40 short");
  });
  it.each([
    ["oak", -90, "Thu 22"], ["cedar", 20, null], ["maple", 13, null],
    ["willow", 24, null], ["pine", 8, null],
  ])("%s has no invented transfer", (id, end, shortage) => {
    const outlook = buildOutlook(String(id), String(id))!;
    expect(outlook.endWithout).toBe(end);
    expect(outlook.firstShortageDay).toBe(shortage);
    expect(outlook.endWith).toBeNull();
    expect(outlook.transferDay).toBeNull();
    expect(outlook.transferQty).toBe(0);
    expect(outlook.points.every((p) => p.withRoute === undefined)).toBe(true);
  });
  it("hubs and unknown IDs have no beneficiary demand forecast", () => {
    for (const id of ["hub", "unknown"]) {
      expect(buildOutlook(id, id)).toBeNull();
      expect(coverFor(id)).toBeNull();
    }
  });
  it("cover fraction is bounded and is derived from seven-day mean demand", () => {
    expect(coverFor("riverbend")!.days).toBeCloseTo(40 / (160 / 7));
    expect(coverFor("cedar")!.fraction).toBe(1);
    expect(coverFor("riverbend")!.fraction).toBeCloseTo(0.25);
    expect(buildOutlook("riverbend", "Riverbend")).toEqual(buildOutlook("riverbend", "Riverbend"));
  });
  it.each([[-40, "−40"], [0, "0"], [80, "80"]])("formats a cumulative balance %s as %s", (value, label) => {
    expect(formatMeals(Number(value))).toBe(label);
  });
});
