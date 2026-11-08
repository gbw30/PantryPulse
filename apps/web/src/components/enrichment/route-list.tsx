import type { Schema } from "@/lib/planning-api";

type RouteEntry = Schema["RouteEntry"];

const fetchedDate = (instant: string) =>
  new Date(instant).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });

/** How each route's distance was found (V1-SPEC §6.3). */
export function routeMethodLabel(route: RouteEntry) {
  if (route.method === "google_road") return `Google road distance, fetched ${route.fetched_at ? fetchedDate(route.fetched_at) : "date unknown"}`;
  if (route.method === "routes_csv") return "from routes.csv";
  return "straight-line estimate";
}

export function RouteList({ routes }: { routes: RouteEntry[] }) {
  if (routes.length === 0) return <p className="text-sm text-muted-foreground">No candidate routes yet.</p>;
  return (
    <div className="grid gap-2">
      <div className="max-h-[28rem] overflow-auto rounded-lg border border-border" role="group" aria-label="Scrollable list of routes" tabIndex={0}>
        <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
          <caption className="px-3 py-2 text-left font-medium">Routes ({routes.length.toLocaleString("en-US")})</caption>
          <thead className="sticky top-0 bg-muted text-xs text-muted-foreground">
            <tr>{["From", "To", "Road miles", "Travel time", "Method"].map((h) => <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {routes.map((route) => (
              <tr key={`${route.from_location_id}→${route.to_location_id}`} className="border-t border-border">
                <td className="px-3 py-2">{route.from_location_id}</td>
                <td className="px-3 py-2">{route.to_location_id}</td>
                <td className="px-3 py-2 tabular-nums">{route.road_miles ?? "Not given"}</td>
                <td className="px-3 py-2 tabular-nums">{route.travel_days} {route.travel_days === 1 ? "day" : "days"}</td>
                <td className="px-3 py-2">{routeMethodLabel(route)}{route.disabled && " · disabled by routes.csv"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        A straight-line estimate is the straight distance × 1.3 at an assumed 45 mph, converted to whole travel days. routes.csv overrides any computed value.
      </p>
    </div>
  );
}
