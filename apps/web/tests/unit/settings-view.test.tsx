// covers: V1-A10
import type { ReactNode } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { EnrichmentStatusPanel } from "@/components/enrichment/enrichment-status";
import { GoogleFetch } from "@/components/enrichment/google-fetch";
import { SettingsView } from "@/components/enrichment/settings-view";
import { networkApi } from "@/lib/network-api";
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

it("queued lookups say how to see the result, since nothing polls the job", async () => {
  const accepted = example("ForecastAccepted");
  render(<EnrichmentStatusPanel status={{ ...example("EnrichmentStatus"), state: "done" }} onRetry={async () => accepted} onSaveAttributes={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Retry lookups" }));
  expect(await screen.findByText(`Lookups queued (job ${accepted.job_id.slice(0, 8)}). Reload this page after they finish to see the results.`)).toBeVisible();

  render(<GoogleFetch configured onPreview={async () => example("GoogleLookupPreview")} onFetch={async () => accepted} />);
  fireEvent.click(screen.getByRole("button", { name: "Fetch Google road distances" }));
  fireEvent.click(await screen.findByRole("button", { name: /^Make .* lookups$/ }));
  expect(await screen.findByText("Google lookups queued. Reload this page after the job finishes to see the new route labels.")).toBeVisible();
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
