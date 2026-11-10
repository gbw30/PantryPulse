// covers: V1-A12, V1-A13
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { RunForecast, useForecastRun } from "@/components/forecast/forecast-run";
import { networkApi } from "@/lib/network-api";
import { ApiError } from "@/lib/planning-api";
import { example, type Schemas } from "./contract-examples";

// W4-02 (Gabriel, 2026-11-10): the app runs a network's forecast and every v1 view uses the newest
// published run for the network's current data, read from GET /networks/{id}/forecasts.
let presenter = "presenter";
vi.mock("@/components/shell/presenter-session", async (load) => ({
  ...(await load<typeof import("@/components/shell/presenter-session")>()),
  usePresenterOptional: () => ({ state: presenter }),
}));

const list = example("ForecastRunList");
const [running, published] = list.runs;
const network: Schemas["Network"] = { ...example("NetworkList").networks[0], id: list.network_id, dataset_version_id: published.dataset_version_id };
const run = (over: Partial<Schemas["ForecastRunSummary"]>): Schemas["ForecastRunSummary"] => ({ ...published, ...over });
const job = (state: Schemas["AttemptState"]): Schemas["ForecastJob"] => ({ job_id: running.job_id, state, current_attempt_id: "a", attempts: [] }) as unknown as Schemas["ForecastJob"];

beforeEach(() => { vi.restoreAllMocks(); presenter = "presenter"; });
afterEach(() => vi.useRealTimers());

it("uses the newest published run of the network's current data, and reports a newer run still going", async () => {
  const older = run({ forecast_run_id: "00000000-0000-4000-8000-0000000000aa", dataset_version_id: "00000000-0000-4000-8000-0000000000bb" });
  vi.spyOn(networkApi, "forecastRuns").mockResolvedValue({ ...list, runs: [running, published, older] });
  const { result } = renderHook(() => useForecastRun(network));
  await waitFor(() => expect(result.current.runs.status).toBe("ready"));
  expect(result.current.runs).toEqual({ status: "ready", current: published, latest: running });
  expect(networkApi.forecastRuns).toHaveBeenCalledWith(network.id);
});

it("has no current run when only an older dataset version was forecast", async () => {
  const older = run({ dataset_version_id: "00000000-0000-4000-8000-0000000000bb" });
  vi.spyOn(networkApi, "forecastRuns").mockResolvedValue({ ...list, runs: [older] });
  const { result } = renderHook(() => useForecastRun(network));
  await waitFor(() => expect(result.current.runs).toEqual({ status: "ready", current: null, latest: null }));
});

it("after a re-import, the previous data's runs are never shown while the new list loads", async () => {
  vi.spyOn(networkApi, "forecastRuns").mockResolvedValueOnce({ ...list, runs: [published] }).mockImplementation(() => new Promise(() => {}));
  const { result, rerender } = renderHook((n: Schemas["Network"]) => useForecastRun(n), { initialProps: network });
  await waitFor(() => expect(result.current.runs.status).toBe("ready"));
  rerender({ ...network, dataset_version_id: "00000000-0000-4000-8000-0000000000bb" });
  expect(result.current.runs).toEqual({ status: "loading" });
});

it("Run forecast posts the dataset version, follows the job through queued and running, then reports done", async () => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  vi.spyOn(networkApi, "submitForecast").mockResolvedValue({ ...example("ForecastAccepted"), job_id: running.job_id, state: "QUEUED" });
  vi.spyOn(networkApi, "job").mockResolvedValueOnce(job("QUEUED")).mockResolvedValueOnce(job("RUNNING")).mockResolvedValueOnce(job("SUCCEEDED"));
  const onDone = vi.fn();
  render(<RunForecast network={network} latest={null} onDone={onDone} />);
  fireEvent.click(screen.getByRole("button", { name: "Run forecast" }));
  await act(async () => {});
  expect(networkApi.submitForecast).toHaveBeenCalledWith(network.id, { dataset_version_id: network.dataset_version_id });
  expect(screen.getByRole("status")).toHaveTextContent("Forecast queued…");
  expect(screen.getByRole("button", { name: "Run forecast" })).toHaveAttribute("aria-disabled", "true");
  await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
  expect(screen.getByRole("status")).toHaveTextContent("Forecast running…");
  expect(onDone).not.toHaveBeenCalled();
  await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
  expect(screen.getByRole("status")).toHaveTextContent("Forecast finished.");
  expect(onDone).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "Run forecast" })).not.toHaveAttribute("aria-disabled");
  expect(networkApi.job).toHaveBeenCalledWith(running.job_id);
});

it("a forecast still running after a reload shows as running and is followed, with no second submit", async () => {
  vi.spyOn(networkApi, "submitForecast");
  vi.spyOn(networkApi, "job").mockResolvedValue(job("SUCCEEDED"));
  const onDone = vi.fn();
  render(<RunForecast network={network} latest={running} onDone={onDone} />);
  expect(screen.getByRole("status")).toHaveTextContent("Forecast running…");
  fireEvent.click(screen.getByRole("button", { name: "Run forecast" }));
  await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
  expect(networkApi.job).toHaveBeenCalledWith(running.job_id);
  expect(networkApi.submitForecast).not.toHaveBeenCalled();
});

it("a forecast that did not finish says so, and can be run again", async () => {
  vi.spyOn(networkApi, "submitForecast").mockResolvedValue({ ...example("ForecastAccepted"), job_id: running.job_id, state: "QUEUED" });
  vi.spyOn(networkApi, "job").mockResolvedValue(job("TIMED_OUT"));
  const onDone = vi.fn();
  render(<RunForecast network={network} latest={null} onDone={onDone} />);
  fireEvent.click(screen.getByRole("button", { name: "Run forecast" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("The forecast did not finish (timed out). Nothing changed; run it again.");
  expect(onDone).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "Run forecast" })).not.toHaveAttribute("aria-disabled");
});

it("the last forecast of this data failing is shown after a reload", () => {
  render(<RunForecast network={network} latest={run({ state: "FAILED", forecast_run_id: null })} onDone={vi.fn()} />);
  expect(screen.getByRole("alert")).toHaveTextContent("The forecast did not finish (failed).");
});

it("a refused submit says why and starts nothing", async () => {
  vi.spyOn(networkApi, "submitForecast").mockRejectedValue(new ApiError("FORECAST_SERIES_OVER_ENVELOPE", 422));
  const poll = vi.spyOn(networkApi, "job");
  render(<RunForecast network={network} latest={null} onDone={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Run forecast" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Forecast not started: forecast series over envelope (FORECAST_SERIES_OVER_ENVELOPE).");
  expect(poll).not.toHaveBeenCalled();
});

it("only a presenter can run a forecast, and only for a network with imported data", () => {
  presenter = "visitor";
  const { unmount } = render(<RunForecast network={network} latest={null} onDone={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "Run forecast" })).not.toBeInTheDocument();
  unmount();
  presenter = "presenter";
  render(<RunForecast network={{ ...network, dataset_version_id: null }} latest={null} onDone={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "Run forecast" })).not.toBeInTheDocument();
  expect(screen.getByText("Import this network's data before forecasting.")).toBeVisible();
});
