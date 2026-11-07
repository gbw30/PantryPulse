import { useMemo } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { NetworkMode } from "@/lib/mode-vocabulary";

export type NetworkSettingsValue = {
  name: string;
  /** Chosen once per network; no default. */
  mode: NetworkMode | null;
  timezone: string;
  /** null: use the shown default (day after the last history date). "" when the user cleared it. */
  asOfDate: string | null;
};

export const dayAfter = (isoDate: string) => {
  const day = new Date(`${isoDate}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + 1);
  return day.toISOString().slice(0, 10);
};

/** The as_of_date to send: the user's value, else the shown default; undefined lets the server default it. */
export function asOfDateToSend(value: NetworkSettingsValue, lastHistory: string | null) {
  if (value.asOfDate !== null) return value.asOfDate || undefined;
  return lastHistory ? dayAfter(lastHistory) : undefined;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const cellsOf = (line: string) => {
  if (!line.includes('"')) return line.split(",");
  const cells: string[] = [];
  let cell = "", quoted = false;
  for (const ch of line) {
    if (ch === '"') quoted = !quoted;
    else if (ch === "," && !quoted) { cells.push(cell); cell = ""; }
    else cell += ch;
  }
  cells.push(cell);
  return cells;
};

/**
 * Latest `date` in a demand_history.csv, read in chunks so a 150 MB file never sits in memory as one
 * string. Rows can be in any order. null when there is no `date` column or no valid date.
 */
export async function lastHistoryDate(file: Blob, chunkBytes = 4 << 20): Promise<string | null> {
  const decoder = new TextDecoder("utf-8");
  let column = -1, carry = "", latest: string | null = null, header = true;
  const take = (line: string) => {
    const cells = cellsOf(line.replace(/\r$/, ""));
    if (header) {
      header = false;
      column = cells.findIndex((cell) => cell.replace(/^﻿/, "").trim() === "date");
      return;
    }
    const value = cells[column]?.trim();
    if (value && ISO_DATE.test(value) && (latest === null || value > latest)) latest = value;
  };
  for (let start = 0; start < file.size; start += chunkBytes) {
    const text = carry + decoder.decode(new Uint8Array(await file.slice(start, start + chunkBytes).arrayBuffer()), { stream: true });
    const lines = text.split("\n");
    carry = lines.pop() ?? "";
    for (const line of lines) {
      take(line);
      if (column < 0) return null;
    }
  }
  carry += decoder.decode();
  if (carry.trim()) take(carry);
  return column < 0 ? null : latest;
}

const MODES: { mode: NetworkMode; label: string; hint: string }[] = [
  { mode: "PANTRY", label: "Pantry network", hint: "Hubs and pantries. Plans aim to help the most people." },
  { mode: "RETAIL", label: "Retail network", hint: "Distribution centers and stores. Plans aim to sell stock before it expires." },
];

type Props = {
  value: NetworkSettingsValue;
  onChange: (value: NetworkSettingsValue) => void;
  lastHistoryDate: string | null;
  /** Re-importing into an existing network: its name, mode and timezone are fixed. */
  existing?: boolean;
  disabled?: boolean;
};

/** Settings entered at import (V1-SPEC §6.1): name, fixed mode, one timezone and the snapshot date. */
export function NetworkSettings({ value, onChange, lastHistoryDate: last, existing = false, disabled = false }: Props) {
  const zones = useMemo(() => {
    const all = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [];
    return all.includes(value.timezone) ? all : [value.timezone, ...all];
  }, [value.timezone]);
  const set = (patch: Partial<NetworkSettingsValue>) => onChange({ ...value, ...patch });
  const shownAsOf = value.asOfDate ?? (last ? dayAfter(last) : "");

  return (
    <fieldset disabled={disabled} className="grid gap-4 rounded-xl border border-border bg-card p-4 md:grid-cols-2">
      <legend className="sr-only">Network settings</legend>
      {!existing && (
        <>
          <div className="grid gap-1.5">
            <Label htmlFor="import-network-name">Network name</Label>
            <Input id="import-network-name" value={value.name} onChange={(e) => set({ name: e.target.value })} autoComplete="off" className="h-10" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="import-timezone">Network timezone</Label>
            <select id="import-timezone" value={value.timezone} onChange={(e) => set({ timezone: e.target.value })} aria-describedby="import-timezone-note"
              className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring">
              {zones.map((zone) => <option key={zone} value={zone}>{zone}</option>)}
            </select>
            <p id="import-timezone-note" className="text-xs text-muted-foreground">
              One timezone for the whole network. Every location plans on this network&apos;s day boundaries; per-location timezones are not supported.
            </p>
          </div>
          <div className="grid gap-2 md:col-span-2" role="radiogroup" aria-labelledby="import-mode-label" aria-describedby="import-mode-note">
            <span id="import-mode-label" className="text-sm font-medium">Network mode</span>
            <RadioGroup value={value.mode ?? ""} onValueChange={(mode) => set({ mode: mode as NetworkMode })} className="grid gap-2 sm:grid-cols-2" aria-labelledby="import-mode-label">
              {MODES.map(({ mode, label, hint }) => (
                <label key={mode} htmlFor={`import-mode-${mode}`} className="flex cursor-pointer items-start gap-2 rounded-lg border border-border p-3 has-[[data-state=checked]]:border-pp-teal">
                  <RadioGroupItem id={`import-mode-${mode}`} value={mode} className="mt-0.5" aria-describedby={`import-mode-${mode}-hint`} />
                  <span className="grid gap-0.5">
                    <span className="text-sm font-medium">{label}</span>
                    <span id={`import-mode-${mode}-hint`} className="text-xs text-muted-foreground">{hint}</span>
                  </span>
                </label>
              ))}
            </RadioGroup>
            <p id="import-mode-note" className="text-xs text-muted-foreground">Required, no default. The mode is fixed for this network once it is created.</p>
          </div>
        </>
      )}
      <div className="grid gap-1.5">
        <Label htmlFor="import-as-of">Stock snapshot date (as_of_date)</Label>
        <Input id="import-as-of" type="date" value={shownAsOf} min={last ?? undefined} onChange={(e) => set({ asOfDate: e.target.value })}
          aria-describedby="import-as-of-note" className="h-10" />
        <p id="import-as-of-note" className="text-xs text-muted-foreground">
          {last
            ? `Defaults to the day after your last history date (${last}). Planning starts the day after it; history dated later is rejected.`
            : "The date your inventory file describes. Choose demand_history.csv to fill in the default: the day after your last history date."}
        </p>
      </div>
    </fieldset>
  );
}
