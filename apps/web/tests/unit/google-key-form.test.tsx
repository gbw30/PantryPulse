// covers: V1-A11
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { GoogleFetch } from "@/components/enrichment/google-fetch";
import { GoogleKeyForm } from "@/components/enrichment/google-key-form";
import { RouteList } from "@/components/enrichment/route-list";
import { example } from "./contract-examples";

const SECRET = "AIza-test-key-never-shown";

it('key input is cleared after save and never re-rendered; only "configured" shows', async () => {
  const user = userEvent.setup();
  const onSave = vi.fn(async () => ({ ...example("LocalSettings"), google_maps_configured: true }));
  const { container } = render(<GoogleKeyForm configured={false} onSave={onSave} onRemove={vi.fn()} />);
  expect(screen.getByText("Google Maps key: not configured")).toBeVisible();
  const input = screen.getByLabelText("Google Maps API key");
  expect(input).toHaveAttribute("type", "password");
  expect(input).toHaveAttribute("autocomplete", "off");
  await user.type(input, SECRET);
  await user.click(screen.getByRole("button", { name: "Save key" }));
  expect(onSave).toHaveBeenCalledWith(SECRET);
  expect(await screen.findByText("Google Maps key: configured")).toBeVisible();
  expect(input).toHaveValue("");
  expect(container.innerHTML).not.toContain(SECRET);
});

it('fetch shows "This will make N Google lookups" before confirming', async () => {
  const user = userEvent.setup();
  const preview = example("GoogleLookupPreview");
  const onPreview = vi.fn(async () => preview);
  const onFetch = vi.fn(async () => example("ForecastAccepted"));
  render(<GoogleFetch configured onPreview={onPreview} onFetch={onFetch} />);
  await user.click(screen.getByRole("button", { name: "Fetch Google road distances" }));
  const confirm = await screen.findByRole("dialog");
  expect(confirm).toHaveTextContent(`This will make ${preview.lookups} Google lookups`);
  expect(confirm).toHaveTextContent(`${preview.cached} routes are already cached`);
  expect(onFetch).not.toHaveBeenCalled();
  await user.click(within(confirm).getByRole("button", { name: `Make ${preview.lookups} lookups` }));
  expect(onFetch).toHaveBeenCalledOnce();
});

it("fetch is unavailable without a configured key", () => {
  render(<GoogleFetch configured={false} onPreview={vi.fn()} onFetch={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Fetch Google road distances" })).toBeDisabled();
});

it('route method labels "straight-line estimate" / "Google road distance, fetched DATE"', () => {
  const list = example("RouteList");
  list.routes.push({ ...list.routes[0], to_location_id: "P-30", method: "routes_csv", override: true, road_miles: null, travel_days: 2 });
  render(<RouteList routes={list.routes} />);
  const table = screen.getByRole("table", { name: /Routes/ });
  expect(within(table).getByRole("row", { name: /HUB-N.*P-12.*42\.3.*1 day.*straight-line estimate/ })).toBeVisible();
  expect(within(table).getByRole("row", { name: /HUB-N.*P-07.*61\.8.*Google road distance, fetched Nov 5, 2026/ })).toBeVisible();
  expect(within(table).getByRole("row", { name: /HUB-N.*P-30.*Not given.*2 days.*from routes\.csv/ })).toBeVisible();
});
