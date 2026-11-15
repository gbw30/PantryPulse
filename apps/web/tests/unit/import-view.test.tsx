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

it("a commit the queue turned away (503) says the import didn't start, stops polling, and Retry commits the same files again", async () => {
  // The commit's transaction rolled back: the run still reads "uploading" with no job (imports/api.py commit_import).
  const created = example("ImportCreated");
  const commit = vi.spyOn(networkApi, "commitImport")
    .mockRejectedValueOnce(new ApiError("COMPUTE_QUEUE_FULL", 503))
    .mockResolvedValueOnce(example("ImportAccepted"));
  const notStarted = { ...example("ImportStatus"), phase: "uploading" as const, job_id: null, progress: null, error_count: 0, errors: [], failure: null };
  const status = vi.spyOn(networkApi, "importStatus").mockResolvedValueOnce(notStarted).mockResolvedValue(example("ImportStatus"));
  await importAll();

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("The import didn't start (compute queue full). Your files are kept and nothing was saved.");
  expect(screen.getByRole("button", { name: "Check and import" })).not.toHaveAttribute("aria-disabled");
  await act(() => new Promise((resolve) => setTimeout(resolve, 1_500))); // longer than one poll interval
  expect(status).toHaveBeenCalledTimes(1);

  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await screen.findByText(example("ImportStatus").failure!.message);
  expect(commit).toHaveBeenCalledTimes(2);
  expect(commit.mock.calls.map(([id]) => id)).toEqual([created.import_id, created.import_id]);
  expect(networkApi.createImport).toHaveBeenCalledTimes(1);
});

// W4 web hardening (lead, 2026-11-10): a commit can outlast the proxy's 20 s while it waits for the queue lock. With no
// answer, a run still "uploading" may yet start, so the page checks again before offering Retry (safe: the API gives
// each run's commit a stable key, so a second commit gets the same job).
const uploadingNoJob = () => ({ ...example("ImportStatus"), phase: "uploading" as const, job_id: null, progress: null, error_count: 0, errors: [], failure: null });

it("a commit the proxy timed out on may still be starting: the page checks again and carries on when its job appears", async () => {
  let answer: (error: unknown) => void = () => {};
  vi.spyOn(networkApi, "commitImport").mockImplementation(() => new Promise((_, reject) => { answer = reject; }));
  const status = vi.spyOn(networkApi, "importStatus").mockResolvedValueOnce(uploadingNoJob()).mockResolvedValueOnce(uploadingNoJob())
    .mockResolvedValue(example("ImportStatus"));
  await importAll();
  await waitFor(() => expect(networkApi.commitImport).toHaveBeenCalled());
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  try {
    await act(async () => { answer(new ApiError("BACKEND_UNAVAILABLE", 503)); });
    expect(screen.getByRole("status")).toHaveTextContent("The server didn't answer in time, so the import may still be starting. Checking again…");
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(screen.queryByText(/didn't start/)).not.toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(status).toHaveBeenCalledTimes(3);
    expect(screen.getByText(example("ImportStatus").failure!.message)).toBeVisible();
    expect(networkApi.commitImport).toHaveBeenCalledTimes(1);
  } finally {
    vi.useRealTimers();
  }
});

it("a commit with no answer whose run still has no job after the checks offers Retry, which sends the same run", async () => {
  const created = example("ImportCreated");
  let answer: (error: unknown) => void = () => {};
  const commit = vi.spyOn(networkApi, "commitImport").mockImplementationOnce(() => new Promise((_, reject) => { answer = reject; }))
    .mockResolvedValueOnce(example("ImportAccepted"));
  const status = vi.spyOn(networkApi, "importStatus").mockResolvedValue(uploadingNoJob());
  await importAll();
  await waitFor(() => expect(commit).toHaveBeenCalled());
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  try {
    await act(async () => { answer(new ApiError("BACKEND_UNAVAILABLE", 503)); });
    await act(async () => { await vi.advanceTimersByTimeAsync(29_000); });
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(screen.getByRole("alert")).toHaveTextContent("The import didn't start (backend unavailable). Your files are kept and nothing was saved.");
    const checks = status.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
    expect(status).toHaveBeenCalledTimes(checks); // the checks stop with the alert
  } finally {
    vi.useRealTimers();
  }
  status.mockResolvedValue(example("ImportStatus"));
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await screen.findByText(example("ImportStatus").failure!.message);
  expect(commit.mock.calls.map(([id]) => id)).toEqual([created.import_id, created.import_id]);
});

it("after a commit with no answer and a lost status read, Check again keeps checking for the rest of the window (F1)", async () => {
  let answer: (error: unknown) => void = () => {};
  vi.spyOn(networkApi, "commitImport").mockImplementation(() => new Promise((_, reject) => { answer = reject; }));
  const status = vi.spyOn(networkApi, "importStatus").mockResolvedValueOnce(uploadingNoJob())
    .mockRejectedValueOnce(new ApiError("BACKEND_UNAVAILABLE", 503)).mockResolvedValue(uploadingNoJob());
  await importAll();
  await waitFor(() => expect(networkApi.commitImport).toHaveBeenCalled());
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  try {
    await act(async () => { answer(new ApiError("BACKEND_UNAVAILABLE", 503)); });
    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
    expect(screen.getByRole("alert")).toHaveTextContent("Lost contact with the import");
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    await act(async () => {});
    // One of the 30 checks was used before contact was lost: 29 remain, one read per second.
    expect(screen.getByRole("status")).toHaveTextContent("the import may still be starting. Checking again…");
    await act(async () => { await vi.advanceTimersByTimeAsync(28_000); });
    expect(screen.queryByText(/didn't start/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start a new import" })).not.toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(screen.getByRole("alert")).toHaveTextContent("The import didn't start (backend unavailable). Your files are kept and nothing was saved.");
    expect(status).toHaveBeenCalledTimes(2 + 30);
    expect(networkApi.commitImport).toHaveBeenCalledTimes(1);
  } finally {
    vi.useRealTimers();
  }
});

it("losing contact again inside the resumed window keeps the remaining checks (F1 review)", async () => {
  let answer: (error: unknown) => void = () => {};
  vi.spyOn(networkApi, "commitImport").mockImplementation(() => new Promise((_, reject) => { answer = reject; }));
  const lost = new ApiError("BACKEND_UNAVAILABLE", 503);
  const status = vi.spyOn(networkApi, "importStatus").mockResolvedValueOnce(uploadingNoJob()).mockRejectedValueOnce(lost);
  for (let i = 0; i < 5; i++) status.mockResolvedValueOnce(uploadingNoJob());
  status.mockRejectedValueOnce(lost).mockResolvedValue(uploadingNoJob());
  await importAll();
  await waitFor(() => expect(networkApi.commitImport).toHaveBeenCalled());
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  try {
    await act(async () => { answer(lost); });
    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
    fireEvent.click(screen.getByRole("button", { name: "Check again" })); // 29 checks left
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
    expect(screen.getByRole("alert")).toHaveTextContent("Lost contact with the import");
    fireEvent.click(screen.getByRole("button", { name: "Check again" })); // 24 checks left, one read per second
    await act(async () => { await vi.advanceTimersByTimeAsync(23_000); });
    expect(screen.queryByText(/didn't start/)).not.toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(screen.getByRole("alert")).toHaveTextContent("The import didn't start (backend unavailable).");
    expect(status).toHaveBeenCalledTimes(2 + 6 + 25);
  } finally {
    vi.useRealTimers();
  }
});

// CR-w5-data-2 (Gabriel, 2026-11-12): a commit admitted with its phase write lost reads "didn't start"; the job then
// finishes, and Retry gets 409 IMPORT_ALREADY_FINISHED (W5-D04). The page reads the run instead of saying nothing was saved.
async function retryAfterFinished(finished: ReturnType<typeof example<"ImportStatus">>) {
  const commit = vi.spyOn(networkApi, "commitImport")
    .mockRejectedValueOnce(new ApiError("COMPUTE_QUEUE_FULL", 503))
    .mockRejectedValueOnce(new ApiError("IMPORT_ALREADY_FINISHED", 409));
  vi.spyOn(networkApi, "importStatus").mockResolvedValueOnce(uploadingNoJob()).mockResolvedValue(finished);
  await importAll();
  expect(await screen.findByRole("alert")).toHaveTextContent("The import didn't start");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(commit).toHaveBeenCalledTimes(2));
}

it("Retry on an import that already finished shows the finished import, not a failed request (CR-w5-data-2)", async () => {
  const done = { ...example("ImportStatus"), phase: "done" as const, error_count: 0, errors: [], failure: null };
  await retryAfterFinished(done);
  expect(await screen.findByRole("heading", { name: "Import finished" })).toBeInTheDocument();
  expect(screen.queryByText(/Nothing was saved/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Import request failed/)).not.toBeInTheDocument();
});

it("Retry on an import that already failed keeps its row-error report (CR-w5-data-2)", async () => {
  await retryAfterFinished(example("ImportStatus"));
  expect(await screen.findByText(example("ImportStatus").failure!.message)).toBeInTheDocument();
  expect(screen.queryByText(/Import request failed/)).not.toBeInTheDocument();
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
