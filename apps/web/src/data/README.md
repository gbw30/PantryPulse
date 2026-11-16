# Bundled map data

Files here ship with the app, so the Overview map makes no request to another origin (V1-SPEC §6.6, V1-A03).

| File | What | Source | License |
|---|---|---|---|
| `us-cities.json` | 281 US places with a population of 100,000 or more: `{ name, state, lat, lon, pop }`, largest first | Natural Earth, "populated places (simple)", 1:10m, fetched 2026-11-16 from `nvkelso/natural-earth-vector` (`geojson/ne_10m_populated_places_simple.geojson`) | Public domain |

State and county outlines come from the `us-atlas` npm package (`counties-10m.json`, US Census Bureau cartographic boundaries; ISC license for the package, public-domain data).

Rebuild `us-cities.json` with `node scripts/data/build-us-cities.mjs <downloaded geojson>`. `pop` is Natural Earth's `pop_max` (metro area), used only to decide which names show at each zoom level.
