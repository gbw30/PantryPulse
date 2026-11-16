// covers: V1-A20
import { expect, it } from "vitest";
import { formatUnits, pluralize } from "@/lib/units";

// Moved unchanged from scenario-lab.test.tsx (pluralize) and status.test.ts (formatUnits) in W5A-03.
// W5-SC01 (W4-03 ux-critic note): the builder's unit headers (wizard.tsx) and the Data Explorer's product
// names use this plural. "boxs" read as a typo.
it("pluralize writes -es after s-like endings, -ies after a consonant y, keeps each and an existing plural", () => {
  const cases = { oz: "oz", g: "g", kg: "kg", ml: "ml", box: "boxes", bunch: "bunches", dish: "dishes", glass: "glasses", case: "cases", bottle: "bottles",
    berry: "berries", tray: "trays", each: "each", lbs: "lbs", meals: "meals" };
  expect(Object.fromEntries(Object.keys(cases).map((unit) => [unit, pluralize(unit)]))).toEqual(cases);
});

// Units are free text from the CSVs: only a plain word takes a plural; abbreviations and all-caps codes stay as written.
it("pluralize keeps abbreviations, anything that isn't a plain word, and an all-caps unit as written", () => {
  const cases = { l: "l", L: "L", dz: "dz", doz: "doz", ea: "ea", mg: "mg", "fl oz": "fl oz", "oz.": "oz.", "24-pack": "24-pack",
    BOX: "BOX", EA: "EA", Box: "Boxes", Berry: "Berries", boxes: "boxes" };
  expect(Object.fromEntries(Object.keys(cases).map((unit) => [unit, pluralize(unit)]))).toEqual(cases);
});

it("pluralize a multi-word unit by its last word, when that word would take a plural on its own", () => {
  const cases = { "fluid ounce": "fluid ounces", "food box": "food boxes", "fl oz": "fl oz", "24-pack": "24-pack",
    "case of 12": "case of 12", "FOOD BOX": "FOOD BOX" };
  expect(Object.fromEntries(Object.keys(cases).map((unit) => [unit, pluralize(unit)]))).toEqual(cases);
});

// Singular only when the number as shown is 1, and one plural for every unit, so "lb" reads "2 lbs" and "oz" stays "2 oz".
it.each([[1.0004, "box", "1 box"], [2, "lb", "2 lbs"], [2, "oz", "2 oz"], [1.5, "box", "1.5 boxes"], [1, "lbs", "1 lbs"]])(
  "%s %s reads %s", (n, unit, text) => {
    expect(formatUnits(Number(n), String(unit))).toBe(text);
  },
);
