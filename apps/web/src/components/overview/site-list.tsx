import { cn } from "@/lib/utils";
import { StatusGlyph } from "./status-glyph";
import type { MarkerStatus, Site } from "./types";

export type SiteListItem = { site: Site; status: MarkerStatus; statusLine: string; detail: string };

/** Accessible list of every site, independent of the map. Selecting a row selects the marker. */
export function SiteList({ items, selectedId, query, onSelect }: { items: SiteListItem[]; selectedId: string | null; query: string; onSelect: (siteId: string, invoker: HTMLElement) => void }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 md:flex-row md:items-center md:gap-3">
      <span className="shrink-0 text-xs font-medium text-muted-foreground max-md:hidden">Sites</span>
      {items.length > 1 && <span className="text-xs text-muted-foreground md:hidden">Scroll sideways for all {items.length} sites</span>}
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground" role="status">No sites match “{query}”.</p>
      ) : (
        <ul aria-label="All sites" className="flex min-w-0 gap-2 overflow-x-auto pb-1 max-md:pr-10 max-md:[mask-image:linear-gradient(to_right,black_calc(100%-3rem),transparent)] md:flex-wrap md:overflow-visible md:pb-0">
          {items.map(({ site, status, statusLine, detail }) => {
            const selected = site.id === selectedId;
            return (
              <li key={site.id} className="shrink-0">
                <button
                  type="button"
                  aria-pressed={selected}
                  aria-describedby={`site-detail-${site.id}`}
                  onClick={(event) => onSelect(site.id, event.currentTarget)}
                  className={cn(
                    "flex min-h-11 items-center gap-2 rounded-lg border bg-card px-2.5 py-1 text-left outline-none transition-colors hover:border-foreground/40 focus-visible:ring-2 focus-visible:ring-ring md:min-h-10",
                    selected ? "border-primary bg-pp-teal-soft" : "border-border",
                  )}
                >
                  <StatusGlyph status={status} />
                  <span className="leading-tight">
                    <span className="block font-condensed text-[13px] font-semibold text-foreground">{site.shortName}</span>
                    <span className="block text-[11px] text-foreground">{statusLine}</span>
                  </span>
                </button>
                <span id={`site-detail-${site.id}`} hidden>{site.name}: {detail}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
