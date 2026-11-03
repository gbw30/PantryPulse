import { describe, expect, it } from "vitest";
import {
  firstDeficit, formatDay, formatRange, formatShortDate, formatUnits,
  markerAccessibleName, nextDeficitFrom, nextDeficitLine, roleLabel,
  statusDetail, statusFor, statusLine,
} from "@/components/overview/status";
import type { BeneficiaryProjection, SiteProductProjection } from "@/components/overview/types";

const dates = ["2026-10-24", "2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"];
const meals = { id: "meals", name: "Meals", unit: "meal", unitPlural: "meals" };
const projection: BeneficiaryProjection = {
  kind: "projected", unmetUnits: [0, 4, 0, 0, 7, 0, 0],
  targetUnits: [10, 10, 10, 10, 10, 10, 10], servedUnits: [10, 6, 10, 10, 3, 10, 10],
  demandOutlook: [10, 10, 10, 10, 10, 10, 10], donationOutlook: [0, 0, 0, 0, 0, 0, 0],
  eligibleStockNow: 59, eligibleStockAtHorizonEnd: 0, expiringLots: { count: 0, units: 0 },
};

describe("US-01 / US-05: status follows the selected date, never past deficits", () => {
  it.each([[0, "watch"], [1, "shortfall"], [2, "watch"], [4, "shortfall"], [5, "covered"], [6, "covered"]])(
    "day %i is %s", (day, status) => expect(statusFor(projection, Number(day))).toBe(status),
  );
  it("distinguishes the first-ever deficit from the next deficit", () => {
    expect(firstDeficit(projection)).toEqual({ dayIndex: 1, unmetUnits: 4 });
    expect(nextDeficitFrom(projection, 2)).toEqual({ dayIndex: 4, unmetUnits: 7 });
    expect(nextDeficitFrom(projection, 5)).toBeNull();
    expect(statusLine("watch", projection, 2, dates)).toBe("Watch · Oct 28");
    expect(statusDetail(projection, meals, dates, 2)).toBe("next deficit Wed, Oct 28: 7 meals unmet");
    expect(nextDeficitLine(projection, meals, dates, 5)).toBe("No projected deficit from Thu, Oct 29 through Fri, Oct 30");
    expect(statusDetail(projection, meals, dates, 5)).toBe("no projected deficit from Thu, Oct 29");
  });
  it("zero demand/unmet is covered", () => {
    const zero = { ...projection, unmetUnits: Array(7).fill(0) };
    expect(firstDeficit(zero)).toBeNull();
    expect(statusFor(zero, 0)).toBe("covered");
  });
  it.each<SiteProductProjection | undefined>([
    undefined,
    { kind: "not_evaluated", reason: "No run" },
    { kind: "insufficient_data", reason: "Sparse history", eligibleStockNow: null },
    { kind: "insufficient_data", reason: "Sparse history", eligibleStockNow: 0 },
  ])("missing/insufficient projections never become covered (%j)", (input) => {
    expect(statusFor(input, 0)).toBe("not_evaluated");
    expect(firstDeficit(input)).toBeNull();
    expect(nextDeficitFrom(input, 0)).toBeNull();
  });
  it("hubs stay supply-only and unknown stock stays distinct from zero", () => {
    const hub = { kind: "hub" as const, donationOutlook: Array(7).fill(0), eligibleStockNow: 1200, eligibleStockAtHorizonEnd: 1200, expiringLots: { count: 0, units: 0 } };
    expect(statusFor(hub, 6)).toBe("hub");
    expect(statusDetail(hub, meals, dates, 0)).toBe("1,200 meals eligible now");
    expect(statusDetail(undefined, meals, dates, 0)).toBe("no projection");
    expect(statusDetail({ kind: "insufficient_data", reason: "missing", eligibleStockNow: null }, meals, dates, 0)).toBe("insufficient data");
  });
});

describe("US-12: truthful units, roles and local calendar dates", () => {
  it("labels singular/plural units without combining categories", () => {
    expect(formatUnits(1, meals)).toBe("1 meal");
    expect(formatUnits(0, meals)).toBe("0 meals");
    expect(formatUnits(1200, meals)).toBe("1,200 meals");
    expect(formatUnits(2, { ...meals, unit: "bottle", unitPlural: "bottles" })).toBe("2 bottles");
  });
  it("formats month/year boundaries and DST dates as local calendar dates", () => {
    expect(formatDay("2026-11-01")).toBe("Sun, Nov 1");
    expect(formatShortDate("2026-10-24")).toBe("Oct 24");
    expect(formatRange(dates)).toBe("Oct 24–30, 2026");
    expect(formatRange(["2026-10-30", "2026-11-05"])).toBe("Oct 30–Nov 5, 2026");
    expect(formatRange(["2026-12-31", "2027-01-06"])).toBe("Dec 31–Jan 6, 2027");
  });
  it("puts role and shortage facts in the marker's accessible name", () => {
    const site = { id: "a", name: "Test Pantry", shortName: "Test", role: "BENEFICIARY" as const };
    expect(roleLabel(site)).toBe("beneficiary pantry");
    expect(roleLabel({ ...site, role: "HUB" })).toBe("distribution hub");
    expect(markerAccessibleName(site, "watch", "next deficit Oct 28")).toBe("Test Pantry, beneficiary pantry, Watch, next deficit Oct 28");
  });
});
