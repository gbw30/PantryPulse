// covers: V1-A14
import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { pluralize } from "@/components/data-explorer/format";
import { ScenarioLab } from "@/components/scenario-lab/scenario-lab";
import { planningApi } from "@/lib/planning-api";
import { example } from "./contract-examples";

// W3 lead decision (2026-11-09): with a v1 network chosen, /scenarios shows only the v1 method comparison;
// the legacy "Scenario builder" stays for the view with no v1 network, as the overview does.
vi.mock("@/components/shell/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main>,
  ShellProviders: ({ children }: { children: ReactNode }) => children }));
vi.mock("@/components/scenario-lab/v1-comparison", () => ({
  MethodComparisonSection: () => <p>v1 comparison</p> }));
vi.mock("@/components/shell/presenter-session", async (load) => ({ ...(await load<typeof import("@/components/shell/presenter-session")>()),
  usePresenter: () => ({ state: "visitor", signIn: vi.fn(), signOut: vi.fn(), expired: vi.fn() }) }));
type NetworkValue = Pick<ReturnType<typeof import("@/components/shell/network-switcher").useNetwork>, "state" | "network">;
let networks: NetworkValue = { state: { status: "signed_out" }, network: null };
vi.mock("@/components/shell/network-switcher", async (load) => ({
  ...(await load<typeof import("@/components/shell/network-switcher")>()),
  useNetwork: () => ({ ...networks, reload: vi.fn(), select: vi.fn() }),
}));

beforeEach(() => { vi.spyOn(planningApi, "planningCatalog").mockReturnValue(new Promise(() => {})); });
afterEach(() => {
  vi.restoreAllMocks();
  networks = { state: { status: "signed_out" }, network: null };
});

it("a chosen v1 network shows only its method comparison: no legacy builder and no legacy load", async () => {
  const network = example("NetworkList").networks[0];
  networks = { state: { status: "ready", networks: [network] }, network };
  render(<ScenarioLab />);
  expect(screen.getByRole("heading", { level: 1, name: "Scenario Lab" })).toBeVisible();
  expect(screen.getByText("v1 comparison")).toBeVisible();
  expect(screen.queryByRole("form", { name: "Scenario builder" })).not.toBeInTheDocument();
  expect(screen.queryByText("Saved comparison")).not.toBeInTheDocument();
  expect(planningApi.planningCatalog).not.toHaveBeenCalled();
});

it("with no v1 network, the legacy builder stays and no v1 comparison is shown", async () => {
  networks = { state: { status: "ready", networks: [] }, network: null };
  render(<ScenarioLab />);
  expect(await screen.findByRole("form", { name: "Scenario builder" })).toBeInTheDocument();
  expect(screen.queryByText(/^v1 comparison/)).not.toBeInTheDocument();
});

it("while the networks load, neither builder is shown", () => {
  networks = { state: { status: "loading" }, network: null };
  render(<ScenarioLab />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading networks…");
  expect(screen.queryByRole("form", { name: "Scenario builder" })).not.toBeInTheDocument();
  expect(screen.queryByText(/^v1 comparison/)).not.toBeInTheDocument();
});

// W5-SC01 (W4-03 ux-critic note): the builder's unit headers (wizard.tsx) and the Data Explorer's product
// names use this plural. "boxs" read as a typo.
it("pluralize writes -es after s-like endings, -ies after a consonant y, keeps each and an existing plural", () => {
  const cases = { oz: "oz", g: "g", kg: "kg", ml: "ml", box: "boxes", bunch: "bunches", dish: "dishes", glass: "glasses", case: "cases", bottle: "bottles",
    berry: "berries", tray: "trays", each: "each", lbs: "lbs", meals: "meals" };
  expect(Object.fromEntries(Object.keys(cases).map((unit) => [unit, pluralize(unit)]))).toEqual(cases);
});
