// covers: V1-A20
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// W5A-01: the "Pantry Ledger with Market Fresh accents" tokens (spec §4.10), read from the stylesheet itself.
const css = readFileSync(path.resolve(__dirname, "../../src/app/globals.css"), "utf8");

function declarations(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  expect(start, `${selector} block`).toBeGreaterThanOrEqual(0);
  const body = css.slice(start, css.indexOf("\n}", start));
  return Object.fromEntries([...body.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((match) => [match[1], match[2].trim().toLowerCase()]));
}

const light = declarations(":root");
const dark = declarations(".dark");
const theme = declarations("@theme inline");
const THEMES = { light, dark: { ...light, ...dark } };

/** Follows var(--x) the way the cascade does: a dark value wins, else the :root one. */
function color(tokens: Record<string, string>, name: string): string {
  const value = tokens[name];
  expect(value, `${name} is declared`).toBeDefined();
  const reference = /^var\((--[\w-]+)\)$/.exec(value);
  if (reference) return color(tokens, reference[1]);
  expect(value, `${name} is a 6-digit hex`).toMatch(/^#[0-9a-f]{6}$/);
  return value;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16) / 255).map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG 2.x contrast ratio. */
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const LIGHT_VALUES = {
  "--pp-canvas": "#f3f1ea",
  "--pp-surface": "#fbfaf6",
  "--pp-ink": "#1b2a41",
  "--pp-ink-muted": "#566072",
  "--pp-border": "#dcd8cb",
  "--pp-action": "#2c6a3c",
  "--pp-tint": "#e6efdb",
  "--pp-danger": "#b03a26",
  "--pp-danger-soft": "#fbe6e0",
  "--pp-warning": "#7d5a12",
  "--pp-warning-soft": "#fbeecb",
  "--pp-warning-fill": "#d99a1c",
};

// Text token -> every ground it is set on.
const TEXT_PAIRS: [string, string[]][] = [
  ["--pp-ink", ["--pp-canvas", "--pp-surface", "--pp-surface-muted", "--pp-tint"]],
  ["--pp-ink-muted", ["--pp-canvas", "--pp-surface", "--pp-surface-muted", "--pp-tint"]],
  ["--pp-action", ["--pp-canvas", "--pp-surface", "--pp-tint", "--pp-action-soft"]],
  ["--pp-danger", ["--pp-canvas", "--pp-surface", "--pp-danger-soft"]],
  ["--pp-warning", ["--pp-canvas", "--pp-surface", "--pp-warning-soft"]],
  ["--primary-foreground", ["--pp-action"]],
  ["--destructive-foreground", ["--pp-danger"]],
];

// Marks, never text (icons, markers, chart strokes): WCAG 1.4.11 asks 3:1.
const MARK_PAIRS: [string, string[]][] = [
  ["--pp-neutral", ["--pp-canvas", "--pp-surface", "--pp-surface-muted"]],
  ["--pp-forecast", ["--pp-canvas", "--pp-surface", "--pp-surface-muted"]],
];

describe("design tokens", () => {
  it.each(Object.entries(LIGHT_VALUES))("light %s is %s", (name, value) => {
    expect(light[name]).toBe(value);
  });

  it("the rule is drawn in ink and the soft action ground is the tint", () => {
    expect(light["--pp-rule"]).toBe("var(--pp-ink)");
    expect(color(light, "--pp-action-soft")).toBe(light["--pp-tint"]);
  });

  it.each(["--pp-canvas", "--pp-surface", "--pp-ink", "--pp-ink-muted", "--pp-border", "--pp-action", "--pp-tint", "--pp-danger", "--pp-danger-soft", "--pp-warning", "--pp-warning-soft", "--pp-neutral"])(
    "%s has its own dark value",
    (name) => {
      expect(dark[name]).toMatch(/^#[0-9a-f]{6}$/);
      expect(dark[name]).not.toBe(light[name]);
    },
  );

  it("the old teal names are gone", () => {
    expect(css).not.toMatch(/pp-teal/);
  });

  it("Tailwind gets the serif family and the new color utilities", () => {
    expect(theme["--font-serif"]).toMatch(/^var\(--font-plex-serif\), "ibm plex serif"/);
    for (const name of ["action", "action-soft", "tint", "rule", "danger-soft", "warning-soft", "warning-fill"]) {
      expect(theme[`--color-pp-${name}`], `--color-pp-${name}`).toBe(`var(--pp-${name})`);
    }
  });

  describe.each(Object.entries(THEMES))("%s theme", (_, tokens) => {
    it.each(TEXT_PAIRS.flatMap(([text, grounds]) => grounds.map((ground) => [text, ground])))("text %s on %s is at least 4.5:1", (text, ground) => {
      expect(contrast(color(tokens, text), color(tokens, ground))).toBeGreaterThanOrEqual(4.5);
    });

    it.each(MARK_PAIRS.flatMap(([mark, grounds]) => grounds.map((ground) => [mark, ground])))("mark %s on %s is at least 3:1", (mark, ground) => {
      expect(contrast(color(tokens, mark), color(tokens, ground))).toBeGreaterThanOrEqual(3);
    });
  });
});
