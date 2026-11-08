import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, type Schema } from "@/lib/planning-api";

type Attributes = Schema["LocationAttributes"];
type Update = Schema["LocationAttributesUpdate"];

const SHARE = /^(0(\.\d+)?|1(\.0+)?|\.\d+)$/;

export function sourceLine(location: Attributes) {
  if (location.state === "manual") return "Source: entered by you";
  if (location.state === "excluded") return "Excluded from EGP";
  if (location.state === "unknown" || !location.source) return "Source: unknown (lookup failed or not run yet)";
  return `Source: ${location.source}`;
}

/** One location's poverty and SNAP shares: Census values, a manual override, or an explicit exclusion. */
export function AttributeEditor({ location, onSave }: { location: Attributes; onSave: (update: Update) => Promise<unknown> }) {
  const [editing, setEditing] = useState(false);
  const [poverty, setPoverty] = useState(location.poverty_rate ?? "");
  const [snap, setSnap] = useState(location.snap_rate ?? "");
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = `attr-${location.location_id.replace(/[^A-Za-z0-9_-]/g, "_")}`;

  async function save(update: Update) {
    setBusy(true);
    setProblem(null);
    try {
      await onSave(update);
      setEditing(false);
    } catch (error) {
      setProblem(`Couldn't save (${(error instanceof ApiError ? error.code : "REQUEST_FAILED").replaceAll("_", " ").toLowerCase()}).`);
    } finally { setBusy(false); }
  }

  function submit(event: { preventDefault(): void }) {
    event.preventDefault();
    const p = poverty.trim(), s = snap.trim();
    if (!SHARE.test(p) || !SHARE.test(s)) { setProblem("Enter each rate as a share between 0 and 1, for example 0.18."); return; }
    void save({ excluded: false, poverty_rate: p, snap_rate: s });
  }

  return (
    <div role="group" aria-label={`${location.location_id} attributes`} className="grid gap-2 border-t border-border py-3 first:border-t-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-sm">
          <span className="font-medium">{location.location_id}</span>
          {location.state !== "excluded" && (
            <span className="text-muted-foreground"> · poverty rate {location.poverty_rate ?? "unknown"} · SNAP rate {location.snap_rate ?? "unknown"}</span>
          )}
        </p>
        <div className="flex flex-wrap gap-2">
          {!editing && <Button variant="outline" size="sm" onClick={() => setEditing(true)}>Enter values</Button>}
          {location.state !== "excluded" && <Button variant="ghost" size="sm" disabled={busy} onClick={() => save({ excluded: true })}>Exclude from EGP</Button>}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">{sourceLine(location)}</p>
      {editing && (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <div className="grid gap-1">
            <Label htmlFor={`${id}-poverty`}>Poverty rate (0 to 1)</Label>
            <Input id={`${id}-poverty`} inputMode="decimal" value={poverty} onChange={(e) => setPoverty(e.target.value)} className="h-10 w-32" />
          </div>
          <div className="grid gap-1">
            <Label htmlFor={`${id}-snap`}>SNAP rate (0 to 1)</Label>
            <Input id={`${id}-snap`} inputMode="decimal" value={snap} onChange={(e) => setSnap(e.target.value)} className="h-10 w-32" />
          </div>
          <Button type="submit" className="h-10" disabled={busy}>Save</Button>
          <Button type="button" variant="outline" className="h-10" onClick={() => { setEditing(false); setProblem(null); }}>Cancel</Button>
        </form>
      )}
      {problem && <p role="alert" className="text-sm">{problem}</p>}
    </div>
  );
}
