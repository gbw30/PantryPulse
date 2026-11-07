// covers: V1-A14, V1-A15
import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { DEFAULT_PANTRY_POLICY } from "@/components/scenario-lab/model";
import { MethodComparisonResults } from "@/components/scenario-lab/results";
import { ComparisonSetup } from "@/components/scenario-lab/wizard";
import type { Schema } from "@/lib/planning-api";
import { example } from "./contract-examples";

vi.mock("motion/react", async (load) => ({ ...(await load<typeof import("motion/react")>()), useReducedMotion: () => true }));

const scenario = example("ScenarioV3");
const saved = example("SavedComparisonV3");
// Retail variant of the same frozen scenario: every product priced, so USD is available.
const pricedRetail: Schema["ScenarioV3"] = {
  ...scenario,
  payload: { ...scenario.payload, mode: "RETAIL", products: scenario.payload.products.map((p, i) => ({ ...p, unit_value_usd: i === 0 ? "4.50" : "6.25" })) },
};

const setup = (props: Partial<React.ComponentProps<typeof ComparisonSetup>> = {}) =>
  render(<ComparisonSetup mode="PANTRY" busy={false} scenario={null} onFreeze={vi.fn()} onCompare={vi.fn()} {...props} />);

it("pantry lists 5 methods, retail lists 3", () => {
  const { unmount } = setup();
  expect(within(screen.getByRole("list", { name: "Methods compared" })).getAllByRole("listitem").map((li) => li.textContent))
    .toEqual(["No transfers", "Equal share", "Most-urgent-first", "Classical GP", "EGP-PI-inspired"]);
  unmount();
  setup({ mode: "RETAIL" });
  expect(within(screen.getByRole("list", { name: "Methods compared" })).getAllByRole("listitem").map((li) => li.textContent))
    .toEqual(["No transfers", "Soonest-expiry-first", "Optimized (minimize expired + lost sales)"]);
});

it("transfer mode has no default and must be chosen", () => {
  const onFreeze = vi.fn();
  setup({ onFreeze });
  const group = screen.getByRole("radiogroup", { name: "Transfer mode (required)" });
  const radios = within(group).getAllByRole("radio");
  expect(radios.map((r) => r.getAttribute("aria-checked"))).toEqual(["false", "false"]);
  expect(within(group).getByText("Hub → pantries only")).toBeVisible();
  expect(within(group).getByText("Hub and pantries → pantries")).toBeVisible();
  const freeze = screen.getByRole("button", { name: "Freeze scenario" });
  fireEvent.click(screen.getByRole("radio", { name: "3 days" }));
  expect(freeze).toBeDisabled();
  expect(screen.getByText("Choose a transfer mode first. There is no default.")).toBeVisible();
  fireEvent.click(within(group).getByRole("radio", { name: "Hub and pantries → pantries" }));
  expect(freeze).toBeEnabled();
  fireEvent.click(freeze);
  expect(onFreeze).toHaveBeenCalledWith({ transferMode: "HUB_AND_PANTRY", retailWeights: null, planningDays: 3, policy: DEFAULT_PANTRY_POLICY });
});

it("the client's default Pantry policy is the frozen contract's", () => {
  expect(DEFAULT_PANTRY_POLICY).toEqual(scenario.payload.policy);
});

it("pantry planning window is 1-3 days with no default", () => {
  const onFreeze = vi.fn();
  setup({ onFreeze });
  fireEvent.click(screen.getByRole("radio", { name: "Hub → pantries only" }));
  const window = screen.getByRole("radiogroup", { name: "Planning window (required)" });
  expect(within(window).getAllByRole("radio")).toHaveLength(3);
  for (const name of ["1 day", "2 days", "3 days"]) expect(within(window).getByRole("radio", { name })).toHaveAttribute("aria-checked", "false");
  expect(screen.getByText("Choose a planning window of 1 to 3 days. There is no default.")).toBeVisible();
  const freeze = screen.getByRole("button", { name: "Freeze scenario" });
  expect(freeze).toBeDisabled();
  fireEvent.click(within(window).getByRole("radio", { name: "2 days" }));
  fireEvent.click(freeze);
  expect(onFreeze).toHaveBeenCalledWith(expect.objectContaining({ planningDays: 2 }));
});

it("pantry policy shows λ, β and the attribute shares, editable; shares must add up to 100", () => {
  const onFreeze = vi.fn();
  setup({ onFreeze });
  fireEvent.click(screen.getByRole("radio", { name: "Hub → pantries only" }));
  fireEvent.click(screen.getByRole("radio", { name: "1 day" }));
  expect(screen.getByLabelText("Vulnerability weight λ (%)")).toHaveValue(100);
  expect(screen.getByLabelText("Weight on total shortfall β (%)")).toHaveValue(50);
  expect(screen.getByLabelText("Poverty rate share (%)")).toHaveValue(50);
  expect(screen.getByLabelText("SNAP rate share (%)")).toHaveValue(50);
  const freeze = screen.getByRole("button", { name: "Freeze scenario" });

  fireEvent.change(screen.getByLabelText("Weight on total shortfall β (%)"), { target: { value: "101" } });
  expect(screen.getByText("Enter a whole number from 0 to 100.")).toBeVisible();
  expect(freeze).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Weight on total shortfall β (%)"), { target: { value: "70" } });
  fireEvent.change(screen.getByLabelText("Vulnerability weight λ (%)"), { target: { value: "80" } });
  fireEvent.change(screen.getByLabelText("Poverty rate share (%)"), { target: { value: "60" } });
  expect(screen.getByText("The poverty and SNAP rate shares must add up to 100.")).toBeVisible();
  expect(freeze).toBeDisabled();
  fireEvent.change(screen.getByLabelText("SNAP rate share (%)"), { target: { value: "40" } });
  fireEvent.click(freeze);
  expect(onFreeze).toHaveBeenCalledWith({ transferMode: "HUB_ONLY", retailWeights: null, planningDays: 1, policy: {
    ...DEFAULT_PANTRY_POLICY, lambda_percent: 80, beta_percent: 70,
    coefficients: [{ attribute_id: "poverty_rate", percent: 60 }, { attribute_id: "snap_rate", percent: 40 }] } });
});

it("a frozen pantry scenario shows its window and policy", () => {
  setup({ scenario });
  expect(screen.getByText("Window 3 days · λ 100% · β 50% · poverty rate 50%, SNAP rate 50%")).toBeVisible();
});

it("retail labels its transfer modes and freezes with editable weights", () => {
  const onFreeze = vi.fn();
  setup({ mode: "RETAIL", onFreeze });
  expect(screen.queryByRole("radiogroup", { name: "Planning window (required)" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Vulnerability weight λ (%)")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("radio", { name: "DC → stores only" }));
  expect(screen.getByLabelText("Weight on expired units")).toHaveValue(1);
  fireEvent.change(screen.getByLabelText("Weight on lost sales"), { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "Freeze scenario" }));
  expect(onFreeze).toHaveBeenCalledWith({ transferMode: "HUB_ONLY", retailWeights: { w_exp: 1, w_lost: 2 }, planningDays: null, policy: null });
});

it("retail weights are whole numbers from 0 to 1000, as the server accepts", () => {
  setup({ mode: "RETAIL" });
  fireEvent.click(screen.getByRole("radio", { name: "DC → stores only" }));
  const freeze = screen.getByRole("button", { name: "Freeze scenario" });
  for (const bad of ["1.5", "1001"]) {
    fireEvent.change(screen.getByLabelText("Weight on lost sales"), { target: { value: bad } });
    expect(screen.getByText("Enter a whole number from 0 to 1000.")).toBeVisible();
    expect(freeze).toBeDisabled();
  }
  fireEvent.change(screen.getByLabelText("Weight on lost sales"), { target: { value: "1000" } });
  expect(freeze).toBeEnabled();
});

it("USD option disabled with the unavailable reason", () => {
  const onCompare = vi.fn();
  const retail: Schema["ScenarioV3"] = { ...scenario, payload: { ...scenario.payload, mode: "RETAIL" } };
  const { unmount } = setup({ mode: "RETAIL", scenario: retail, onCompare });
  const usd = screen.getByRole("radio", { name: "USD" });
  expect(usd).toBeDisabled();
  expect(screen.getByText("USD unavailable: no unit_value_usd in products.csv for Bottled water, Rice, 5 lb.")).toBeVisible();
  fireEvent.click(screen.getByRole("radio", { name: "Units" }));
  fireEvent.click(screen.getByRole("button", { name: "Compare methods" }));
  expect(onCompare).toHaveBeenCalledWith("UNITS");
  unmount();

  setup({ mode: "RETAIL", scenario: pricedRetail, onCompare });
  expect(screen.getByRole("radio", { name: "USD" })).toBeEnabled();
  expect(screen.queryByText(/USD unavailable/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("radio", { name: "USD" }));
  fireEvent.click(screen.getByRole("button", { name: "Compare methods" }));
  expect(onCompare).toHaveBeenLastCalledWith("USD");
});

it("each method shows verification status; a failed method shows its native status and no plan", () => {
  render(<MethodComparisonResults comparison={saved} scenario={scenario} requested={["NO_TRANSFERS", "EQUAL_SHARE", "MOST_URGENT_FIRST", "CLASSICAL_GP", "EGP_PI_INSPIRED"]} />);
  const classical = screen.getByRole("region", { name: "Classical GP" });
  expect(classical).toHaveTextContent("Verified by the independent check");
  expect(classical).toHaveTextContent("Solver status: OPTIMAL (native)");
  expect(classical).toHaveTextContent("optimized per product, with shared capacity split in advance");
  expect(classical).toHaveTextContent("Products solved: Bottled water (OPTIMAL)");
  expect(classical).toHaveTextContent("Rice, 5 lb: not at risk; not optimized");

  const egp = screen.getByRole("region", { name: "EGP-PI-inspired" });
  expect(egp).toHaveTextContent("Not verified — no plan shown");
  expect(egp).toHaveTextContent("Solver status: UNKNOWN (native)");
  expect(egp).toHaveTextContent("search limit reached before a feasible plan; no plan shown");
  expect(within(egp).queryByRole("table")).not.toBeInTheDocument();

  expect(screen.getByRole("region", { name: "No transfers" })).toHaveTextContent("No solver: rule-based method");
  // Requested but absent from the saved result: said plainly, never filled in.
  expect(screen.getByRole("region", { name: "Equal share" })).toHaveTextContent("No result returned for this method.");
});

it("per-location effects table", () => {
  render(<MethodComparisonResults comparison={saved} scenario={scenario} requested={saved.result.methods.map((m) => m.method)} />);
  const table = within(screen.getByRole("region", { name: "Classical GP" })).getByRole("table", { name: "Classical GP: effects by location" });
  expect(within(table).getAllByRole("columnheader").map((th) => th.textContent))
    .toEqual(["Location", "Product", "Unmet without plan", "Unmet with plan", "Expired without plan", "Expired with plan"]);
  const row = within(table).getAllByRole("row")[1];
  expect(within(row).getByRole("rowheader")).toHaveTextContent("Pantry 12");
  expect(within(row).getAllByRole("cell").map((td) => td.textContent)).toEqual(["Bottled water", "55 cases", "15 cases", "0 cases", "0 cases"]);
  expect(screen.getByText("Effects are per location and product; quantities of different products are never added together.")).toBeVisible();
  // A verified method with transfers links to its suggested actions (W1-W08).
  expect(screen.getByRole("link", { name: "Open suggested actions for Classical GP" }))
    .toHaveAttribute("href", `/decisions?comparison_id=${saved.id}&method=CLASSICAL_GP`);
  expect(screen.queryByRole("link", { name: /for EGP-PI-inspired/ })).not.toBeInTheDocument();
});
