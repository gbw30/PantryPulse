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
