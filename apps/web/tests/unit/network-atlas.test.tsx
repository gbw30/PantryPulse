// covers: V1-A21
import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { NetworkAtlas } from "@/components/overview/network-atlas";
import { example } from "./contract-examples";

// Isolate the state switch; the real shell, ranking and keyboard run in E2E.
vi.mock("@/components/shell/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main>,
  ShellProviders: ({ children }: { children: ReactNode }) => children }));
// The mocked shell has no NetworkProvider; the v1 danger ranking has its own tests (danger-ranking.test.tsx).
vi.mock("@/components/overview/danger-ranking", async (load) => ({ ...(await load<typeof import("@/components/overview/danger-ranking")>()),
  // It renders the page header it is given beside its presenter controls (W5-UI02.5).
  DangerRankingSection: ({ header }: { header?: ReactNode }) => <>{header}<p>v1 danger ranking</p></> }));
type NetworkValue = Pick<ReturnType<typeof import("@/components/shell/network-switcher").useNetwork>, "state" | "network">;
let networks: NetworkValue = { state: { status: "signed_out" }, network: null };
vi.mock("@/components/shell/network-switcher", async (load) => ({
  ...(await load<typeof import("@/components/shell/network-switcher")>()),
  useNetwork: () => ({ ...networks, reload: vi.fn(), select: vi.fn() }),
}));

afterEach(() => {
  networks = { state: { status: "signed_out" }, network: null };
});

it("W2-06 carry-in: a chosen v1 network shows its own ranking, never simulated wording", () => {
  const network = example("NetworkList").networks.find((n) => !n.is_sample)!;
  networks = { state: { status: "ready", networks: [network] }, network };
  render(<NetworkAtlas />);
  expect(screen.getByRole("heading", { level: 1, name: "Network Atlas" })).toBeVisible();
  expect(screen.getByText("v1 danger ranking")).toBeVisible();
  expect(document.body).not.toHaveTextContent(/simulated/i);
  expect(document.body).toHaveTextContent(network.name);
});

it("while the networks load, no ranking is shown", () => {
  networks = { state: { status: "loading" }, network: null };
  render(<NetworkAtlas />);
  expect(screen.queryByText(/v1 danger ranking/)).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Loading networks…");
});
