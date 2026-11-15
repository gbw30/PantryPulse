// covers: V1-A08
import { expect, test } from "@playwright/test";
import { example, mockV1 } from "./v1-mocks";

// W5-UI04: the API writes a receiver's donation forecast into the action's why text (services/optimization/actions.py
// _donations). The page shows that line as written: display-only, never turned into supply. Mocked against
// packages/contracts/examples/v1: proves UI behavior, not the connected app.
const DONATIONS = "At Pantry 12, expected donations (forecast, not confirmed): 12 cases over 3 days, not counted as supply.";

test("@V1-A08 a location's why text with the donations line renders unchanged on Decisions", async ({ page }) => {
  const saved = example("SavedComparisonV3");
  const network = example("NetworkList").networks.find((n) => n.id === saved.network_id)!;
  const actions = example("DecisionActions");
  const why = `${actions.actions[0].why_text} ${DONATIONS}`;
  const base = `networks/${network.id}/comparisons/${saved.id}`;
  await mockV1(page, {
    "GET networks": { body: { networks: [network] } },
    [`GET networks/${network.id}`]: { body: network },
    [`GET ${base}`]: { body: saved },
    [`GET ${base}/methods/CLASSICAL_GP/actions`]: { body: { ...actions, actions: [{ ...actions.actions[0], why_text: why }] } },
  });
  await page.goto(`/decisions?comparison_id=${saved.id}&method=CLASSICAL_GP`);
  const section = page.getByRole("region", { name: `Suggested actions · ${network.name}` });
  await expect(section.getByText(why, { exact: true })).toBeVisible();
});
