// covers: V1-A07, V1-A23
import type { ReactNode } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ImportView } from "@/components/import/import-view";
import { lastHistoryDate } from "@/components/import/network-settings";
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
  vi.spyOn(networkApi, "exampleUnavailableReason").mockResolvedValue(null);
});

const csv = (name: string) => new File(["x"], name, { type: "text/csv" });
const asOf = () => screen.getByLabelText("Stock snapshot date (as_of_date)");

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
  fireEvent.click(screen.getByRole("button", { name: "Check again" }));
  await screen.findByText(example("ImportStatus").failure!.message);
  expect(status).toHaveBeenCalledTimes(2);
});
