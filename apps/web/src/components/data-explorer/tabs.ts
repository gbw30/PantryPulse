// Data Explorer subviews (packet PP-53 decision 5). One config drives the tab strip and in-page links.
// `built: false` renders disabled with "(not built yet)"; all five are built as of PP-56 integration.
// `presenterOnly` tabs render only for a presenter session.

export type ExplorerTabKey = "dashboard" | "pulse" | "operations" | "inventory" | "inputs";

// `stockChanging` subviews (receipts, posting, adjustments, lot declarations) stay built but are left out
// of v1 navigation: in v1 the app never changes its own stock (V1-SPEC §8).
export type ExplorerTab = { key: ExplorerTabKey; label: string; href: string; built: boolean; presenterOnly: boolean; stockChanging?: true };

export const EXPLORER_TABS: readonly ExplorerTab[] = [
  { key: "dashboard", label: "Dashboard", href: "/data", built: true, presenterOnly: false },
  { key: "pulse", label: "Seven-Day Pulse", href: "/data/pulse", built: true, presenterOnly: false },
  { key: "operations", label: "Operations Board", href: "/data/operations", built: true, presenterOnly: false, stockChanging: true },
  { key: "inventory", label: "Inventory & Lots", href: "/data/inventory", built: true, presenterOnly: false, stockChanging: true },
  { key: "inputs", label: "Data input", href: "/data/inputs", built: true, presenterOnly: true, stockChanging: true },
];

export function explorerTab(key: ExplorerTabKey) {
  return EXPLORER_TABS.find((tab) => tab.key === key)!;
}

/** Keeps the selected product across subviews. */
export function tabHref(tab: ExplorerTab, productId?: string | null) {
  return productId ? `${tab.href}?product=${encodeURIComponent(productId)}` : tab.href;
}
