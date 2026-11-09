// covers: V1-A12, V1-A23
import { render, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ForecastTrustSection } from "@/components/data-explorer/backtest-summary";
import { networkApi } from "@/lib/network-api";
import { example } from "./contract-examples";

// CR-w1-web-4, mocked from the contract examples until the forecast routes ship (W4): the section reads the
// run (NetworkForecastRun), its backtest (BacktestResult, by the run's job) and the network's location names.
const network = example("NetworkList").networks[0];
const run = { ...example("NetworkForecastRun"), network_id: network.id };
const backtest = { ...example("BacktestResult"), network_id: network.id };
vi.mock("motion/react", async (load) => ({ ...(await load<typeof import("motion/react")>()), useReducedMotion: () => true }));
vi.mock("@/components/shell/network-switcher", async (load) => ({
  ...(await load<typeof import("@/components/shell/network-switcher")>()),
  useNetwork: () => ({ state: { status: "ready", networks: [network] }, network, reload: vi.fn(), select: vi.fn() }),
}));

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(networkApi, "locations").mockResolvedValue({ ...example("LocationList"), network_id: network.id });
  vi.spyOn(networkApi, "forecastRun").mockImplementation((_, id) => (id === run.forecast_run_id ? Promise.resolve(run) : new Promise(() => {})));
  vi.spyOn(networkApi, "backtest").mockImplementation((job) => (job === run.job_id ? Promise.resolve(backtest) : new Promise(() => {})));
});

it("each series shows its run's method, missing days, band and donation forecast, under the location's name", async () => {
  render(<ForecastTrustSection forecastRunId={run.forecast_run_id} />);
  const panel = await screen.findByRole("region", { name: "Forecast trust: Archer Road Pantry (P-12) · WATER-24" });
  expect(panel).toHaveTextContent("Method: Seasonal-naive baseline · no fallback");
  expect(panel).toHaveTextContent("4 missing days in the history, kept as missing (never zero)");
  expect(panel).toHaveTextContent("No band: this method gives a point forecast only.");
  // The donation series of the same location and product, over its 7 days in its own unit.
  expect(panel).toHaveTextContent("expected donations (forecast, not confirmed): 21 cases");
  expect(networkApi.backtest).toHaveBeenCalledWith(run.job_id);
  expect(within(screen.getByRole("list", { name: "Not forecast" })).getByRole("listitem")).toHaveTextContent("Eastside Pantry (P-07) · RICE-5: 9 days of history; needs 14");
});

it("accuracy by location: one row per location and unit, never pooled across units", async () => {
  render(<ForecastTrustSection forecastRunId={run.forecast_run_id} />);
  const table = await screen.findByRole("table", { name: "Accuracy by location and unit" });
  const rows = within(table).getAllByRole("row").slice(1);
  expect(rows).toHaveLength(backtest.locations.length);
  const p12 = rows.find((r) => r.textContent?.includes("Archer Road Pantry (P-12)"))!;
  expect(p12).toHaveTextContent(/case.*1 series.*off by about 18%/);
  const p07 = rows.find((r) => r.textContent?.includes("Eastside Pantry (P-07)"))!;
  expect(p07).toHaveTextContent("accuracy not evaluated: needs 35+ days");
});

it("a different forecast run never shows the previous run's accuracy while it loads", async () => {
  const { rerender } = render(<ForecastTrustSection forecastRunId={run.forecast_run_id} />);
  const label = "Forecast trust: Archer Road Pantry (P-12) · WATER-24";
  expect(await screen.findByRole("region", { name: label })).toBeVisible();

  rerender(<ForecastTrustSection forecastRunId="another-run" />);
  expect(screen.getByText("Loading forecast accuracy…")).toBeVisible();
  expect(screen.queryByRole("region", { name: label })).not.toBeInTheDocument();
});

it("a run of another network says so and shows no accuracy", async () => {
  vi.spyOn(networkApi, "forecastRun").mockResolvedValue({ ...run, network_id: "someone-else" });
  render(<ForecastTrustSection forecastRunId={run.forecast_run_id} />);
  expect(await screen.findByText("This forecast belongs to another network. Choose that network in the sidebar.")).toBeVisible();
  expect(networkApi.backtest).not.toHaveBeenCalled();
});
