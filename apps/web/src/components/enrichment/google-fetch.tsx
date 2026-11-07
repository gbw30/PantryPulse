import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ApiError, type Schema } from "@/lib/planning-api";

type Props = {
  configured: boolean;
  onPreview: () => Promise<Schema["GoogleLookupPreview"]>;
  onFetch: () => Promise<Schema["ForecastAccepted"]>;
};

const failure = (error: unknown) => (error instanceof ApiError ? error.code : "REQUEST_FAILED").replaceAll("_", " ").toLowerCase();

/** Road distances from the user's own key: always shows the lookup count before any call is made. */
export function GoogleFetch({ configured, onPreview, onFetch }: Props) {
  const [preview, setPreview] = useState<Schema["GoogleLookupPreview"] | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function ask() {
    setBusy(true);
    setMessage(null);
    try { setPreview(await onPreview()); } catch (error) { setMessage(`Couldn't count the lookups (${failure(error)}).`); } finally { setBusy(false); }
  }

  async function confirm() {
    setBusy(true);
    try {
      await onFetch();
      setMessage("Google lookups queued. Route labels update when the job finishes.");
    } catch (error) {
      setMessage(`Couldn't start the lookups (${failure(error)}).`);
    } finally { setBusy(false); setPreview(null); }
  }

  return (
    <div className="grid gap-2">
      <Button variant="outline" className="h-10 justify-self-start" disabled={!configured || busy} onClick={ask} aria-describedby="google-fetch-note">
        Fetch Google road distances
      </Button>
      <p id="google-fetch-note" className="text-xs text-muted-foreground">
        {configured ? "Uses your key for candidate routes; results are cached and labeled with their fetch date." : "Add a Google Maps key above to fetch road distances."}
      </p>
      {message && <p role="status" className="text-sm">{message}</p>}
      <Dialog open={preview !== null} onOpenChange={(open) => { if (!open) setPreview(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Fetch road distances from Google?</DialogTitle>
            <DialogDescription>
              This will make {preview?.lookups.toLocaleString("en-US")} Google lookups on your key. {preview?.cached.toLocaleString("en-US")} routes are already cached and won&apos;t be fetched again.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPreview(null)}>Cancel</Button>
            <Button onClick={confirm} disabled={busy}>Make {preview?.lookups.toLocaleString("en-US")} lookups</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
