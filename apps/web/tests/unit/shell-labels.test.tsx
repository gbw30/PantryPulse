// covers: V1-A05
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { PresenterFooter } from "@/components/shell/presenter-footer";
import { TopBar } from "@/components/shell/top-bar";
import { useNetwork } from "@/components/shell/network-switcher";
import { example } from "./contract-examples";

// W2-06 carry-ins: no "simulated" wording on a real import (pill, session footer); the pill stays
// only for samples (Network.is_sample); the header shows the snapshot's as_of_date, not today.

vi.mock("@/components/ui/sidebar", () => ({ useSidebar: () => ({ toggleSidebar: vi.fn() }) }));
vi.mock("@/components/shell/presenter-session", () => ({ usePresenter: () => ({ state: "presenter", signIn: vi.fn(), signOut: vi.fn() }), signInMessage: () => "" }));
vi.mock("@/components/shell/network-switcher", async (load) => ({
  ...(await load<typeof import("@/components/shell/network-switcher")>()), useNetwork: vi.fn(),
}));

type Ctx = ReturnType<typeof useNetwork>;
const imported = example("Network"); // is_sample false, as_of_date 2026-11-05
const ready = (network: Ctx["network"]): Ctx =>
  ({ state: { status: "ready", networks: network ? [network] : [] }, network, select: vi.fn(), reload: vi.fn() });

beforeEach(() => vi.mocked(useNetwork).mockReset());

it("a real imported network shows its snapshot date and no simulated pill", () => {
  vi.mocked(useNetwork).mockReturnValue(ready(imported));
  render(<TopBar />);
  const banner = screen.getByRole("banner");
  expect(banner).toHaveTextContent("Snapshot Nov 5, 2026");
  expect(banner).not.toHaveTextContent(/simulated|sample/i);
});

it("a sample network keeps the pill, labeled as fictional sample data", () => {
  vi.mocked(useNetwork).mockReturnValue(ready({ ...imported, is_sample: true }));
  render(<TopBar />);
  expect(screen.getByRole("banner")).toHaveTextContent("Sample data — fictional");
  expect(screen.getByRole("banner")).toHaveTextContent("Snapshot Nov 5, 2026");
});

it("with no v1 network chosen, the legacy demo keeps its simulated pill and shows no snapshot date", () => {
  vi.mocked(useNetwork).mockReturnValue({ state: { status: "signed_out" }, network: null, select: vi.fn(), reload: vi.fn() });
  render(<TopBar />);
  expect(screen.getByRole("banner")).toHaveTextContent("Simulated network");
  expect(screen.getByRole("banner")).not.toHaveTextContent(/Snapshot/);
});

it("while networks load, neither pill nor date is guessed", () => {
  vi.mocked(useNetwork).mockReturnValue({ state: { status: "loading" }, network: null, select: vi.fn(), reload: vi.fn() });
  render(<TopBar />);
  expect(screen.getByRole("banner")).not.toHaveTextContent(/simulated|sample|Snapshot/i);
});

it("the session footer names the session without calling the data simulated", () => {
  render(<PresenterFooter />);
  expect(screen.getByText("Presenter session")).toBeVisible();
  expect(document.body).not.toHaveTextContent(/simulated/i);
});

// Lead decision (2026-11-09): the pill marks the legacy fixture data, so screens that show none
// (/import, /settings) carry no pill; a failed network list says so, and legacy screens keep the pill.
it("on /import and /settings, which show no network data, there is no simulated pill", () => {
  vi.mocked(useNetwork).mockReturnValue(ready(null));
  for (const active of ["import", "settings"] as const) {
    const { unmount } = render(<TopBar active={active} />);
    expect(screen.getByRole("banner")).not.toHaveTextContent(/simulated/i);
    unmount();
  }
  render(<TopBar active="overview" />);
  expect(screen.getByRole("banner")).toHaveTextContent("Simulated network");
});

it("a network list that failed to load says so; a screen showing the legacy demo still calls it simulated", () => {
  vi.mocked(useNetwork).mockReturnValue({ state: { status: "error", code: "REQUEST_FAILED" }, network: null, select: vi.fn(), reload: vi.fn() });
  const { unmount } = render(<TopBar active="overview" />);
  expect(screen.getByRole("banner")).toHaveTextContent("Network list unavailable");
  expect(screen.getByRole("banner")).toHaveTextContent("Simulated network");
  unmount();
  render(<TopBar active="import" />);
  expect(screen.getByRole("banner")).toHaveTextContent("Network list unavailable");
  expect(screen.getByRole("banner")).not.toHaveTextContent(/simulated/i);
});

// L1 (review of #129): /data and /recommendations render the legacy fixture data whatever network is chosen,
// so they say "Simulated network" in every network state, never the chosen network's own label.
it("a screen that always renders the legacy demo says simulated whatever network is chosen", () => {
  const states: Ctx[] = [ready(imported), ready({ ...imported, is_sample: true }), ready(null),
    { state: { status: "loading" }, network: null, select: vi.fn(), reload: vi.fn() }];
  for (const active of ["data", "recommendations"] as const) {
    for (const ctx of states) {
      vi.mocked(useNetwork).mockReturnValue(ctx);
      const { unmount } = render(<TopBar active={active} />);
      expect(screen.getByRole("banner")).toHaveTextContent("Simulated network");
      expect(screen.getByRole("banner")).not.toHaveTextContent("Sample data");
      unmount();
    }
  }
});

// W4-03 #1: the Data dashboard also renders the chosen network's forecast trust, so its top bar labels that network
// (sample data, or nothing for a real import); the legacy block below labels itself "Simulated network".
it("a legacy screen that also shows the chosen network's data labels that network, not the legacy demo", () => {
  vi.mocked(useNetwork).mockReturnValue(ready(imported));
  const { unmount } = render(<TopBar active="data" legacyOnly={false} />);
  expect(screen.getByRole("banner")).not.toHaveTextContent(/simulated|sample/i);
  unmount();
  vi.mocked(useNetwork).mockReturnValue(ready({ ...imported, is_sample: true }));
  render(<TopBar active="data" legacyOnly={false} />);
  expect(screen.getByRole("banner")).toHaveTextContent("Sample data — fictional");
  expect(screen.getByRole("banner")).not.toHaveTextContent(/simulated/i);
});
