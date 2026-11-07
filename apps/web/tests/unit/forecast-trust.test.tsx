// covers: V1-A12
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ForecastTrustSection } from "@/components/data-explorer/backtest-summary";
import { networkApi } from "@/lib/network-api";
import { example } from "./contract-examples";

const network = example("NetworkList").networks[0];
vi.mock("motion/react", async (load) => ({ ...(await load<typeof import("motion/react")>()), useReducedMotion: () => true }));
vi.mock("@/components/shell/network-switcher", async (load) => ({
  ...(await load<typeof import("@/components/shell/network-switcher")>()),
  useNetwork: () => ({ state: { status: "ready", networks: [network] }, network, reload: vi.fn(), select: vi.fn() }),
}));

it("a different forecast job never shows the previous job's accuracy while it loads", async () => {
  const first = { ...example("BacktestResult"), network_id: network.id };
  vi.spyOn(networkApi, "backtest").mockImplementation((id) => (id === "job-a" ? Promise.resolve(first) : new Promise(() => {})));
  const { rerender } = render(<ForecastTrustSection forecastJobId="job-a" />);
  const label = `${first.series[0].location_id} · ${first.series[0].product_id}`;
  expect((await screen.findAllByText(label)).length).toBeGreaterThan(0);

  rerender(<ForecastTrustSection forecastJobId="job-b" />);
  expect(screen.getByText("Loading forecast accuracy…")).toBeVisible();
  expect(screen.queryByText(label)).not.toBeInTheDocument();
});
