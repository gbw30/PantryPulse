import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, type Schema } from "@/lib/planning-api";

type Props = {
  configured: boolean;
  onSave: (key: string) => Promise<Schema["LocalSettings"]>;
  onRemove: () => Promise<Schema["LocalSettings"]>;
};

const failure = (error: unknown) => (error instanceof ApiError ? error.code : "REQUEST_FAILED").replaceAll("_", " ").toLowerCase();

/**
 * Write-only Google Maps key (V1-SPEC §6.3). The input is uncontrolled, so the key never enters React
 * state or a DOM attribute; it is cleared after every save attempt and only "configured" is shown.
 */
export function GoogleKeyForm({ configured: initial, onSave, onRemove }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [configured, setConfigured] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function save(event: { preventDefault(): void }) {
    event.preventDefault();
    const key = input.current?.value.trim() ?? "";
    if (input.current) input.current.value = "";
    if (!key) { setMessage("Paste a key first."); return; }
    setBusy(true);
    try {
      setConfigured((await onSave(key)).google_maps_configured);
      setMessage("Key saved. It is stored locally and is never shown again.");
    } catch (error) {
      setMessage(`Couldn't save the key (${failure(error)}).`);
    } finally { setBusy(false); }
  }

  async function remove() {
    setBusy(true);
    try {
      setConfigured((await onRemove()).google_maps_configured);
      setMessage("Key removed. Routes use the straight-line estimate.");
    } catch (error) {
      setMessage(`Couldn't remove the key (${failure(error)}).`);
    } finally { setBusy(false); }
  }

  return (
    <form onSubmit={save} className="grid gap-3">
      <p className="text-sm font-medium">Google Maps key: {configured ? "configured" : "not configured"}</p>
      <div className="grid gap-1.5 sm:max-w-md">
        <Label htmlFor="google-maps-key">Google Maps API key</Label>
        <Input ref={input} id="google-maps-key" type="password" autoComplete="off" spellCheck={false} className="h-10"
          aria-describedby="google-maps-key-note" placeholder={configured ? "Paste a new key to replace it" : "Paste your key"} />
        <p id="google-maps-key-note" className="text-xs text-muted-foreground">
          Optional. Without a key, routes use a straight-line estimate. Your key is stored only on this machine and is never sent back to the browser.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" className="h-10" disabled={busy}>Save key</Button>
        {configured && <Button type="button" variant="outline" className="h-10" disabled={busy} onClick={remove}>Remove key</Button>}
      </div>
      {message && <p role="status" className="text-sm">{message}</p>}
    </form>
  );
}
