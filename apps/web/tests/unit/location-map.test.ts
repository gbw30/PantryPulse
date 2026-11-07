// covers: V1-A13
import { expect, it } from "vitest";
import { placeLocations } from "@/components/overview/location-map";
import { example } from "./contract-examples";

const locations = example("LocationList").locations;

it("places located sites by their coordinates and lists the rest instead of guessing", () => {
  const { placed, unplaced } = placeLocations(locations);
  expect(unplaced.map((l) => l.location_id)).toEqual(["P-12"]);
  const at = Object.fromEntries(placed.map((p) => [p.location.location_id, p]));
  expect(Object.keys(at)).toEqual(["H-1", "P-07"]);
  // The hub is west and south of Eastside Pantry.
  expect(at["H-1"].x).toBeLessThan(at["P-07"].x);
  expect(at["H-1"].y).toBeGreaterThan(at["P-07"].y);
  for (const v of placed.flatMap((p) => [p.x, p.y])) {
    expect(v).toBeGreaterThanOrEqual(0);
    expect(v).toBeLessThanOrEqual(100);
  }
});

it("a single located site sits in the middle", () => {
  expect(placeLocations([locations[0]]).placed[0]).toMatchObject({ x: 50, y: 50 });
});
