"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { AppShell } from "@/components/shell/app-shell";
import { SampleBadge, useNetwork } from "@/components/shell/network-switcher";
import { networkApi, type Network } from "@/lib/network-api";
import { ApiError } from "@/lib/planning-api";
import { EnrichmentStatusPanel } from "./enrichment-status";
import { GoogleFetch } from "./google-fetch";
import { GoogleKeyForm } from "./google-key-form";
import { RouteList } from "./route-list";

type Load<T> = { status: "loading" } | { status: "error"; code: string } | { status: "ready"; value: T };

/** Reads `load` on mount and whenever `key` changes; `reload` re-reads without blanking the shown value. */
function useLoad<T>(load: (() => Promise<T>) | null, key: string) {
  const [state, setState] = useState<Load<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!load) return;
    let active = true;
    load().then(
      (value) => { if (active) setState({ status: "ready", value }); },
      (error: unknown) => { if (active) setState({ status: "error", code: error instanceof ApiError ? error.code : "REQUEST_FAILED" }); },
    );
    return () => { active = false; };
    // `load` is rebuilt every render; `key` names what it reads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);
  return { state, reload: useCallback(() => setAttempt((n) => n + 1), []) };
}

function Failed({ what, code, retry }: { what: string; code: string; retry: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
      {what} unavailable ({code.replaceAll("_", " ").toLowerCase()}).
      <Button variant="outline" size="sm" onClick={retry}>Retry</Button>
    </div>
  );
}

export function SettingsView() {
  return <AppShell active="settings"><SettingsContent /></AppShell>;
}

function SettingsContent() {
  const { network } = useNetwork();
  const settings = useLoad(() => networkApi.settings(), "settings");
  const configured = settings.state.status === "ready" && settings.state.value.google_maps_configured;

  return (
    <div className="flex flex-1 flex-col gap-6 px-4 pt-3 pb-6 md:px-6 md:py-5">
      <header className="grid gap-1">
        <p className="font-condensed text-xs font-semibold tracking-[0.16em] text-muted-foreground uppercase">Locations, routes and keys</p>
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight md:text-[28px]">Settings</h1>
      </header>

      <section aria-labelledby="google-heading" className="grid gap-3 rounded-xl border border-border bg-card p-4">
        <h2 id="google-heading" className="text-lg font-semibold">Google Maps (optional)</h2>
        {settings.state.status === "loading" && <p role="status" className="text-sm text-muted-foreground">Loading settings…</p>}
        {settings.state.status === "error" && <Failed what="Settings" code={settings.state.code} retry={settings.reload} />}
        {settings.state.status === "ready" && (
          <GoogleKeyForm configured={settings.state.value.google_maps_configured}
            onSave={async (key) => { const saved = await networkApi.setGoogleKey(key); settings.reload(); return saved; }}
            onRemove={async () => { const saved = await networkApi.deleteGoogleKey(); settings.reload(); return saved; }} />
        )}
      </section>

      {!network ? (
        <p className="text-sm text-muted-foreground">Choose a network in the sidebar, or import one, to see its locations and routes.</p>
      ) : (
        // Keyed by network: switching never shows the previous network's rows under the new name.
        <NetworkSections key={network.id} network={network} configured={configured} />
      )}
    </div>
  );
}

/** Locations and routes of one network; remounted per network so its reads start from "loading". */
function NetworkSections({ network, configured }: { network: Network; configured: boolean }) {
  const enrichment = useLoad(() => networkApi.enrichment(network.id), `enrichment:${network.id}`);
  const routes = useLoad(() => networkApi.routes(network.id), `routes:${network.id}`);
  return (
    <>
      <section aria-labelledby="locations-heading" className="grid gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="locations-heading" className="text-lg font-semibold">Locations in {network.name}</h2>
          {network.is_sample && <SampleBadge />}
        </div>
        {enrichment.state.status === "loading" && <p role="status" className="text-sm text-muted-foreground">Loading locations…</p>}
        {enrichment.state.status === "error" && <Failed what="Location details" code={enrichment.state.code} retry={enrichment.reload} />}
        {enrichment.state.status === "ready" && (
          <EnrichmentStatusPanel status={enrichment.state.value}
            onRetry={async () => { const job = await networkApi.retryEnrichment(network.id); enrichment.reload(); return job; }}
            onSaveAttributes={async (locationId, update) => { await networkApi.setAttributes(network.id, locationId, update); enrichment.reload(); }} />
        )}
      </section>

      <section aria-labelledby="routes-heading" className="grid gap-3">
        <h2 id="routes-heading" className="text-lg font-semibold">Routes in {network.name}</h2>
        <GoogleFetch configured={configured}
          onPreview={() => networkApi.googlePreview(network.id)}
          onFetch={async () => { const job = await networkApi.googleFetch(network.id); routes.reload(); return job; }} />
        {routes.state.status === "loading" && <p role="status" className="text-sm text-muted-foreground">Loading routes…</p>}
        {routes.state.status === "error" && <Failed what="Routes" code={routes.state.code} retry={routes.reload} />}
        {routes.state.status === "ready" && <RouteList routes={routes.state.value.routes} />}
      </section>
    </>
  );
}
