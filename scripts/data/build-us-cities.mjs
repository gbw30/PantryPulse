// Rebuilds apps/web/src/data/us-cities.json: the city names the Overview map shows.
// Source: Natural Earth "populated places (simple)", 1:10m, public domain.
//   https://github.com/nvkelso/natural-earth-vector  geojson/ne_10m_populated_places_simple.geojson
// Usage: node scripts/data/build-us-cities.mjs <path to the downloaded geojson>
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const MIN_POP = 100_000;
const source = process.argv[2];
if (!source) {
  console.error("usage: node scripts/data/build-us-cities.mjs <ne_10m_populated_places_simple.geojson>");
  process.exit(2);
}

const { features } = JSON.parse(readFileSync(source, "utf8"));
const cities = features
  .map((f) => f.properties)
  .filter((p) => p.adm0_a3 === "USA" && Number(p.pop_max) >= MIN_POP)
  .map((p) => ({
    name: String(p.name),
    state: String(p.adm1name ?? ""),
    lat: Math.round(Number(p.latitude) * 1e4) / 1e4,
    lon: Math.round(Number(p.longitude) * 1e4) / 1e4,
    pop: Number(p.pop_max),
  }))
  .filter((c) => c.name && Number.isFinite(c.lat) && Number.isFinite(c.lon))
  .sort((a, b) => b.pop - a.pop || a.name.localeCompare(b.name));

if (cities.length < 50) throw new Error(`only ${cities.length} cities: wrong source file?`);
const out = fileURLToPath(new URL("../../apps/web/src/data/us-cities.json", import.meta.url));
writeFileSync(out, JSON.stringify(cities) + "\n");
console.log(`wrote ${cities.length} cities to ${out}`);
