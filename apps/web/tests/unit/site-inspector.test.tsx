import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { SiteInspector } from "@/components/overview/site-inspector";
import { staticFixtureSnapshot } from "@/components/overview/static-fixture";
import type { SiteProductProjection } from "@/components/overview/types";

const snapshot = staticFixtureSnapshot;
const props = {
  site: snapshot.sites[0], product: snapshot.products[0], dates: snapshot.dates, dayIndex: 0,
  renderTitle: (name: string) => <h2>{name}</h2>,
};

it.each<SiteProductProjection | undefined>([
  undefined,
  { kind: "not_evaluated", reason: "No saved run" },
  { kind: "insufficient_data", reason: "Missing observations", eligibleStockNow: null },
  { kind: "insufficient_data", reason: "Missing observations", eligibleStockNow: 0 },
])("US-04/12: unavailable demand stays distinct from covered or zero-demand data (%j)", async (projection) => {
  const user = userEvent.setup();
  render(<SiteInspector {...props} projection={projection} />);
  expect(screen.getByText("Not evaluated on Sat, Oct 24")).toBeVisible();
  if (projection?.kind === "insufficient_data") {
    expect(screen.getByText(projection.eligibleStockNow === null ? "Unknown" : "0 meals")).toBeVisible();
  }
  expect(screen.getByText("No projection, so transfers can't be assessed.", { exact: false })).toBeVisible();
  await user.click(screen.getByRole("tab", { name: "Demand" }));
  expect(screen.getByText(/No outlook for shelf-stable meals at this site:/)).toBeVisible();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("figure")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Go to Site Details" })).toBeDisabled();
});

it("US-05: zero target uses N/A, and a covered site does not suggest a transfer", () => {
  const original = snapshot.projections.riverbend["shelf-stable-meals"];
  if (original.kind !== "projected") throw new Error("Expected projection");
  render(<SiteInspector {...props} projection={{ ...original, targetUnits: Array(7).fill(0), servedUnits: Array(7).fill(0), unmetUnits: Array(7).fill(0) }} />);
  expect(screen.getByText("N/A (target is 0)")).toBeVisible();
  expect(screen.getByText("Covered on Sat, Oct 24")).toBeVisible();
  expect(screen.getByText(/No projected deficit, so no transfer is needed in this view/)).toBeVisible();
});

it("US-12: a hub has eligible supply and no beneficiary demand forecast", () => {
  const site = snapshot.sites.find((site) => site.role === "HUB")!;
  render(<SiteInspector {...props} site={site} projection={snapshot.projections[site.id]["shelf-stable-meals"]} />);
  expect(screen.getByText("Hub · source (no beneficiary status)")).toBeVisible();
  expect(screen.getByText("Not applicable: the hub has no demand forecast.")).toBeVisible();
  expect(screen.getByText(/1,020 meals now/)).toBeVisible();
});
