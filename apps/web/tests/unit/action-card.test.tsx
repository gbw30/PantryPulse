// covers: V1-A16
import { render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ActionCard } from "@/components/decisions/action-card";
import { ActionList } from "@/components/decisions/action-list";
import type { Schema } from "@/lib/planning-api";
import { example } from "./contract-examples";

const decisions = example("DecisionActions");
const [action] = decisions.actions;
// A second, inferred action cloned from the example, to show two effects side by side.
const second: Schema["DecisionAction"] = { ...action, id: "T-2", explanation_kind: "inferred",
  action_text: "Move 10 cases of Bottled water from Hub North to Pantry 7, ship on Nov 6, arrives Nov 7.",
  why_text: "Pantry 7 is likely short on Nov 9.", effect: { ...action.effect, receiver_unmet_delta: -10 } };

const card = (props: Partial<React.ComponentProps<typeof ActionCard>> = {}) =>
  render(<ActionCard action={action} mode="PANTRY" usdUnavailableReason={null} selected={false} onSelectedChange={vi.fn()} {...props} />);

it("action/why/effect three parts", () => {
  card();
  const article = screen.getByRole("article", { name: action.action_text });
  expect(within(article).getAllByRole("heading").map((h) => h.textContent)).toEqual(["Action", "Why", "Effect"]);
  expect(article).toHaveTextContent(action.action_text);
  expect(article).toHaveTextContent(action.why_text);
  expect(article).toHaveTextContent("Receiver unmet need: 40 cases lower");
  expect(article).toHaveTextContent("Sender unmet need: unchanged");
  expect(article).toHaveTextContent("Expired: unchanged");
  expect(within(article).getByRole("checkbox", { name: "Include in export" })).not.toBeChecked();
  // Effect lines carry the product's unit, so there is no "units as in the plan" caveat.
  expect(article).not.toHaveTextContent(/units as in the plan/);
});

it("proven vs inferred badge", () => {
  const { unmount } = card();
  expect(screen.getByText("Proven: binding constraint")).toBeVisible();
  unmount();
  card({ action: second });
  expect(screen.getByText("Inferred reason")).toBeVisible();
  expect(screen.queryByText(/Proven/)).not.toBeInTheDocument();
});

it("non-additive label visible", () => {
  render(<ActionList decisions={decisions} mode="PANTRY" usdUnavailableReason={null} selected={new Set()} onToggle={vi.fn()} />);
  expect(screen.getByText("effect of this action given the rest of the plan; effects don't add up across actions")).toBeVisible();
});

it("no summed effect anywhere", () => {
  const { container } = render(<ActionList decisions={{ ...decisions, actions: [action, second] }} mode="PANTRY" usdUnavailableReason={null}
    selected={new Set(["T-1", "T-2"])} onToggle={vi.fn()} />);
  expect(screen.getAllByRole("article")).toHaveLength(2);
  // −40 and −10 must never be shown as a combined 50.
  expect(container).not.toHaveTextContent(/\b50\b/);
  expect(container).not.toHaveTextContent(/total|combined|overall/i);
});

it("USD effect hidden with reason when unavailable", () => {
  const { unmount } = card({ mode: "RETAIL", usdUnavailableReason: "no unit values in products.csv" });
  expect(screen.getByText("USD effect unavailable: no unit values in products.csv")).toBeVisible();
  expect(screen.getByText(/Receiver lost sales: 40 cases lower/)).toBeVisible();
  unmount();
  const { unmount: unmount2 } = card({ mode: "RETAIL", action: { ...action, effect: { ...action.effect, usd_delta: "-180.00" } } });
  // price × (Δunmet + Δexpired): not the objective and not a loss, so never "Value lost".
  expect(screen.getByText("Dollar value of the units changed (USD): $180.00 lower")).toBeVisible();
  expect(screen.queryByText(/Value lost/)).not.toBeInTheDocument();
  expect(screen.queryByText(/USD effect unavailable/)).not.toBeInTheDocument();
  unmount2();
  // Pantry plans are never in USD: no USD line at all.
  card();
  expect(screen.queryByText(/USD/)).not.toBeInTheDocument();
});
