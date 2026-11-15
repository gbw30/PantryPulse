// covers: V1-A06
import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { UploadForm } from "@/components/import/upload-form";
import type { TemplateCatalog } from "@/lib/network-api";
import { example } from "./contract-examples";

// W5-UI05 (W4-03 ux-critic notes): the API's descriptions of optional files start "Optional.", and the form
// prefixed its own, so the routes and inbound hints read "Optional. Optional.".
it("every file hint says Required. or Optional. exactly once", () => {
  const templates = (["locations", "products", "inventory", "demand_history", "routes", "inbound", "donation_history"] as const).map((name, i) => ({
    ...example("TemplateCatalog").templates[0], name, required: i < 4,
    description: i < 4 ? "Every row." : "Optional. Overrides or adds what it lists.",
  })) as TemplateCatalog["templates"];
  render(<UploadForm templates={templates} files={{}} onChange={() => {}} />);
  for (const t of templates) {
    const hint = screen.getByLabelText(`${t.name}.csv (${t.required ? "required" : "optional"})`).getAttribute("aria-describedby")!;
    const text = document.getElementById(hint)!.textContent!;
    expect(text.match(/\bOptional\./g)?.length ?? 0, `${t.name}: ${text}`).toBe(t.required ? 0 : 1);
    expect(text.match(/\bRequired\./g)?.length ?? 0, `${t.name}: ${text}`).toBe(t.required ? 1 : 0);
  }
});
