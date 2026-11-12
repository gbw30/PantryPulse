// covers: V1-A16
import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { DecisionsView } from "@/components/decisions/decisions-view";
import { PrintPlan } from "@/components/decisions/print-plan";
import { periodText, planCovers } from "@/components/decisions/action-card";
import { networkApi } from "@/lib/network-api";
import { ApiError } from "@/lib/planning-api";
import { example, type Schemas } from "./contract-examples";

// W4 web fixes (code-review #8 and #7): an unverified method keeps its reason on Decisions and its print
// page, and a large selection reaches the print page without putting action ids in the URL.
const saved = example("SavedComparisonV3");
const network = example("NetworkList").networks.find((n) => n.id === saved.network_id)!;
const egp = saved.result.methods.find((m) => m.method === "EGP_PI_INSPIRED")!;
const NO_PLAN = "EGP-PI-inspired has no verified plan in this comparison, so there are no suggested actions.";

vi.mock("@/components/shell/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
vi.mock("@/components/shell/network-switcher", async (load) => ({
  ...(await load<typeof import("@/components/shell/network-switcher")>()),
  useNetwork: () => ({ state: { status: "ready", networks: [network] }, network, reload: vi.fn(), select: vi.fn() }),
}));

beforeEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
  vi.spyOn(networkApi, "comparison").mockResolvedValue(saved);
  vi.spyOn(networkApi, "get").mockResolvedValue(network);
});

/** `n` actions with real-shaped ids: "t-" plus 20 hex characters. */
function actions(n: number): Schemas["DecisionActions"] {
  const d = example("DecisionActions");
  const [first] = d.actions;
  d.actions = Array.from({ length: n }, (_, i) => ({ ...first, id: `t-${i.toString(16).padStart(20, "0")}` }));
  return d;
}

it("an unverified method shows why it has no plan, with its solver status, although its actions answer 409", async () => {
  vi.spyOn(networkApi, "actions").mockRejectedValue(new ApiError("RESULT_NOT_VERIFIED", 409));
  render(<DecisionsView comparisonId={saved.id} method="EGP_PI_INSPIRED" />);
  const section = screen.getByRole("region", { name: `Suggested actions · ${network.name}` });
  await waitFor(() => expect(section).toHaveTextContent(NO_PLAN));
  expect(section).toHaveTextContent(egp.failure_reason!);
  expect(section).toHaveTextContent(`Solver status: ${egp.native_status} (native)`);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Export CSV/ })).not.toBeInTheDocument();
});

it("a method that is not in the comparison says so, not that the comparison is missing", async () => {
  vi.spyOn(networkApi, "actions").mockRejectedValue(new ApiError("METHOD_NOT_IN_COMPARISON", 404));
  render(<DecisionsView comparisonId={saved.id} method="EQUAL_SHARE" />);
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Equal share is not one of the methods in this comparison. Open suggested actions from a method result in Scenario Lab.");
  expect(alert).not.toHaveTextContent(/Comparison not found/);
});

it("the print page of an unverified method shows why, although its actions answer 409", async () => {
  vi.spyOn(networkApi, "actions").mockRejectedValue(new ApiError("RESULT_NOT_VERIFIED", 409));
  render(<PrintPlan networkId={network.id} comparisonId={saved.id} method="EGP_PI_INSPIRED" />);
  const main = screen.getByRole("main");
  await waitFor(() => expect(main).toHaveTextContent(NO_PLAN));
  expect(main).toHaveTextContent(egp.failure_reason!);
  expect(main).toHaveTextContent(`Solver status: ${egp.native_status} (native)`);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("selecting 700 actions keeps the print link short, with no action ids, and the print page shows all 700", async () => {
  const many = actions(700);
  vi.spyOn(networkApi, "actions").mockResolvedValue(many);
  render(<DecisionsView comparisonId={saved.id} method="CLASSICAL_GP" />);
  fireEvent.click(await screen.findByRole("button", { name: "Select all" }));
  const link = screen.getByRole("link", { name: "Print page (700 actions)" });
  const href = link.getAttribute("href")!;
  expect(href.length).toBeLessThan(2048);
  expect(many.actions.filter((a) => href.includes(a.id))).toEqual([]);
  expect(new URL(href, "http://localhost").searchParams.has("actions")).toBe(false);
  fireEvent.click(link);
  cleanup();

  render(<PrintPlan networkId={network.id} comparisonId={saved.id} method="CLASSICAL_GP" />);
  const table = await screen.findByRole("table", { name: "Selected actions" });
  expect(within(table).getAllByRole("row")).toHaveLength(701); // the header and 700 actions
  // About 1 s alone; it once passed 5 s under full-gate load on 977f7c6 (W5-SC01).
}, 20_000);

it("the print page says the selection is missing, never prints an empty plan, when nothing was stored or storage is blocked", async () => {
  vi.spyOn(networkApi, "actions").mockResolvedValue(actions(3));
  render(<PrintPlan networkId={network.id} comparisonId={saved.id} method="CLASSICAL_GP" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("No selected actions were found for this plan. Open the print page from Decisions after selecting actions.");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  cleanup();

  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
  render(<PrintPlan networkId={network.id} comparisonId={saved.id} method="CLASSICAL_GP" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("No selected actions were found for this plan.");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("an export the server finds too large says how many actions can be exported at once", async () => {
  vi.spyOn(networkApi, "actions").mockResolvedValue(actions(3));
  vi.spyOn(networkApi, "exportPlan").mockRejectedValue(new ApiError("INPUT_TOO_LARGE", 413));
  render(<DecisionsView comparisonId={saved.id} method="CLASSICAL_GP" />);
  fireEvent.click(await screen.findByRole("button", { name: "Select all" }));
  fireEvent.click(screen.getByRole("button", { name: "Export CSV (3 actions)" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Export failed: too many actions selected to export at once (at most 40,000).");
});

it("a selection that cannot be saved (storage full) leaves none behind, so print says it is missing instead of printing an older one", async () => {
  vi.spyOn(networkApi, "actions").mockResolvedValue(actions(700));
  render(<DecisionsView comparisonId={saved.id} method="CLASSICAL_GP" />);
  fireEvent.click((await screen.findAllByRole("checkbox"))[0]);
  fireEvent.click(screen.getByRole("link", { name: "Print page (1 action)" }));
  expect(window.localStorage.length).toBe(1); // one action saved
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
  fireEvent.click(screen.getByRole("button", { name: "Select all" }));
  fireEvent.click(screen.getByRole("link", { name: "Print page (700 actions)" }));
  expect(window.localStorage.length).toBe(0);
  cleanup();

  render(<PrintPlan networkId={network.id} comparisonId={saved.id} method="CLASSICAL_GP" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("No selected actions were found for this plan.");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("only the latest selection is kept, and the print page uses it only for the same network, comparison and method", async () => {
  vi.spyOn(networkApi, "actions").mockResolvedValue(actions(3));
  render(<DecisionsView comparisonId={saved.id} method="CLASSICAL_GP" />);
  fireEvent.click(await screen.findByRole("button", { name: "Select all" }));
  fireEvent.click(screen.getByRole("link", { name: "Print page (3 actions)" }));
  cleanup();
  render(<DecisionsView comparisonId={saved.id} method="NO_TRANSFERS" />);
  fireEvent.click(await screen.findByRole("button", { name: "Select all" }));
  fireEvent.click(screen.getByRole("link", { name: "Print page (3 actions)" }));
  expect(window.localStorage.length).toBe(1); // saving overwrites; storage never piles up
  cleanup();

  // CLASSICAL_GP's selection was replaced by NO_TRANSFERS's; another comparison has none either.
  for (const [comparisonId, method] of [[saved.id, "CLASSICAL_GP"], ["00000000-0000-4000-8000-000000000000", "NO_TRANSFERS"]] as const) {
    render(<PrintPlan networkId={network.id} comparisonId={comparisonId} method={method} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No selected actions were found for this plan.");
    cleanup();
  }
  render(<PrintPlan networkId={network.id} comparisonId={saved.id} method="NO_TRANSFERS" />);
  expect(within(await screen.findByRole("table", { name: "Selected actions" })).getAllByRole("row")).toHaveLength(4);
});

it("a verified method whose actions still answer 409 shows the no-plan state on Decisions and print, not an error", async () => {
  const classical = saved.result.methods.find((m) => m.method === "CLASSICAL_GP")!;
  expect(classical.verified).toBe(true);
  const actionsCall = vi.spyOn(networkApi, "actions").mockRejectedValue(new ApiError("RESULT_NOT_VERIFIED", 409));
  render(<DecisionsView comparisonId={saved.id} method="CLASSICAL_GP" />);
  const section = screen.getByRole("region", { name: `Suggested actions · ${network.name}` });
  await waitFor(() => expect(section).toHaveTextContent("Classical GP has no verified plan in this comparison, so there are no suggested actions."));
  expect(actionsCall).toHaveBeenCalled();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  cleanup();

  render(<PrintPlan networkId={network.id} comparisonId={saved.id} method="CLASSICAL_GP" />);
  await waitFor(() => expect(screen.getByRole("main")).toHaveTextContent("Classical GP has no verified plan in this comparison, so there are no suggested actions."));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

// W4 decisions §6 / W5-SC01: selecting saves nothing; only following the print link saves the selection, so
// Decisions open in another tab can't replace the selection this tab is about to print.
it("the selection is saved only when the print link is used, so another tab's selecting doesn't replace it", async () => {
  vi.spyOn(networkApi, "actions").mockResolvedValue(actions(3));
  render(<DecisionsView comparisonId={saved.id} method="CLASSICAL_GP" />);
  fireEvent.click(await screen.findByRole("button", { name: "Select all" }));
  expect(window.localStorage.length).toBe(0);
  fireEvent.click(screen.getByRole("link", { name: "Print page (3 actions)" }));
  expect(window.localStorage.length).toBe(1);
  cleanup();

  // The other tab: a second plan's Decisions, with actions selected but not printed.
  render(<DecisionsView comparisonId={saved.id} method="NO_TRANSFERS" />);
  fireEvent.click(await screen.findByRole("button", { name: "Select all" }));
  cleanup();

  render(<PrintPlan networkId={network.id} comparisonId={saved.id} method="CLASSICAL_GP" />);
  expect(within(await screen.findByRole("table", { name: "Selected actions" })).getAllByRole("row")).toHaveLength(4);
});

it("a middle-click or the link's context menu (open in a new tab) saves the selection too; neither fires click", async () => {
  vi.spyOn(networkApi, "actions").mockResolvedValue(actions(3));
  render(<DecisionsView comparisonId={saved.id} method="CLASSICAL_GP" />);
  fireEvent.click(await screen.findByRole("button", { name: "Select all" }));
  const link = screen.getByRole("link", { name: "Print page (3 actions)" });
  fireEvent.mouseDown(link, { button: 1 });
  expect(window.localStorage.length).toBe(1);
  window.localStorage.clear();
  fireEvent.mouseDown(link, { button: 2 });
  expect(window.localStorage.length).toBe(1);
});

// W5-UI02.3: effect periods and the plan window are named in local calendar days.
it("names a period across months, a single day, and the Retail wording after the plan's window", () => {
  expect(periodText("2026-10-30", "2026-11-05")).toBe("Oct 30–Nov 5 (7 days)");
  expect(periodText("2026-11-06", "2026-11-06")).toBe("Nov 6 (1 day)");
  const decisions = { ...example("DecisionActions"), plan_window_start: "2026-11-06", plan_window_end: "2026-11-12" };
  expect(planCovers(decisions, "RETAIL")).toBe("Plan covers Nov 6–12 (7 days) only; lost sales after Nov 12 are not planned.");
});
