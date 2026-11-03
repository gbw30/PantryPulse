import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { DemandOutlookChart } from "@/components/overview/demand-outlook-chart";
import { staticFixtureSnapshot } from "@/components/overview/static-fixture";

it("US-04/05/06: the chart's text/table alternative preserves units, dates and unmet quantities", async () => {
  const user = userEvent.setup();
  const snapshot = staticFixtureSnapshot;
  const projection = snapshot.projections.riverbend["shelf-stable-meals"];
  if (projection.kind !== "projected") throw new Error("Expected beneficiary projection");
  render(<DemandOutlookChart projection={projection} product={snapshot.products[0]} dates={snapshot.dates} />);
  expect(screen.getByText(/Static fixture outlook; no interval available/)).toBeVisible();
  expect(screen.getByText(/Projected unmet: 361 meals, first on Sat, Oct 24/)).toBeVisible();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Show data table" }));
  const table = screen.getByRole("table");
  expect(within(table).getAllByRole("row")).toHaveLength(8);
  const first = within(table).getAllByRole("row")[1];
  expect(within(first).getByRole("rowheader")).toHaveTextContent("Sat, Oct 24");
  expect(within(first).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["70", "10", "50", "20"]);
  expect(within(table).getByRole("columnheader", { name: "Unmet, projected (meals)" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Hide data table" })).toHaveAttribute("aria-expanded", "true");
  await user.click(screen.getByRole("button", { name: "Hide data table" }));
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("US-12: hub donation outlook never invents demand or unmet data", async () => {
  const user = userEvent.setup();
  const snapshot = staticFixtureSnapshot;
  const projection = snapshot.projections["gator-hub"]["bottled-water"];
  if (projection.kind !== "hub") throw new Error("Expected hub projection");
  render(<DemandOutlookChart projection={projection} product={snapshot.products[1]} dates={snapshot.dates} />);
  expect(screen.getByText(/Donation outlook totals 480 bottles/)).toBeVisible();
  expect(screen.getByText(/The hub has no demand forecast/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Show data table" }));
  const table = screen.getByRole("table");
  expect(within(table).getAllByRole("columnheader")).toHaveLength(2);
  expect(within(table).queryByRole("columnheader", { name: /Demand|Unmet|Served/ })).not.toBeInTheDocument();
});
