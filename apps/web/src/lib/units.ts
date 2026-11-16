// The app's one display rule for quantities in a product's own unit. Units are free text from the CSVs.

export function pluralize(unit: string) {
  // Units are free text: only the last word takes a plural ("fluid ounces"), and only when it is a plain word that is
  // not an abbreviation ("fl oz", "dz", "oz.") or an all-caps code ("BOX", "FOOD BOX"); anything else stays as written.
  const head = unit.slice(0, unit.lastIndexOf(" ") + 1);
  const word = unit.slice(head.length);
  if (/^(each|ea|oz|g|kg|mg|ml|l|dz|doz)$/i.test(word) || !/^[a-z]+$/i.test(word) || word === word.toUpperCase()) return unit;
  if (/(ss|x|z|ch|sh)$/i.test(word)) return `${unit}es`;
  if (/s$/i.test(word)) return unit; // already plural ("lbs", "meals")
  if (/[^aeiou]y$/i.test(word)) return `${unit.slice(0, -1)}ies`;
  return `${unit}s`;
}

/** "55 cases": one product's quantity in its own unit, never combined with another product's. Singular only when the
 *  number as shown is 1 (1.0004 shows "1 box"); the plural is the app's shared rule ("2 lbs", "2 oz"). */
export function formatUnits(n: number, unit: string) {
  const shown = n.toLocaleString("en-US");
  return `${shown} ${shown === "1" ? unit : pluralize(unit)}`;
}
