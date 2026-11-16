import { useState } from "react";
import { CalendarDays, Menu, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSidebar } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";
import type { NavKey } from "./app-sidebar";
import { NetworkSwitcher, SAMPLE_LABEL, useNetwork } from "./network-switcher";
import { ThemeToggle } from "./theme-toggle";

const snapshotDate = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

// Screens that show no network data, so the legacy demo's "simulated" pill would mislabel them (lead, 2026-11-09).
// The Overview joined them in W5A-03: without a network it shows a sign-in or a picker, never the fixture atlas.
const NO_NETWORK_DATA: ReadonlySet<NavKey> = new Set(["overview", "import", "settings"]);
// Screens that never read the chosen network: they render the legacy fixture data whatever is chosen (L1). The Data
// dashboard also renders the chosen network's forecast trust, so it passes legacyOnly={false} (W4-03 #1).
const ALWAYS_LEGACY: ReadonlySet<NavKey> = new Set(["data", "recommendations"]);

/**
 * The data labels (W2-06 carry-in): a screen that renders the legacy demo says "Simulated network" (the data
 * and recommendations screens always do); otherwise a sample network is fictional sample data and a real
 * import gets none. A network list that failed says so. Nothing is guessed while the list loads.
 */
function dataLabels(state: ReturnType<typeof useNetwork>["state"], network: ReturnType<typeof useNetwork>["network"], active?: NavKey,
  legacyOnly = !!active && ALWAYS_LEGACY.has(active)) {
  const unavailable = state.status === "error" ? ["Network list unavailable"] : [];
  if (legacyOnly) return [...unavailable, "Simulated network"];
  if (network) return network.is_sample ? [SAMPLE_LABEL] : [];
  if (state.status === "loading") return [];
  return active && NO_NETWORK_DATA.has(active) ? unavailable : [...unavailable, "Simulated network"];
}

export type TopBarSearch = {
  value: string;
  onChange: (value: string) => void;
  /** Enter in the field: select the first match. */
  onSubmit: (invoker: HTMLElement) => void;
};

const SEARCH_LABEL = "Search sites or products";

/**
 * The header's context bar (row 2 of AppTopNav; the whole header below 768 px): network, search, data labels,
 * snapshot date, horizon, the page-actions slot (filled by PageActions) and the theme toggle.
 */
export function TopBar({ search, horizonLabel, active, legacyOnly }: { search?: TopBarSearch; horizonLabel?: string; active?: NavKey; legacyOnly?: boolean }) {
  const { toggleSidebar, isMobile } = useSidebar();
  const { state, network } = useNetwork();
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  // At 768 px and up the switcher beside the pills already carries the sample badge.
  const labels = dataLabels(state, network, active, legacyOnly).filter((label) => isMobile || label !== SAMPLE_LABEL);

  return (
    <div data-slot="context-bar" className="flex items-center gap-2 border-b border-border px-3 max-md:h-14 md:flex-wrap md:gap-x-4 md:gap-y-2 md:px-7 md:py-2.5">
      <Button variant="ghost" size="icon" className="size-11 md:hidden" aria-label="Open navigation" onClick={toggleSidebar}>
        <Menu />
      </Button>
      {/* Below 768 px the switcher is in the drawer; isMobile is false until hydration, hence the CSS too. */}
      {/* The Overview announces a failed network list itself (W5A-03c), so the bar's copy is not a second alert. */}
      {!isMobile && <div className="min-w-0 max-md:hidden"><NetworkSwitcher bar quietError={active === "overview"} /></div>}
      {/* Only a page that searches gets the field: a disabled one took a second row at 1280 px (W5A-03c). */}
      {search && (
        <>
          <div className={cn("relative min-w-0 flex-1 md:max-w-md md:min-w-48", !mobileSearchOpen && "max-md:hidden")}>
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              type="search"
              aria-label={SEARCH_LABEL}
              placeholder={`${SEARCH_LABEL}…`}
              className="h-10 rounded-full bg-pp-tint pl-9 dark:bg-pp-tint"
              value={search.value}
              onChange={(event) => search.onChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  search.onSubmit(event.currentTarget);
                }
              }}
            />
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="size-11 md:hidden"
            aria-label={mobileSearchOpen ? "Close search" : "Search"}
            aria-expanded={mobileSearchOpen}
            onClick={() => setMobileSearchOpen((open) => !open)}
          >
            <Search />
          </Button>
        </>
      )}
      <div className={cn("ml-auto flex min-w-0 items-center gap-3", mobileSearchOpen && "max-md:hidden")}>
        {/* Below sm the data label sits over the snapshot date, so the bar fits 390 px without hiding either. */}
        <div className="flex min-w-0 items-center gap-3 max-sm:flex-col max-sm:items-end max-sm:gap-0.5">
        {/* A neutral badge (spec §4.10): no action green and no dot, which would read as "OK" or "live". */}
        {labels.map((label) => (
          <span key={label} className="inline-flex items-center rounded-full bg-pp-tint px-2.5 py-1 text-xs font-medium whitespace-nowrap text-pp-ink max-sm:py-0.5">
            {label}
          </span>
        ))}
        {network?.as_of_date && (
          <span className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">Snapshot {snapshotDate(network.as_of_date)}</span>
        )}
        </div>
        {horizonLabel && (
          <span className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-sm text-foreground max-md:hidden">
            <CalendarDays className="size-4 text-muted-foreground" aria-hidden="true" />
            {horizonLabel}
          </span>
        )}
        <div data-slot="page-actions" className="flex items-center gap-2 empty:hidden" />
        <ThemeToggle />
      </div>
    </div>
  );
}
