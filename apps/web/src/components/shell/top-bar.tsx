import { useState } from "react";
import { CalendarDays, Menu, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSidebar } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";
import { SAMPLE_LABEL, useNetwork } from "./network-switcher";
import { ThemeToggle } from "./theme-toggle";

const snapshotDate = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

/**
 * The data label (W2-06 carry-in): a sample network is fictional sample data; a real import gets no
 * label; with no v1 network chosen the screens show the legacy simulated demo. Nothing while loading.
 */
function dataLabel(state: ReturnType<typeof useNetwork>["state"], network: ReturnType<typeof useNetwork>["network"]) {
  if (network) return network.is_sample ? SAMPLE_LABEL : null;
  return state.status === "loading" ? null : "Simulated network";
}

export type TopBarSearch = {
  value: string;
  onChange: (value: string) => void;
  /** Enter in the field: select the first match. */
  onSubmit: (invoker: HTMLElement) => void;
};

const SEARCH_LABEL = "Search sites or products";

/** Shared top bar (blueprint §2): search left; data label, snapshot date, horizon and theme toggle right. No identity here. */
export function TopBar({ search, horizonLabel }: { search?: TopBarSearch; horizonLabel?: string }) {
  const { toggleSidebar } = useSidebar();
  const { state, network } = useNetwork();
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const label = dataLabel(state, network);

  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-card px-3 md:gap-4 md:px-6">
      <Button variant="ghost" size="icon" className="size-11 md:hidden" aria-label="Open navigation" onClick={toggleSidebar}>
        <Menu />
      </Button>
      <div className={cn("relative min-w-0 flex-1 md:max-w-md", !mobileSearchOpen && "max-md:hidden")}>
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input
          type="search"
          aria-label={SEARCH_LABEL}
          placeholder={`${SEARCH_LABEL}…`}
          className="h-10 bg-background pl-9"
          value={search?.value ?? ""}
          disabled={!search}
          onChange={(event) => search?.onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && search) {
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
      <div className={cn("ml-auto flex shrink-0 items-center gap-3", mobileSearchOpen && "max-md:hidden")}>
        {label && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-pp-teal/30 bg-pp-teal-soft px-2.5 py-1 text-xs font-medium text-foreground">
            <span aria-hidden="true" className="size-1.5 rounded-full bg-pp-teal" />
            {label}
          </span>
        )}
        {network?.as_of_date && (
          <span className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">Snapshot {snapshotDate(network.as_of_date)}</span>
        )}
        {horizonLabel && (
          <span className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-sm text-foreground max-md:hidden">
            <CalendarDays className="size-4 text-muted-foreground" aria-hidden="true" />
            {horizonLabel}
          </span>
        )}
        <ThemeToggle />
      </div>
    </header>
  );
}
