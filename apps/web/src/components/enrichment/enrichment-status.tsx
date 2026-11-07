import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ApiError, type Schema } from "@/lib/planning-api";
import { AttributeEditor } from "./attribute-editor";

type Status = Schema["EnrichmentStatus"];

const STATE_LABEL: Record<Status["state"], string> = { not_started: "not started", running: "running", done: "done", failed: "failed" };
const MISSING_LABEL: Record<Schema["EgpBlocker"]["missing"][number], string> = { poverty_rate: "poverty rate", snap_rate: "SNAP rate" };

type Props = {
  status: Status;
  onRetry: () => Promise<Schema["ForecastAccepted"]>;
  onSaveAttributes: (locationId: string, update: Schema["LocationAttributesUpdate"]) => Promise<unknown>;
};

/** Census geocoding and ACS attributes for one network (V1-SPEC §6.3), with EGP blockers (§6.2). */
export function EnrichmentStatusPanel({ status, onRetry, onSaveAttributes }: Props) {
  const [retry, setRetry] = useState<{ busy: boolean; message: string | null }>({ busy: false, message: null });

  async function retryLookups() {
    setRetry({ busy: true, message: null });
    try {
      const job = await onRetry();
      setRetry({ busy: false, message: `Lookups queued (job ${job.job_id.slice(0, 8)}). This list updates when they finish.` });
    } catch (error) {
      setRetry({ busy: false, message: `Couldn't retry (${(error instanceof ApiError ? error.code : "REQUEST_FAILED").replaceAll("_", " ").toLowerCase()}).` });
    }
  }

  return (
    <div className="grid gap-4">
      <p className="text-sm">
        Address and Census lookups: <span className="font-medium">{STATE_LABEL[status.state]}</span>
        {status.last_error && <span className="text-muted-foreground"> · last error: {status.last_error}</span>}
      </p>

      {status.egp_blockers.length > 0 && (
        <div role="alert" className="grid gap-1 rounded-xl border border-pp-warning/60 bg-card px-4 py-3 text-sm">
          <p className="font-medium">EGP_PI_INSPIRED is blocked until each location below has values entered or is excluded.</p>
          <ul className="ml-5 list-disc">
            {status.egp_blockers.map((b) => <li key={b.location_id}>{b.location_id}: {b.missing.map((m) => MISSING_LABEL[m]).join(", ")}</li>)}
          </ul>
          <p className="text-xs text-muted-foreground">No location is left out silently: enter its rates below, or exclude it explicitly.</p>
        </div>
      )}

      {(status.unmatched.length > 0 || status.state === "failed") && (
        <section aria-labelledby="unmatched-heading" className="grid gap-2 rounded-xl border border-border bg-card p-4 text-sm">
          <h3 id="unmatched-heading" className="font-semibold">Addresses not found</h3>
          {status.unmatched.length > 0 ? (
            <ul className="grid gap-2">
              {status.unmatched.map((u) => (
                <li key={u.location_id}>
                  <span className="font-medium">{u.location_id}</span> · {u.address}
                  <span className="block text-xs text-muted-foreground">{u.hint}</span>
                </li>
              ))}
            </ul>
          ) : <p>The lookup service could not be reached. Affected values stay unknown until a retry succeeds.</p>}
          <p className="text-xs text-muted-foreground">Fix the address or add latitude and longitude in locations.csv and re-import, or retry if the lookup service was unreachable.</p>
          <Button variant="outline" className="h-10 justify-self-start" disabled={retry.busy || status.state === "running"} onClick={retryLookups}>Retry lookups</Button>
          {retry.message && <p role="status">{retry.message}</p>}
        </section>
      )}

      <section aria-labelledby="attributes-heading" className="rounded-xl border border-border bg-card px-4 py-1">
        <h3 id="attributes-heading" className="pt-3 text-sm font-semibold">Poverty and SNAP rates by location</h3>
        {status.locations.map((location) => (
          <AttributeEditor key={`${location.location_id}:${location.state}:${location.poverty_rate}:${location.snap_rate}`} location={location}
            onSave={(update) => onSaveAttributes(location.location_id, update)} />
        ))}
      </section>
    </div>
  );
}
