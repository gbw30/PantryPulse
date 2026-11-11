// covers: V1-A10
import type { ReactNode } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { EnrichmentStatusPanel } from "@/components/enrichment/enrichment-status";
import { GoogleFetch } from "@/components/enrichment/google-fetch";
import { SettingsView } from "@/components/enrichment/settings-view";
import { networkApi } from "@/lib/network-api";
import type { Schema } from "@/lib/planning-api";
import { example } from "./contract-examples";

const [first, second] = example("NetworkList").networks;
let current = first;
vi.mock("@/components/shell/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
vi.mock("@/components/shell/network-switcher", async (load) => ({
  ...(await load<typeof import("@/components/shell/network-switcher")>()),
  useNetwork: () => ({ state: { status: "ready", networks: [first, second] }, network: current, reload: vi.fn(), select: vi.fn() }),
}));

const never = <T,>() => new Promise<T>(() => {});
beforeEach(() => {
  vi.restoreAllMocks();
  current = first;
  vi.spyOn(networkApi, "settings").mockResolvedValue(example("LocalSettings"));
  vi.spyOn(networkApi, "enrichment").mockImplementation((id) => (id === first.id ? Promise.resolve({ ...example("EnrichmentStatus"), network_id: first.id }) : never()));
  vi.spyOn(networkApi, "routes").mockImplementation((id) => (id === first.id ? Promise.resolve({ ...example("RouteList"), network_id: first.id }) : never()));
});

it("queued lookups promise an update, which the job poll keeps", async () => {
  const accepted = example("ForecastAccepted");
  render(<EnrichmentStatusPanel status={{ ...example("EnrichmentStatus"), state: "done" }} onRetry={async () => accepted} onSaveAttributes={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Retry lookups" }));
  expect(await screen.findByText(`Lookups queued (job ${accepted.job_id.slice(0, 8)}). This list updates when they finish.`)).toBeVisible();

  render(<GoogleFetch configured onPreview={async () => example("GoogleLookupPreview")} onFetch={async () => accepted} />);
  fireEvent.click(screen.getByRole("button", { name: "Fetch Google road distances" }));
  fireEvent.click(await screen.findByRole("button", { name: /^Make .* lookups$/ }));
  expect(await screen.findByText("Google lookups queued. Route labels update when the job finishes.")).toBeVisible();
});

it("a queued lookup or route job re-reads its list when the job ends (GET /jobs/{id})", async () => {
  const accepted = example("ForecastAccepted");
  const ended = { job_id: accepted.job_id, state: "SUCCEEDED", current_attempt_id: accepted.attempt_id, attempts: [] } as unknown as Schema["ForecastJob"];
  vi.spyOn(networkApi, "retryEnrichment").mockResolvedValue(accepted);
  vi.spyOn(networkApi, "googlePreview").mockResolvedValue(example("GoogleLookupPreview"));
  vi.spyOn(networkApi, "googleFetch").mockResolvedValue(accepted);
  let end!: (job: Schema["ForecastJob"]) => void;
  const job = vi.spyOn(networkApi, "job").mockImplementation(() => new Promise((resolve) => { end = resolve; }));
  vi.spyOn(networkApi, "settings").mockResolvedValue({ ...example("LocalSettings"), google_maps_configured: true });
  render(<SettingsView />);

  fireEvent.click(await screen.findByRole("button", { name: "Retry lookups" }));
  // Mount, then the queued state right away; the job is still open.
  await waitFor(() => expect(networkApi.enrichment).toHaveBeenCalledTimes(2));
  expect(job).toHaveBeenCalledWith(accepted.job_id);
  await act(async () => end(ended));
  await waitFor(() => expect(networkApi.enrichment).toHaveBeenCalledTimes(3));

  fireEvent.click(screen.getByRole("button", { name: "Fetch Google road distances" }));
  fireEvent.click(await screen.findByRole("button", { name: /^Make .* lookups$/ }));
  await waitFor(() => expect(networkApi.routes).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(job).toHaveBeenCalledTimes(2));
  await act(async () => end(ended));
  await waitFor(() => expect(networkApi.routes).toHaveBeenCalledTimes(3));
});

it("a status read while the import's lookups still run follows that job and re-reads when it ends", async () => {
  const done = { ...example("EnrichmentStatus"), network_id: first.id };
  const running = { ...done, state: "running" as const };
  vi.spyOn(networkApi, "enrichment").mockResolvedValueOnce(running).mockResolvedValue(done);
  const job = vi.spyOn(networkApi, "job").mockResolvedValue({ job_id: running.job_id, state: "SUCCEEDED", attempts: [] } as unknown as Schema["ForecastJob"]);
  render(<SettingsView />);
  await waitFor(() => expect(job).toHaveBeenCalledWith(running.job_id));
  await waitFor(() => expect(screen.getByText(/Address and Census lookups:/)).toHaveTextContent("done"));
  expect(networkApi.enrichment).toHaveBeenCalledTimes(2);
});

it("a job state outside the contract stops the polling and re-reads the list once", async () => {
  vi.spyOn(networkApi, "retryEnrichment").mockResolvedValue(example("ForecastAccepted"));
  let answer!: (job: Schema["ForecastJob"]) => void;
  const job = vi.spyOn(networkApi, "job").mockImplementation(() => new Promise((resolve) => { answer = resolve; }));
  render(<SettingsView />);
  fireEvent.click(await screen.findByRole("button", { name: "Retry lookups" }));
  // Mount, then the queued state right away.
  await waitFor(() => expect(networkApi.enrichment).toHaveBeenCalledTimes(2));
  await act(async () => answer({ state: "PAUSED" } as unknown as Schema["ForecastJob"]));
  // Once more when the poll gives up, with no further job read.
  await waitFor(() => expect(networkApi.enrichment).toHaveBeenCalledTimes(3));
  expect(job).toHaveBeenCalledTimes(1);
});

it("switching network never shows the previous network's locations or routes under the new name", async () => {
  const { rerender } = render(<SettingsView />);
  const firstLocation = example("EnrichmentStatus").locations[0].location_id;
  expect((await screen.findAllByText(new RegExp(firstLocation))).length).toBeGreaterThan(0);

  current = second;
  rerender(<SettingsView />);
  expect(screen.getByRole("heading", { name: `Locations in ${second.name}` })).toBeVisible();
  expect(screen.getByText("Loading locations…")).toBeVisible();
  expect(screen.getByText("Loading routes…")).toBeVisible();
  expect(screen.queryByText(new RegExp(firstLocation))).not.toBeInTheDocument();
});

it("a sample network's pre-filled rates say they are sample values; a real manual entry says entered by you (V1-SPEC §8)", async () => {
  const { sourceLine } = await import("@/components/enrichment/attribute-editor");
  const location = { ...example("LocationAttributes"), state: "manual" as const };
  expect(sourceLine({ ...location, source: "sample values" })).toBe("Source: sample values");
  expect(sourceLine({ ...location, source: null })).toBe("Source: entered by you");
  expect(sourceLine({ ...location, source: "manual" })).toBe("Source: entered by you");
});

// W4-03 #2: one rate entered, the other looked up. The API names each rate's source; the Census one must read
// "ACS 5-year YYYY, tract NNNN" (V1-SPEC §6.3), never "entered by you" for both.
it("a location with one rate entered and one looked up names each rate's source", async () => {
  const { sourceLine } = await import("@/components/enrichment/attribute-editor");
  const location = { ...example("LocationAttributes"), state: "manual" as const };
  expect(sourceLine({ ...location, source: "snap_rate: manual; poverty_rate: ACS 5-year 2024, tract 06001400100" }))
    .toBe("Source: SNAP rate entered by you; poverty rate from ACS 5-year 2024, tract 06001400100");
  expect(sourceLine({ ...location, source: "poverty_rate: manual; snap_rate: ACS 5-year 2024, tract 06001400100 (unconfirmed address match)" }))
    .toBe("Source: poverty rate entered by you; SNAP rate from ACS 5-year 2024, tract 06001400100 (unconfirmed address match)");
});

// W4 web hardening (lead, 2026-11-10): an import whose lookups were refused by a full queue says so, and Retry starts them.
it("lookups that did not start say why and offer Retry, which queues them", async () => {
  const message = "Address lookups did not start: the job queue was full when the import finished. Use Retry to start them.";
  const accepted = example("ForecastAccepted");
  const onRetry = vi.fn(async () => accepted);
  render(<EnrichmentStatusPanel status={{ ...example("EnrichmentStatus"), state: "not_started", unmatched: [], last_error: message }} onRetry={onRetry} onSaveAttributes={vi.fn()} />);
  expect(screen.getByText(message)).toBeVisible();
  expect(screen.queryByText(/last error/)).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Addresses not found" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry lookups" }));
  expect(onRetry).toHaveBeenCalledTimes(1);
  expect(await screen.findByText(`Lookups queued (job ${accepted.job_id.slice(0, 8)}). This list updates when they finish.`)).toBeVisible();
});

it("a sample network's lookups never started, with no message: nothing to retry", () => {
  render(<EnrichmentStatusPanel status={{ ...example("EnrichmentStatus"), state: "not_started", unmatched: [], last_error: null }} onRetry={vi.fn()} onSaveAttributes={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "Retry lookups" })).not.toBeInTheDocument();
});
