// covers: V1-A14
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { MethodComparisonSection } from "@/components/scenario-lab/v1-comparison";
import { networkApi } from "@/lib/network-api";
import { ApiError, type Schema } from "@/lib/planning-api";
import { example } from "./contract-examples";

const network = example("NetworkList").networks.find((n) => n.mode === "PANTRY")!;
vi.mock("motion/react", async (load) => ({ ...(await load<typeof import("motion/react")>()), useReducedMotion: () => true }));
vi.mock("@/components/shell/network-switcher", async (load) => ({
  ...(await load<typeof import("@/components/shell/network-switcher")>()),
  useNetwork: () => ({ state: { status: "ready", networks: [network] }, network, reload: vi.fn(), select: vi.fn() }),
}));

// The comparison freezes the network's newest published forecast run for its current data (W4-02).
const runs = example("ForecastRunList");
const published = { ...runs.runs[1], forecast_run_id: example("ScenarioV3").payload.forecast_run_id, dataset_version_id: network.dataset_version_id! };
beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(networkApi, "forecastRuns").mockResolvedValue({ ...runs, network_id: network.id, runs: [published] });
});

it("losing the job status mid-comparison keeps the job: no new job is queued, and checking again shows its result", async () => {
  const accepted = { ...example("ForecastAccepted"), result_url: `/api/v1/networks/${network.id}/comparisons/${example("ForecastAccepted").job_id}` };
  vi.spyOn(networkApi, "createScenario").mockResolvedValue(example("ScenarioV3"));
  const submit = vi.spyOn(networkApi, "submitComparison").mockResolvedValue(accepted);
  vi.spyOn(networkApi, "job")
    .mockRejectedValueOnce(new ApiError("NETWORK_ERROR", 0))
    .mockResolvedValueOnce({ job_id: accepted.job_id, state: "SUCCEEDED", current_attempt_id: accepted.attempt_id, attempts: [] } as unknown as Schema["ForecastJob"]);
  const at = vi.spyOn(networkApi, "comparisonAt").mockResolvedValue(example("SavedComparisonV3"));
  render(<MethodComparisonSection />);
  fireEvent.click(screen.getByRole("radio", { name: "Hub and pantries → pantries" }));
  fireEvent.click(screen.getByRole("radio", { name: "3 days" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Freeze scenario" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Freeze scenario" }));
  fireEvent.click(await screen.findByRole("button", { name: "Compare methods" }));

  const lost = await screen.findByRole("alert");
  expect(lost).toHaveTextContent("Lost contact with the comparison job (network error). It may still finish; check again before comparing again.");
  expect(screen.getByRole("button", { name: "Compare methods" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Check again" }));
  await waitFor(() => expect(at).toHaveBeenCalledWith(accepted.result_url));
  expect((await screen.findAllByText("Verified by the independent check")).length).toBeGreaterThan(0);
  expect(submit).toHaveBeenCalledTimes(1);
});

it("a job state outside the contract stops the polling and says the status is unknown", async () => {
  const accepted = { ...example("ForecastAccepted"), result_url: `/api/v1/networks/${network.id}/comparisons/${example("ForecastAccepted").job_id}` };
  vi.spyOn(networkApi, "createScenario").mockResolvedValue(example("ScenarioV3"));
  vi.spyOn(networkApi, "submitComparison").mockResolvedValue(accepted);
  const job = vi.spyOn(networkApi, "job").mockResolvedValue({ job_id: accepted.job_id, state: "PAUSED" } as unknown as Schema["ForecastJob"]);
  render(<MethodComparisonSection />);
  fireEvent.click(screen.getByRole("radio", { name: "Hub and pantries → pantries" }));
  fireEvent.click(screen.getByRole("radio", { name: "3 days" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Freeze scenario" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Freeze scenario" }));
  fireEvent.click(await screen.findByRole("button", { name: "Compare methods" }));

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("The comparison job reported a status this page doesn't know (paused). It may still finish; check again before comparing again.");
  expect(screen.getByRole("button", { name: "Compare methods" })).toBeDisabled();
  expect(job).toHaveBeenCalledTimes(1);
});

it("freezes the network's newest published forecast run for its current data (W4-02)", async () => {
  const create = vi.spyOn(networkApi, "createScenario").mockResolvedValue(example("ScenarioV3"));
  render(<MethodComparisonSection />);
  fireEvent.click(screen.getByRole("radio", { name: "Hub and pantries → pantries" }));
  fireEvent.click(screen.getByRole("radio", { name: "3 days" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Freeze scenario" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Freeze scenario" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith(network.id, expect.objectContaining({ dataset_version_id: network.dataset_version_id, forecast_run_id: published.forecast_run_id })));
});

it("with no forecast run yet, freezing is blocked and the page points to the Overview to run one (W4-02)", async () => {
  vi.mocked(networkApi.forecastRuns).mockResolvedValue({ ...runs, network_id: network.id, runs: [] });
  render(<MethodComparisonSection />);
  expect(await screen.findByText(/No forecast for this network yet\./)).toBeVisible();
  expect(screen.getByRole("link", { name: "Run one on the Overview" })).toHaveAttribute("href", "/overview");
  expect(screen.getByText("A forecast run is needed before freezing a scenario.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Freeze scenario" })).toBeDisabled();
});
