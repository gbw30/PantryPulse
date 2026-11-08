// covers: V1-A13
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { LocationInspector } from "@/components/overview/location-inspector";
import { networkApi } from "@/lib/network-api";
import { ApiError } from "@/lib/planning-api";
import { example } from "./contract-examples";

const projection = example("LocationProjection");
const network = example("NetworkList").networks.find((n) => n.id === projection.network_id)!;
const location = example("LocationList").locations.find((l) => l.location_id === "P-12")!;
const open = (onClose = vi.fn()) =>
  render(<LocationInspector network={network} forecastRunId={projection.forecast_run_id} location={location} onClose={onClose} />);

beforeEach(() => vi.restoreAllMocks());

it("shows each product in its own unit, unknown days as unknown, and no totals", async () => {
  const read = vi.spyOn(networkApi, "projection").mockResolvedValue(projection);
  open();
  expect(read).toHaveBeenCalledWith(network.id, projection.forecast_run_id, "P-12");
  const region = screen.getByRole("region", { name: "Site inspector · Archer Road Pantry" });
  expect(within(region).getByText("Pantry · P-12 · Gainesville, FL · no coordinates, so not on the map")).toBeVisible();

  const water = await within(region).findByRole("table", { name: "WATER-24 in cases" });
  expect(within(water).getAllByRole("columnheader").map((h) => h.textContent))
    .toEqual(["Day", "Target", "Served", "Unmet need", "Expiring unsold"]);
  const unknownDay = within(water).getByRole("row", { name: /Nov 10/ });
  expect(within(unknownDay).getAllByText("unknown")).toHaveLength(4);
  expect(within(region).getByText("Eligible stock now: 21 cases")).toBeVisible();
  expect(within(region).getByText("Donations (forecast, not confirmed): not available for WATER-24.")).toBeVisible();

  const rice = within(region).getByRole("table", { name: "RICE-5 in bags" });
  expect(within(rice).getAllByRole("columnheader").map((h) => h.textContent))
    .toEqual(["Day", "Target", "Served", "Unmet need", "Donations (forecast, not confirmed)"]);
  expect(within(region).getByText("Expiring unsold: not available for RICE-5.")).toBeVisible();
  expect(region).not.toHaveTextContent(/total/i);
  expect(region).toHaveTextContent("Forecasts are projections.");
});

it("a projection the server can't give yet says so, with a retry, and close hands focus back", async () => {
  vi.spyOn(networkApi, "projection").mockRejectedValueOnce(new ApiError("NOT_IMPLEMENTED", 501)).mockResolvedValueOnce(projection);
  const onClose = vi.fn();
  open(onClose);
  expect(await screen.findByRole("alert")).toHaveTextContent("Projection unavailable (not implemented).");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("table", { name: "WATER-24 in cases" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Close inspector" }));
  expect(onClose).toHaveBeenCalled();
});
