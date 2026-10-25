import { cn } from "@/lib/utils";
import type { ForecastMethod, Product, SeriesMethod, Site } from "./types";

// Forecast method in plain words. Known provider names get a label; anything else is shown verbatim.
const PROVIDER_LABEL: Record<string, string> = {
  SEASONAL_NAIVE: "Seasonal-naive baseline",
  MOVING_AVERAGE: "Moving-average baseline",
  CHRONOS2: "Chronos-2 model",
};

// Provider error codes recorded as the reason the requested method was replaced.
const FALLBACK_REASON: Record<string, string> = {
  INSUFFICIENT_DATA: "Too little history for the primary method",
  INVALID_PROVIDER_OUTPUT: "The primary method returned invalid output",
  PROVIDER_UNAVAILABLE: "The primary model was unavailable",
};

export function providerLabel(provider: string) {
  return PROVIDER_LABEL[provider] ?? provider;
}

export function fallbackReasonLabel(reason: string | null) {
  if (!reason) return "No reason was recorded.";
  const plain = FALLBACK_REASON[reason];
  return plain ? `${plain} (${reason}).` : `Reason: ${reason}.`;
}

/** Accessible-name fragment for markers and chips; undefined when no fallback was used. */
export function fallbackNameFragment(method: ForecastMethod | undefined) {
  return method?.fallbackUsed ? `fallback forecast: ${providerLabel(method.provider)}` : undefined;
}

/** Visible note for a series whose requested method failed and another filled in. */
export function FallbackNote({ method, className }: { method: ForecastMethod; className?: string }) {
  return (
    <div data-fallback-note className={cn("rounded-md border border-pp-warning bg-card px-2.5 py-1.5 text-xs text-foreground", className)}>
      <p><strong className="font-semibold">Fallback forecast</strong> · {providerLabel(method.provider)}</p>
      <p className="text-muted-foreground">{fallbackReasonLabel(method.fallbackReason)}</p>
    </div>
  );
}

/**
 * Footnote line: "all sites: X" when every beneficiary has series from one method, otherwise the
 * sites per method (with the product when a site's products differ) and the sites without a series.
 */
export function methodSummary(methods: SeriesMethod[], sites: Site[], products: Product[]) {
  if (methods.length === 0) return null;
  const label = (method: ForecastMethod) => `${providerLabel(method.provider)}${method.fallbackUsed ? ", fallback" : ""}`;
  const groups = new Map<string, SeriesMethod[]>();
  for (const method of methods) groups.set(label(method), [...(groups.get(label(method)) ?? []), method]);
  const beneficiaries = sites.filter((site) => site.role !== "HUB");
  const covered = new Set(methods.map((method) => method.siteId));
  const missing = beneficiaries.filter((site) => !covered.has(site.id));
  if (groups.size === 1 && missing.length === 0) return `Forecast method, all sites: ${[...groups.keys()][0]}`;

  const groupsBySite = new Map<string, Set<string>>();
  for (const method of methods) groupsBySite.set(method.siteId, (groupsBySite.get(method.siteId) ?? new Set()).add(label(method)));
  const parts = [...groups].map(([name, members]) => {
    const names = sites
      .filter((site) => members.some((member) => member.siteId === site.id))
      .map((site) => {
        if ((groupsBySite.get(site.id)?.size ?? 0) < 2) return site.shortName;
        const units = members.filter((member) => member.siteId === site.id).map((member) => products.find((product) => product.id === member.productId)?.unitPlural ?? member.productId);
        return `${site.shortName} (${units.join(", ")})`;
      });
    return `${name}: ${names.join(", ")}`;
  });
  if (missing.length > 0) parts.push(`No series: ${missing.map((site) => site.shortName).join(", ")}`);
  return `Forecast method by site. ${parts.join("; ")}`;
}
