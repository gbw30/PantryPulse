"use client";

import { MotionConfig } from "motion/react";
import { AppShell, ShellProviders } from "@/components/shell/app-shell";
import { SampleBadge, useNetwork } from "@/components/shell/network-switcher";
import type { Network } from "@/lib/network-api";
import { DangerRankingSection } from "./danger-ranking";
import { OverviewNetworkError, OverviewNoNetwork, OverviewSignedOut } from "./overview-states";

/** The Overview: a chosen network's danger ranking, or what to do first when there is none (W5A-03). */
export function NetworkAtlas() {
  return <ShellProviders><AtlasForNetwork /></ShellProviders>;
}

function AtlasForNetwork() {
  const { state, network } = useNetwork();
  // One shell for every state: swapping shells when the network list settles would remount the
  // navigation and close a drawer or sign-in dialog opened meanwhile.
  return (
    <MotionConfig reducedMotion="user">
      <AppShell active="overview">
        {network ? <NetworkOverview network={network} />
          : state.status === "loading" ? <p role="status" className="px-4 py-5 text-sm text-muted-foreground md:px-6">Loading networks…</p>
          : state.status === "signed_out" ? <OverviewSignedOut />
          : state.status === "error" ? <OverviewNetworkError code={state.code} />
          : <OverviewNoNetwork />}
      </AppShell>
    </MotionConfig>
  );
}

function NetworkOverview({ network }: { network: Network }) {
  return (
    <div className="flex flex-1 flex-col gap-3 px-4 pt-3 pb-4 md:gap-4 md:px-6 md:py-5 lg:gap-6">
      <DangerRankingSection header={
        <header data-atlas-header className="min-w-0">
          <p className="font-condensed text-xs font-semibold tracking-[0.16em] text-muted-foreground uppercase">Network intelligence</p>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-serif text-[26px] leading-tight font-medium tracking-tight md:text-[28px]">Network Atlas</h1>
            {network.is_sample && <SampleBadge />}
          </div>
          <p className="text-sm text-muted-foreground">Which locations in {network.name} are projected to run short, ranked by danger.</p>
        </header>
      } />
    </div>
  );
}
