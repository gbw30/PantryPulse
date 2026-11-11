// covers: V1-A23
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ForecastTrustSection } from "@/components/data-explorer/backtest-summary";
import { DangerRankingSection } from "@/components/overview/danger-ranking";
import { networkApi, type Network } from "@/lib/network-api";
import { example } from "./contract-examples";

let current: Network = example("NetworkList").networks[0];
vi.mock("motion/react", async (load) => ({ ...(await load<typeof import("motion/react")>()), useReducedMotion: () => true }));
vi.mock("@/components/shell/network-switcher", async (load) => ({
  ...(await load<typeof import("@/components/shell/network-switcher")>()),
  useNetwork: () => ({ state: { status: "ready", networks: [current] }, network: current, reload: vi.fn(), select: vi.fn() }),
}));

const never = <T,>() => new Promise<T>(() => {});
beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(networkApi, "forecastRuns").mockImplementation(never);
  vi.spyOn(networkApi, "backtest").mockImplementation(never);
  vi.spyOn(networkApi, "forecastRun").mockImplementation(never);
  vi.spyOn(networkApi, "danger").mockImplementation(never);
  vi.spyOn(networkApi, "locations").mockImplementation(never);
});

const views = () => render(<><DangerRankingSection /><ForecastTrustSection /></>);

it("the atlas and forecast views say when the network has no inbound.csv", () => {
  current = { ...example("NetworkList").networks[0], inbound_file_provided: false };
  views();
  expect(screen.getAllByText(/no scheduled deliveries provided/)).toHaveLength(2);
});

it("no note when inbound.csv was provided, or when there is no dataset yet (null): nothing is guessed", () => {
  for (const inbound of [true, null]) {
    current = { ...example("NetworkList").networks[0], inbound_file_provided: inbound };
    const { unmount } = views();
    expect(screen.queryByText(/no scheduled deliveries provided/)).not.toBeInTheDocument();
    unmount();
  }
});
