"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { modeSummary } from "@/lib/mode-vocabulary";
import { networkApi, type Network } from "@/lib/network-api";
import { ApiError } from "@/lib/planning-api";

type NetworkState =
  | { status: "loading" }
  | { status: "signed_out" }
  | { status: "error"; code: string }
  | { status: "ready"; networks: Network[] };

type NetworkContextValue = {
  state: NetworkState;
  /** The chosen network, or null while loading, signed out, failed or when none exist yet. */
  network: Network | null;
  select: (networkId: string) => void;
  /** Re-read the list, e.g. after an import created a network. */
  reload: () => void;
};

// Per-browser convenience only: which network this viewer last looked at.
const STORAGE_KEY = "pantrypulse.network";
const readStored = () => { try { return window.localStorage.getItem(STORAGE_KEY); } catch { return null; } };
const writeStored = (id: string) => { try { window.localStorage.setItem(STORAGE_KEY, id); } catch { /* storage blocked */ } };

const NetworkContext = createContext<NetworkContextValue | null>(null);

export function NetworkProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<NetworkState>({ status: "loading" });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [generation, setGeneration] = useState(0);

  useEffect(() => {
    let active = true;
    networkApi.list().then(
      ({ networks }) => {
        if (!active) return;
        setState({ status: "ready", networks });
        setSelectedId((current) => {
          const wanted = current ?? readStored();
          return networks.some((n) => n.id === wanted) ? wanted : networks[0]?.id ?? null;
        });
      },
      (error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) setState({ status: "signed_out" });
        else setState({ status: "error", code: error instanceof ApiError ? error.code : "REQUEST_FAILED" });
      },
    );
    return () => { active = false; };
  }, [generation]);

  const select = useCallback((networkId: string) => { setSelectedId(networkId); writeStored(networkId); }, []);
  const reload = useCallback(() => setGeneration((n) => n + 1), []);
  const value = useMemo<NetworkContextValue>(() => ({
    state,
    network: state.status === "ready" ? state.networks.find((n) => n.id === selectedId) ?? null : null,
    select,
    reload,
  }), [state, selectedId, select, reload]);
  return <NetworkContext.Provider value={value}>{children}</NetworkContext.Provider>;
}

export function useNetwork() {
  const value = useContext(NetworkContext);
  if (!value) throw new Error("useNetwork must be used inside NetworkProvider");
  return value;
}

export const SAMPLE_LABEL = "Sample data — fictional";

export function SampleBadge() {
  return (
    <span className="inline-flex w-fit items-center rounded-full border border-dashed border-border bg-muted px-2 py-0.5 text-xs font-medium text-foreground">
      {SAMPLE_LABEL}
    </span>
  );
}

/** Sidebar control: choose the network every v1 screen reads, with its mode vocabulary and sample badge. */
export function NetworkSwitcher() {
  const { state, network, select } = useNetwork();
  return (
    <section aria-label="Current network" className="grid gap-1.5 px-1 text-sm">
      <Label htmlFor="network-switcher" className="text-xs text-muted-foreground">Network</Label>
      {state.status === "loading" && <p className="text-muted-foreground">Loading networks…</p>}
      {state.status === "signed_out" && <p className="text-muted-foreground">Sign in to see your networks.</p>}
      {state.status === "error" && <p role="alert" className="text-muted-foreground">Networks unavailable ({state.code.replaceAll("_", " ").toLowerCase()}).</p>}
      {state.status === "ready" && state.networks.length === 0 && (
        <p className="text-muted-foreground">No network yet. <Link href="/import" className="font-medium text-foreground underline underline-offset-2">Import your data</Link></p>
      )}
      {state.status === "ready" && state.networks.length > 0 && (
        <>
          <Select value={network?.id} onValueChange={select}>
            <SelectTrigger id="network-switcher" className="h-10 w-full bg-background">
              <SelectValue placeholder="Choose a network" />
            </SelectTrigger>
            <SelectContent>
              {state.networks.map((n) => (
                <SelectItem key={n.id} value={n.id}>{n.name}{n.is_sample ? " (sample)" : ""}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {network && <p className="text-xs text-muted-foreground">{modeSummary(network.mode)}</p>}
          {network?.is_sample && <SampleBadge />}
        </>
      )}
    </section>
  );
}
