// covers: V1-A13
import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { DangerRanking } from "@/components/overview/danger-ranking";
import { example } from "./contract-examples";

const pantry = example("DangerRanking");

function retail() {
  const ranking = example("DangerRanking");
  ranking.mode = "RETAIL";
  ranking.rows[0] = { ...ranking.rows[0], reason: "expiry", score_ratio: "0.40", driving_product_id: "YOGURT-6", driving_units: 30, unit: "tray" };
  return ranking;
}

const item = (locationId: string) => screen.getByRole("listitem", { name: new RegExp(`^${locationId}\\b`) });

it("ranked rows show driving product and its units", () => {
  render(<DangerRanking ranking={pantry} />);
  const items = within(screen.getByRole("list", { name: "Locations by danger" })).getAllByRole("listitem");
  expect(items.map((li) => li.getAttribute("aria-label")?.split(",")[0])).toEqual(pantry.rows.map((r) => r.location_id));
  expect(item("P-12")).toHaveTextContent("WATER-24");
  expect(item("P-12")).toHaveTextContent("55 cases projected unmet");
  expect(item("P-12")).toHaveTextContent("62% of 7-day demand projected unmet");
  expect(item("P-12")).toHaveTextContent("first deficit Nov 8");
  expect(item("P-07")).toHaveTextContent("4 bags projected unmet");
});

it("no cross-product unit total is rendered anywhere", () => {
  const { container } = render(<DangerRanking ranking={pantry} />);
  const total = pantry.rows.reduce((sum, row) => sum + row.driving_units, 0);
  expect(container).not.toHaveTextContent(/total/i);
  expect(container.textContent).not.toMatch(new RegExp(`\\b${total}\\b`));
});

it("band has text label and shape, not color only", () => {
  render(<DangerRanking ranking={pantry} />);
  for (const [location, band] of [["P-12", "High danger"], ["P-07", "Low danger"]] as const) {
    const row = item(location);
    expect(within(row).getByText(band)).toBeVisible();
    expect(row.querySelector(`svg[data-band-shape]`)?.getAttribute("data-band-shape")).toBe(band === "High danger" ? "diamond" : "circle");
  }
  // The legend explains every band in words.
  const legend = screen.getByRole("list", { name: "Danger bands" });
  for (const band of ["High danger", "Medium danger", "Low danger"]) expect(within(legend).getByText(band)).toBeVisible();
});

it("retail shows the higher of unmet share and expiry share with its reason", () => {
  render(<DangerRanking ranking={retail()} />);
  expect(item("P-12")).toHaveTextContent("40% of stock projected to expire unsold");
  expect(item("P-12")).toHaveTextContent("Reason: stock expiring unsold (higher than the unmet-sales share)");
  expect(item("P-12")).toHaveTextContent("30 trays expiring unsold");
  expect(item("P-07")).toHaveTextContent("Reason: lost sales (higher than the expiring-stock share)");
  expect(item("P-07")).toHaveTextContent("10% of 7-day sales projected unmet");
});

it("the table alternative lists the same rows in the same order", () => {
  render(<DangerRanking ranking={pantry} view="table" />);
  const rows = within(screen.getByRole("table", { name: /Danger ranking/ })).getAllByRole("row").slice(1);
  expect(rows.map((r) => within(r).getAllByRole("cell")[0].textContent)).toEqual(pantry.rows.map((r) => r.location_id));
  expect(rows[0]).toHaveTextContent("High danger");
  expect(rows[0]).toHaveTextContent("55 cases");
});
