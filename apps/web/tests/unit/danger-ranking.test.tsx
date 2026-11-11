// covers: V1-A13
import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DangerRanking, DangerRankingSection } from "@/components/overview/danger-ranking";
import { DangerLegend } from "@/components/overview/risk-legend";
import { networkApi } from "@/lib/network-api";
import { example } from "./contract-examples";

const pantry = example("DangerRanking");
const runs = example("ForecastRunList");
const published = { ...runs.runs[1], forecast_run_id: pantry.forecast_run_id };
const retailNetwork = { ...example("NetworkList").networks.find((n) => n.mode === "RETAIL")!, dataset_version_id: published.dataset_version_id };
vi.mock("@/components/shell/presenter-session", async (load) => ({
  ...(await load<typeof import("@/components/shell/presenter-session")>()),
  usePresenterOptional: () => ({ state: "presenter" }),
}));
vi.mock("@/components/shell/network-switcher", async (load) => ({
  ...(await load<typeof import("@/components/shell/network-switcher")>()),
  useNetwork: () => ({ state: { status: "ready", networks: [retailNetwork] }, network: retailNetwork, reload: vi.fn(), select: vi.fn() }),
}));

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

// W4-03 #4 and D1: a location with a known 7-day target above zero gets a row even at 0% (ranking.py), so an empty
// ranking means no location could be scored (no available forecast, or one of zero), never an all-clear.
it("an empty Retail ranking says no location could be ranked, in sales and expiry terms", async () => {
  vi.spyOn(networkApi, "danger").mockResolvedValue({ ...retail(), rows: [] });
  vi.spyOn(networkApi, "locations").mockResolvedValue(example("LocationList"));
  vi.spyOn(networkApi, "forecastRuns").mockResolvedValue({ ...runs, runs: [published] });
  render(<DangerRankingSection />);
  expect(await screen.findByText("No location could be ranked: none has forecast sales above zero for the next 7 days, and no stock expiry could be projected.")).toBeVisible();
  expect(networkApi.danger).toHaveBeenCalledWith(retailNetwork.id, pantry.forecast_run_id);
  vi.restoreAllMocks();
});

it("an empty Pantry ranking says no location could be ranked, not that none runs short", async () => {
  vi.spyOn(networkApi, "danger").mockResolvedValue({ ...pantry, rows: [] });
  vi.spyOn(networkApi, "locations").mockResolvedValue(example("LocationList"));
  vi.spyOn(networkApi, "forecastRuns").mockResolvedValue({ ...runs, runs: [published] });
  render(<DangerRankingSection />);
  expect(await screen.findByText("No location could be ranked: none has forecast demand above zero for the next 7 days.")).toBeVisible();
  vi.restoreAllMocks();
});

// W4-03 #5: the API's band() puts every score under its MEDIUM threshold into "low", 0% included.
it("the low band names the API's real threshold and that it may mean nothing is short", () => {
  const ranking = readFileSync(join(__dirname, "../../../api/app/services/danger/ranking.py"), "utf8");
  const match = /^MEDIUM\s*=\s*Decimal\(\s*["']([\d.]+)["']\s*\)/m.exec(ranking);
  expect(match, 'ranking.py no longer defines MEDIUM = Decimal("…"); update this test').not.toBeNull();
  const medium = Number((Number(match![1]) * 100).toFixed(6)); // 0.07 → 7, not 7.000000000000001
  render(<DangerLegend mode="PANTRY" />);
  const low = within(screen.getByRole("list", { name: "Danger bands" })).getByText("Low danger").parentElement!;
  expect(within(low).getByText(`under ${medium}% projected short (may be none)`)).toBeVisible();
});

it("with no forecast yet, the presenter runs one from the ranking and the ranking then uses it (W4-02)", async () => {
  vi.spyOn(networkApi, "forecastRuns").mockResolvedValueOnce({ ...runs, runs: [] }).mockResolvedValue({ ...runs, runs: [published] });
  vi.spyOn(networkApi, "submitForecast").mockResolvedValue({ ...example("ForecastAccepted"), job_id: published.job_id });
  vi.spyOn(networkApi, "job").mockResolvedValue({ job_id: published.job_id, state: "SUCCEEDED", current_attempt_id: "a", attempts: [] } as never);
  vi.spyOn(networkApi, "danger").mockResolvedValue(retail());
  vi.spyOn(networkApi, "locations").mockResolvedValue(example("LocationList"));
  render(<DangerRankingSection />);
  expect(await screen.findByText("Run a forecast for this network to rank its locations by danger.")).toBeVisible();
  expect(networkApi.danger).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Run forecast" }));
  expect(await screen.findByRole("list", { name: "Locations by danger" })).toBeVisible();
  expect(networkApi.submitForecast).toHaveBeenCalledWith(retailNetwork.id, { dataset_version_id: published.dataset_version_id });
  expect(networkApi.danger).toHaveBeenCalledWith(retailNetwork.id, pantry.forecast_run_id);
  expect(screen.getByText("Forecast finished. The views below use the new run.")).toBeVisible();
  vi.restoreAllMocks();
});
