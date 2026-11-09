// covers: V1-A06
import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { CHOOSE_MODE_NOTE, TemplateGuide } from "@/components/import/template-guide";
import { example } from "./contract-examples";

const catalog = example("TemplateCatalog");

function columnRow(template: string, column: string) {
  const section = screen.getByRole("region", { name: new RegExp(`^${template}\\.csv`) });
  return within(section).getByRole("row", { name: new RegExp(`^${column}\\b`) });
}

it("every column renders required/optional, unit, meaning and effect on plan", () => {
  render(<TemplateGuide catalog={catalog} exampleReasons={{}} />);
  for (const template of catalog.templates) {
    for (const column of template.columns) {
      const row = columnRow(template.name, column.name);
      expect(within(row).getByText(column.required ? "Required" : "Optional")).toBeVisible();
      expect(within(row).getByText(column.unit ?? "No unit")).toBeVisible();
      expect(row).toHaveTextContent(column.meaning);
      expect(row).toHaveTextContent(column.effect_on_plan);
      for (const value of column.allowed_values) expect(within(row).getByText(value)).toBeVisible();
    }
  }
});

it("the locations guide says a pantry given coordinates also needs both rates, or an exclusion (W2-06 carry-in)", () => {
  // Given coordinates skip the Census lookup, so the tract's rates are never filled in (W2-06 §4).
  render(<TemplateGuide catalog={catalog} exampleReasons={{}} />);
  const locations = screen.getByRole("region", { name: /^locations\.csv/ });
  expect(locations).toHaveTextContent(/pantry given latitude and longitude.*both poverty_rate and snap_rate.*exclude it in Settings/);
  for (const other of catalog.templates.filter((t) => t.name !== "locations")) {
    expect(screen.getByRole("region", { name: new RegExp(`^${other.name}\\.csv`) })).not.toHaveTextContent(/given latitude and longitude/);
  }
});

it("a Retail locations guide (stores have no rates) has no rates note", () => {
  render(<TemplateGuide catalog={{ ...example("TemplateCatalog"), mode: "RETAIL" }} exampleReasons={{}} />);
  expect(screen.getByRole("region", { name: /^locations\.csv/ })).not.toHaveTextContent(/given latitude and longitude/);
});

it("optional blank columns say they never become zero", () => {
  // Strip the server's own wording so the guide itself must say it.
  const plain = example("TemplateCatalog");
  for (const template of plain.templates) for (const column of template.columns) column.meaning = `Meaning of ${column.name}.`;
  render(<TemplateGuide catalog={plain} exampleReasons={{}} />);
  for (const template of plain.templates) {
    for (const column of template.columns) {
      const row = columnRow(template.name, column.name);
      if (column.required) expect(row).not.toHaveTextContent(/never becomes zero/);
      else expect(row).toHaveTextContent("Leave it blank if you don't know it; a blank never becomes zero.");
    }
  }
});

it("shows the catalog notes and whether each file is required", () => {
  render(<TemplateGuide catalog={catalog} exampleReasons={{}} />);
  for (const note of catalog.notes) expect(screen.getByText(note)).toBeVisible();
  for (const template of catalog.templates) {
    const section = screen.getByRole("region", { name: new RegExp(`^${template.name}\\.csv`) });
    expect(within(section).getByText(template.required ? "Required file" : "Optional file")).toBeVisible();
    expect(within(section).getByText(template.description)).toBeVisible();
  }
});

const CHOOSE_MODE = CHOOSE_MODE_NOTE;

it("an example downloads in the catalog's own mode, Retail included (CR-w3-samples-3)", () => {
  for (const mode of ["PANTRY", "RETAIL"] as const) {
    const available = { ...catalog, mode, templates: catalog.templates.map((t) => ({ ...t, example_available: true })) };
    const { unmount } = render(<TemplateGuide catalog={available} exampleReasons={{}} />);
    for (const t of catalog.templates) {
      expect(screen.getByRole("link", { name: `Download example ${t.name}.csv` })).toHaveAttribute("href", `/api/v1/templates/${t.name}.csv?kind=example&mode=${mode}`);
    }
    unmount();
  }
});

it("with no network type chosen, an example asks for one instead of offering a download", () => {
  render(<TemplateGuide catalog={{ ...catalog, mode: null }} exampleReasons={{}} />);
  for (const t of catalog.templates) {
    const section = screen.getByRole("region", { name: new RegExp(`^${t.name}\\.csv`) });
    expect(within(section).getByRole("button", { name: `Download example ${t.name}.csv` })).toBeDisabled();
    expect(section).toHaveTextContent(CHOOSE_MODE);
  }
});
