// covers: V1-A07, V1-A23
import type { ReactNode } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ImportView } from "@/components/import/import-view";
import { lastHistoryDate } from "@/components/import/network-settings";
import { CHOOSE_MODE_NOTE } from "@/components/import/template-guide";
import { networkApi } from "@/lib/network-api";
import { ApiError } from "@/lib/planning-api";
import { example } from "./contract-examples";

const reload = vi.fn();
vi.mock("@/components/shell/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
vi.mock("@/components/shell/network-switcher", async (load) => ({
  ...(await load<typeof import("@/components/shell/network-switcher")>()),
  useNetwork: () => ({ state: { status: "ready", networks: [] }, network: null, reload, select: vi.fn() }),
}));
vi.mock("@/components/import/network-settings", async (load) => ({
  ...(await load<typeof import("@/components/import/network-settings")>()), lastHistoryDate: vi.fn(),
}));

beforeEach(() => {
  vi.restoreAllMocks();
  vi.mocked(lastHistoryDate).mockReset().mockResolvedValue(null);
  vi.spyOn(networkApi, "templates").mockResolvedValue(example("TemplateCatalog"));
});

const csv = (name: string) => new File(["x"], name, { type: "text/csv" });
const asOf = () => screen.getByLabelText("Stock snapshot date (as_of_date)");

/** Fill in a new Pantry network with every template file and press "Check and import". */
async function importAll() {
  vi.spyOn(networkApi, "createImport").mockResolvedValue(example("ImportCreated"));
  vi.spyOn(networkApi, "uploadImportFile").mockResolvedValue(example("ImportFile"));
  const user = userEvent.setup();
  render(<ImportView />);
  fireEvent.change(await screen.findByLabelText("Network name"), { target: { value: "My pantries" } });
  fireEvent.click(screen.getByRole("radio", { name: /^Pantry network/ }));
  for (const t of example("TemplateCatalog").templates) await user.upload(screen.getByLabelText(`${t.name}.csv (${t.required ? "required" : "optional"})`), csv(`${t.name}.csv`));
  fireEvent.click(screen.getByRole("button", { name: "Check and import" }));
}

it("says which addresses are sent to the US Census Geocoder before anything is uploaded (V1-SPEC §2, §6.3)", async () => {
  render(<ImportView />);
  const notice = await screen.findByText(/Addresses without latitude and longitude are sent to the US Census Geocoder/);
  expect(notice).toHaveTextContent(/after the import/);
  expect(notice).toHaveTextContent(/Locations with coordinates are never sent/);
  expect(notice).toHaveTextContent(/stay unknown.*retry/);
});

it("a slower scan of an earlier demand_history.csv never overwrites the later file's date", async () => {
  let finishFirst!: (last: string | null) => void;
  vi.mocked(lastHistoryDate)
    .mockImplementationOnce(() => new Promise((resolve) => { finishFirst = resolve; }))
    .mockImplementationOnce(async () => "2026-09-30");
  const user = userEvent.setup();
  render(<ImportView />);
  const history = await screen.findByLabelText("demand_history.csv (required)");
  await user.upload(history, csv("big.csv"));
  await user.upload(history, csv("small.csv"));
  await waitFor(() => expect(asOf()).toHaveValue("2026-10-01"));
  await act(async () => finishFirst("2026-06-30"));
  expect(asOf()).toHaveValue("2026-10-01");
});

it("losing the status check after the commit was accepted never claims nothing was saved", async () => {
  vi.spyOn(networkApi, "createImport").mockResolvedValue(example("ImportCreated"));
  vi.spyOn(networkApi, "uploadImportFile").mockResolvedValue(example("ImportFile"));
  vi.spyOn(networkApi, "commitImport").mockResolvedValue(example("ImportAccepted"));
  const status = vi.spyOn(networkApi, "importStatus")
    .mockRejectedValueOnce(new ApiError("NETWORK_ERROR", 0))
    .mockResolvedValueOnce(example("ImportStatus"));
  const user = userEvent.setup();
  render(<ImportView />);
  fireEvent.change(await screen.findByLabelText("Network name"), { target: { value: "My pantries" } });
  fireEvent.click(screen.getByRole("radio", { name: /^Pantry network/ }));
  for (const t of example("TemplateCatalog").templates) await user.upload(screen.getByLabelText(`${t.name}.csv (${t.required ? "required" : "optional"})`), csv(`${t.name}.csv`));
  fireEvent.click(screen.getByRole("button", { name: "Check and import" }));

  const lost = await screen.findByRole("alert");
  expect(lost).toHaveTextContent("Lost contact with the import (network error). It may still finish; nothing is known yet about what was saved.");
  expect(lost).not.toHaveTextContent(/Nothing was saved/);
  // The accepted import may still commit: a second submit could create a second copy. The button stays
  // focusable (aria-disabled) so keyboard focus isn't dropped, but pressing it does nothing.
  const again = screen.getByRole("button", { name: "Check and import" });
  expect(again).toHaveAttribute("aria-disabled", "true");
  fireEvent.click(again);
  expect(networkApi.createImport).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Check again" }));
  await screen.findByText(example("ImportStatus").failure!.message);
  expect(status).toHaveBeenCalledTimes(2);
});

it("an import phase outside the contract stops the polling and says the status is unknown", async () => {
  vi.spyOn(networkApi, "commitImport").mockResolvedValue(example("ImportAccepted"));
  const status = vi.spyOn(networkApi, "importStatus").mockResolvedValue({ ...example("ImportStatus"), phase: "archived" } as unknown as ReturnType<typeof example<"ImportStatus">>);
  await importAll();
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("The import reported a status this page doesn't know (archived). It may still finish; nothing is known yet about what was saved.");
  expect(screen.getByRole("button", { name: "Check again" })).toBeVisible();
  expect(status).toHaveBeenCalledTimes(1);
});

it("a commit with no answer never claims nothing was saved: the run is read again", async () => {
  const created = example("ImportCreated");
  vi.spyOn(networkApi, "commitImport").mockRejectedValue(new ApiError("NETWORK_ERROR", 0));
  const status = vi.spyOn(networkApi, "importStatus").mockResolvedValue(example("ImportStatus"));
  await importAll();
  await screen.findByText(example("ImportStatus").failure!.message);
  expect(status).toHaveBeenCalledWith(created.import_id);
  expect(screen.queryByText(/Nothing was saved/)).not.toBeInTheDocument();
});

it("a commit the server refused still says nothing was saved", async () => {
  vi.spyOn(networkApi, "commitImport").mockRejectedValue(new ApiError("AS_OF_DATE_INVALID", 422));
  const status = vi.spyOn(networkApi, "importStatus");
  await importAll();
  expect(await screen.findByRole("alert")).toHaveTextContent("Import request failed (as of date invalid). Nothing was saved.");
  expect(status).not.toHaveBeenCalled();
});

it("follows the catalog's example_available and requests no example just to learn why (CR-w3-samples-3)", async () => {
  const fetches = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 404 }));
  vi.mocked(networkApi.templates).mockImplementation(async (mode) => ({ ...example("TemplateCatalog"), mode: mode ?? null }));
  render(<ImportView />);
  expect(await screen.findAllByText(CHOOSE_MODE_NOTE)).toHaveLength(2);
  fireEvent.click(screen.getByRole("radio", { name: /^Retail network/ }));
  await waitFor(() => expect(networkApi.templates).toHaveBeenLastCalledWith("RETAIL"));
  expect(await screen.findAllByText("Example not available yet.")).toHaveLength(2);
  expect(fetches.mock.calls.map(([url]) => String(url)).filter((url) => url.includes("kind=example"))).toEqual([]);
});
