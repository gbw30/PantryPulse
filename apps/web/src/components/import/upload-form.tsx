import { Input } from "@/components/ui/input";
import type { TemplateCatalog, TemplateName } from "@/lib/network-api";

export type ChosenFiles = Partial<Record<TemplateName, File>>;

// Extra guidance for the optional files (V1-SPEC §6.1 inbound and donation rules).
const OPTIONAL_HINTS: Partial<Record<TemplateName, string>> = {
  routes: "Overrides computed distances and travel days for the routes it lists.",
  inbound: "Confirmed deliveries arriving in the 7 forecast days after the snapshot date; later rows are kept and listed, not planned. Without this file, plans show “no scheduled deliveries provided”.",
  donation_history: "Donations received per location, product and day. A 0 means reported, nothing received; a missing day stays unknown, never zero.",
};

type Props = {
  templates: TemplateCatalog["templates"];
  files: ChosenFiles;
  onChange: (name: TemplateName, file: File | null) => void;
  disabled?: boolean;
};

/** One file input per template, required ones first as listed by the catalog. */
export function UploadForm({ templates, files, onChange, disabled = false }: Props) {
  return (
    <fieldset disabled={disabled} className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-2">
      <legend className="sr-only">Files to upload</legend>
      {templates.map((template) => {
        const id = `import-file-${template.name}`;
        const hint = [template.description, OPTIONAL_HINTS[template.name]].filter(Boolean).join(" ");
        const file = files[template.name];
        return (
          <div key={template.name} className="grid content-start gap-1.5">
            <label htmlFor={id} className="text-sm font-medium">
              <code className="font-mono">{template.name}.csv</code> ({template.required ? "required" : "optional"})
            </label>
            <Input id={id} type="file" accept=".csv,text/csv" aria-describedby={`${id}-hint`} className="h-10 py-1.5"
              onChange={(e) => onChange(template.name, e.target.files?.[0] ?? null)} />
            <p id={`${id}-hint`} className="text-xs text-muted-foreground">
              {template.required ? "Required. " : "Optional. "}{hint}
              {file && <span className="block text-foreground">{file.name} · {file.size.toLocaleString("en-US")} bytes</span>}
            </p>
          </div>
        );
      })}
    </fieldset>
  );
}
