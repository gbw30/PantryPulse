// covers: V1-A21
import type { ReactNode } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { NetworkAtlas } from "@/components/overview/network-atlas";
import * as sources from "@/components/overview/sources";
import * as fixtures from "@/components/overview/static-fixture";
import type { OverviewDataSource, OverviewSnapshot } from "@/components/overview/types";

// Isolate adapter/state behavior; the real shell/map, keyboard and geometry run in E2E.
vi.mock("@/components/shell/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
// The mocked shell has no NetworkProvider; the v1 danger ranking has its own tests (danger-ranking.test.tsx).
vi.mock("@/components/overview/danger-ranking", async (load) => ({ ...(await load<typeof import("@/components/overview/danger-ranking")>()), DangerRankingSection: () => null }));
vi.mock("@/components/overview/schematic-map", () => ({
  SchematicMapRenderer: ({ markers }: { markers: { site: { id: string }; accessibleName: string }[] }) => (
    <div data-testid="loaded-map">{markers.map((marker) => <span key={marker.site.id}>{marker.accessibleName}</span>)}</div>
  ),
}));

afterEach(() => vi.restoreAllMocks());

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

it("US-01: loading becomes an error, and Retry loads real adapter results", async () => {
  const user = userEvent.setup();
  const initial = deferred<OverviewSnapshot>();
  const load = vi.fn<OverviewDataSource["load"]>()
    .mockReturnValueOnce(initial.promise)
    .mockResolvedValueOnce(fixtures.staticFixtureSnapshot);
  vi.spyOn(sources, "overviewSourceFor").mockReturnValue({ source: { id: "controlled", load }, preview: null });
  render(<NetworkAtlas />);
  expect(screen.getByText("Loading network snapshot…")).toBeVisible();
  expect(screen.queryByTestId("loaded-map")).not.toBeInTheDocument();
  await act(async () => initial.reject(new Error("Temporary snapshot outage")));
  expect(await screen.findByRole("alert")).toHaveTextContent("Temporary snapshot outage");
  expect(screen.queryByTestId("loaded-map")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByTestId("loaded-map")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByRole("list", { name: "All sites" }).children).toHaveLength(7);
  expect(load).toHaveBeenCalledTimes(2);
  expect(load.mock.calls[0][0].aborted).toBe(true);
});

it.each(["resolve", "reject"] as const)("US-01: a stale request cannot %s over the newer snapshot", async (settle) => {
  const old = deferred<OverviewSnapshot>();
  const oldLoad = vi.fn<OverviewDataSource["load"]>().mockReturnValue(old.promise);
  const newSource: OverviewDataSource = { id: "new", load: async () => fixtures.emptyFixtureSnapshot };
  const oldSource: OverviewDataSource = { id: "old", load: oldLoad };
  vi.spyOn(sources, "overviewSourceFor").mockImplementation((preview) => ({ source: preview === "new" ? newSource : oldSource, preview: null }));
  const { rerender } = render(<NetworkAtlas statePreview="old" />);
  rerender(<NetworkAtlas statePreview="new" />);
  await screen.findByText(/No projection is available for this snapshot/);
  expect(oldLoad.mock.calls[0][0].aborted).toBe(true);
  await act(async () => {
    if (settle === "resolve") old.resolve(fixtures.staticFixtureSnapshot);
    else old.reject(new Error("Stale error"));
  });
  expect(screen.getByText(/No projection is available for this snapshot/)).toBeVisible();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /Not evaluated/ })).toHaveLength(7);
});

it("aborts an in-flight adapter request on unmount", async () => {
  const waiting = deferred<OverviewSnapshot>();
  const load = vi.fn<OverviewDataSource["load"]>().mockReturnValue(waiting.promise);
  vi.spyOn(sources, "overviewSourceFor").mockReturnValue({ source: { id: "pending", load }, preview: null });
  const { unmount } = render(<NetworkAtlas />);
  await waitFor(() => expect(load).toHaveBeenCalledTimes(1));
  unmount();
  expect(load.mock.calls[0][0].aborted).toBe(true);
  await act(async () => waiting.resolve(fixtures.staticFixtureSnapshot));
});
