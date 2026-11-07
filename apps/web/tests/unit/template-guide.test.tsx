// covers: V1-A06
import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { TemplateGuide } from "@/components/import/template-guide";
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
