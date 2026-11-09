import { Download } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { exampleUrl, templateUrl, type TemplateCatalog, type TemplateName } from "@/lib/network-api";
import { cn } from "@/lib/utils";

export const OPTIONAL_BLANK_NOTE = "Leave it blank if you don't know it; a blank never becomes zero.";
// Given coordinates skip the Census lookup, so no tract rates are filled in (reverse geocoding is deferred, W2-06 §4).
// The examples differ by mode, so none is offered or asked about before a network type is chosen.
export const CHOOSE_MODE_NOTE = "Choose Pantry or Retail under 2. Network settings to get an example.";
export const LOCATED_RATES_NOTE = "A pantry given latitude and longitude is never looked up, so it gets no Census rates: fill in both poverty_rate and snap_rate, or exclude it in Settings before a Pantry comparison.";

type Props = {
  catalog: TemplateCatalog;
  /** Why each unavailable example can't be downloaded, read from the API's error envelope. */
  exampleReasons: Partial<Record<TemplateName, string>>;
};

/** V1-SPEC §6.1: every template with blank/example downloads and a guide to every column. */
export function TemplateGuide({ catalog, exampleReasons }: Props) {
  return (
    <div className="grid gap-4">
      {catalog.notes.length > 0 && (
        <ul className="grid gap-1 rounded-xl border border-border bg-card px-4 py-3 text-sm">
          {catalog.notes.map((note) => <li key={note}>{note}</li>)}
        </ul>
      )}
      {catalog.templates.map((template) => {
        const file = `${template.name}.csv`;
        const headingId = `template-${template.name}`;
        const reasonId = `template-${template.name}-example-reason`;
        const reason = exampleReasons[template.name];
        return (
          <section key={template.name} aria-labelledby={headingId} className="grid gap-3 rounded-xl border border-border bg-card p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="grid gap-1">
                <h3 id={headingId} className="flex flex-wrap items-center gap-2 text-base font-semibold">
                  <code className="font-mono">{file}</code>
                  <span className={cn("rounded-full border px-2 py-0.5 text-xs font-medium", template.required ? "border-foreground/30" : "border-dashed border-border text-muted-foreground")}>
                    {template.required ? "Required file" : "Optional file"}
                  </span>
                </h3>
                <p className="text-sm text-muted-foreground">{template.description}</p>
                {template.name === "locations" && catalog.mode !== "RETAIL" && <p className="text-sm">{LOCATED_RATES_NOTE}</p>}
              </div>
              <div className="flex flex-wrap items-start gap-2">
                <a href={templateUrl(template.name)} download={file} className={buttonVariants({ variant: "outline", size: "sm" })}
                  aria-label={`Download blank ${file}`}>
                  <Download aria-hidden="true" /> Blank
                </a>
                {template.example_available && catalog.mode ? (
                  <a href={exampleUrl(template.name, catalog.mode)} download={`${template.name}-example.csv`} className={buttonVariants({ variant: "outline", size: "sm" })}
                    aria-label={`Download example ${file}`}>
                    <Download aria-hidden="true" /> Example
                  </a>
                ) : (
                  <div className="grid max-w-56 gap-1">
                    <Button variant="outline" size="sm" disabled aria-label={`Download example ${file}`} aria-describedby={reasonId}>
                      <Download aria-hidden="true" /> Example
                    </Button>
                    <p id={reasonId} className="text-xs text-muted-foreground">{catalog.mode ? `Example not available yet${reason ? `: ${reason}` : "."}` : CHOOSE_MODE_NOTE}</p>
                  </div>
                )}
              </div>
            </div>
            <div className="overflow-x-auto rounded-lg border border-border" role="group" aria-label={`Columns of ${file}`} tabIndex={0}>
              <table className="w-full min-w-[44rem] border-collapse text-left text-sm">
                <thead className="bg-muted/60 text-xs text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">Column</th>
                    <th scope="col" className="px-3 py-2 font-medium">Required</th>
                    <th scope="col" className="px-3 py-2 font-medium">Unit</th>
                    <th scope="col" className="px-3 py-2 font-medium">What it means</th>
                    <th scope="col" className="px-3 py-2 font-medium">Effect on the plan</th>
                  </tr>
                </thead>
                <tbody>
                  {template.columns.map((column) => (
                    <tr key={column.name} className="border-t border-border align-top">
                      <th scope="row" className="px-3 py-2 font-normal"><code className="font-mono text-[13px] font-medium">{column.name}</code></th>
                      <td className="px-3 py-2">{column.required ? "Required" : "Optional"}</td>
                      <td className="px-3 py-2 text-muted-foreground">{column.unit ?? "No unit"}</td>
                      <td className="px-3 py-2">
                        <p>{column.meaning}</p>
                        {column.allowed_values.length > 0 && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            Allowed: {column.allowed_values.map((value, i) => <span key={value}>{i > 0 && ", "}<code className="font-mono text-foreground">{value}</code></span>)}
                          </p>
                        )}
                        {!column.required && <p className="mt-1 text-xs text-muted-foreground">{OPTIONAL_BLANK_NOTE}</p>}
                      </td>
                      <td className="px-3 py-2">{column.effect_on_plan}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </div>
  );
}
