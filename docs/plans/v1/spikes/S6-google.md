# Spike S6: Google road distances (W1-D01)

Status: decided from Google's public documentation, read on 2026-11-07. **No key was used and no Google API was called.** The fixture is Google's documented example, labeled as such.

## Choice: Routes API `computeRouteMatrix`

The legacy Distance Matrix API is out. Its overview page says it "is in Legacy status. As of October 2026, Distance Matrix API (Legacy) can no longer be enabled for new Google Cloud projects", and points to the Routes API ([overview](https://developers.google.com/maps/documentation/distance-matrix/overview)). A user creating a key today can't enable it.

## Request shape ([guide](https://developers.google.com/maps/documentation/routes/compute_route_matrix), [reference](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRouteMatrix))

```
POST https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix
Content-Type: application/json
X-Goog-Api-Key: <user key>
X-Goog-FieldMask: originIndex,destinationIndex,status,condition,distanceMeters,duration

{"origins": [{"waypoint": {"location": {"latLng": {"latitude": 30.44, "longitude": -84.28}}}}],
 "destinations": [{"waypoint": {"location": {"latLng": {"latitude": 29.65, "longitude": -82.32}}}}],
 "travelMode": "DRIVE", "routingPreference": "TRAFFIC_UNAWARE"}
```

- The field mask is **required**; there is no default. It **must include `status`**, "as otherwise all messages will appear to be OK".
- Use `TRAFFIC_UNAWARE`. Traffic-aware preferences move the request to the Pro SKU, and a planning day doesn't need live traffic. Then `duration` equals `staticDuration`.
- Send lat/lng waypoints only (we have coordinates after geocoding). The 50-waypoint limit applies only to address/placeId waypoints.

## Limits ([usage and billing](https://developers.google.com/maps/documentation/routes/usage-and-billing))

- Elements per request: origins × destinations ≤ **625** (≤ 100 with `TRAFFIC_AWARE_OPTIMAL` or transit).
- Rate: **3,000 elements per minute**, adjustable in the Cloud console.

## Billing and the up-front lookup count

- Billed **per element** = origins × destinations, including pairs we don't need.
- SKUs ([pricing](https://developers.google.com/maps/billing-and-pricing/pricing), per 1,000 elements): **Essentials** (basic features; free cap 10,000/month, then $5.00), **Pro** (traffic-aware; free cap 5,000, then $10.00), **Enterprise** (two-wheeler, large vehicle; free cap 1,000, then $15.00). Free caps are shared across all projects on the user's billing account.
- **Batching, so the count we show is the count billed:** one request per receiver, with that receiver's uncached candidate senders as origins and the receiver as the single destination. Each request is ≤ 10 elements (k = 10), and no unwanted pairs are billed. A dense origins × destinations matrix over a sparse candidate set would bill pairs we discard.
- **Preview count** (`GoogleLookupPreview.lookups`) = the number of candidate routes whose (origin, destination) coordinates are not in `google_distance_cache` and are not overridden by `routes.csv`. That equals the billed element count for the fetch. The UI shows it before the user confirms, along with "billed to your Google account".
- At 100 locations with k = 10, a full fetch is at most about 1,000 elements, inside the Essentials free cap for one month if the account has no other usage.

## Response and errors

- REST returns a **JSON array**, one element per pair, **not in row-major order**. Key on `originIndex`/`destinationIndex`. (Streaming is gRPC-only.)
- Element: `status` (`{}` when OK), `condition` (`ROUTE_EXISTS` or `ROUTE_NOT_FOUND`), `distanceMeters` (int), `duration` (string of seconds ending in `s`, e.g. `"160s"`, up to nine fractional digits).
- Per-element errors appear only in the affected element's `status`/`condition`. `ROUTE_NOT_FOUND` has no distance or duration; that route keeps its straight-line estimate.
- A malformed request fails as a whole, with a `google.rpc.Status` body `{"code", "message", "details"}`. HTTP codes for an invalid key, permission denied or quota exceeded were **not found** on the pages read. The client treats any non-200 as a provider error, keeps straight-line routes, and never echoes the request or headers (the key) into the error.

## Fixture

`apps/api/tests/fixtures/google/route-matrix-documented.json`: `recorded.kind = "documented_example"`, transcribed from the guide page (2 origins × 2 destinations, `TRAFFIC_AWARE`, four `ROUTE_EXISTS` elements, out of order). The key placeholder is literal text, not a key.
