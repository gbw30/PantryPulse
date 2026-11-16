// covers: V1-A20
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ExplorerTabLink } from "@/components/data-explorer/header";
import { EXPLORER_TABS } from "@/components/data-explorer/tabs";
import { NetworkProvider } from "@/components/shell/network-switcher";
import { TopBar, type TopBarSearch } from "@/components/shell/top-bar";
import { networkApi } from "@/lib/network-api";
import { example } from "./contract-examples";

// W5A-03c: the context bar's controls take the new look (spec §4.10; the prototype's .pick, .search input, .tab.on).
const sidebar = vi.hoisted(() => ({ isMobile: false }));
vi.mock("@/components/ui/sidebar", () => ({ useSidebar: () => ({ toggleSidebar: vi.fn(), isMobile: sidebar.isMobile }) }));
vi.mock("@/components/shell/presenter-session", () => ({ usePresenter: () => ({ state: "presenter", signIn: vi.fn(), signOut: vi.fn() }), signInMessage: () => "" }));

const sample = example("NetworkList").networks.find((n) => n.is_sample)!;
const classes = (el: Element) => el.className.split(/\s+/);
const bar = (search?: TopBarSearch) => render(<NetworkProvider><TopBar search={search} /></NetworkProvider>);

beforeEach(() => {
  vi.restoreAllMocks();
  sidebar.isMobile = false;
  vi.spyOn(networkApi, "list").mockResolvedValue({ networks: [sample] });
});

it("the network picker is a fully rounded tint pill", async () => {
  bar();
  expect(classes(await screen.findByRole("combobox"))).toEqual(expect.arrayContaining(["rounded-full", "bg-pp-tint"]));
});

it("with no search passed, the context bar renders no search field and no Search button", async () => {
  bar();
  await screen.findByRole("combobox");
  expect(screen.queryByRole("searchbox")).toBeNull();
  expect(screen.queryByRole("button", { name: /search/i })).toBeNull();
});

it("a passed search renders as a fully rounded tint pill", () => {
  bar({ value: "", onChange: vi.fn(), onSubmit: vi.fn() });
  expect(classes(screen.getByRole("searchbox", { name: "Search sites or products" }))).toEqual(expect.arrayContaining(["rounded-full", "bg-pp-tint"]));
});

it("below 768 px the sample label is a neutral tint badge: ink text, no dot, no action colour", async () => {
  sidebar.isMobile = true;
  bar();
  const label = await screen.findByText("Sample data — fictional");
  expect(label.children).toHaveLength(0);
  expect(label.className).not.toMatch(/pp-action/);
  expect(classes(label)).toEqual(expect.arrayContaining(["bg-pp-tint", "text-pp-ink"]));
});

it("the current Data Explorer tab is a 3 px action underline, and no tab is an outlined box", () => {
  render(<ul><li><ExplorerTabLink tab={EXPLORER_TABS[0]} active /></li><li><ExplorerTabLink tab={EXPLORER_TABS[1]} /></li></ul>);
  const current = screen.getByRole("link", { name: "Dashboard" });
  expect(current).toHaveAttribute("aria-current", "page");
  expect(classes(current)).toEqual(expect.arrayContaining(["border-b-[3px]", "aria-[current=page]:border-pp-action"]));
  for (const tab of [current, screen.getByRole("link", { name: "Seven-Day Pulse" })]) {
    expect(classes(tab)).not.toContain("border");
    expect(tab.className).not.toMatch(/rounded|shadow|bg-pp-action-soft/);
  }
});
