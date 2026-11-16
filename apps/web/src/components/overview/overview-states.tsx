"use client";

import Link from "next/link";
import { NetworkSwitcher, useNetwork } from "@/components/shell/network-switcher";
import { PresenterSignIn } from "@/components/shell/presenter-footer";
import { Button } from "@/components/ui/button";
import { useSidebar } from "@/components/ui/sidebar";

// The Overview before there is a network to show (W5A-03). Listing networks needs a presenter session,
// so a visitor is asked to sign in; no fixture network stands in for theirs.
function OverviewState({ title, help, children }: { title: string; help: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col px-4 pt-3 pb-4 md:px-6 md:py-5">
      <section className="flex max-w-xl flex-col items-start gap-4 border-t border-pp-rule pt-4">
        <h1 className="font-serif text-[26px] leading-tight font-medium tracking-tight md:text-[28px]">{title}</h1>
        <p className="text-sm text-muted-foreground">{help}</p>
        {children}
      </section>
    </div>
  );
}

export function OverviewSignedOut() {
  return (
    <OverviewState title="Sign in to see your networks" help="Networks, forecasts and plans are open to the presenter session only.">
      <PresenterSignIn trigger={<Button size="lg">Presenter sign in</Button>} />
    </OverviewState>
  );
}

// One picker per page (W5A-03c): at 768 px and up it is the context bar's, so the page points there instead.
export function OverviewNoNetwork() {
  const { isMobile } = useSidebar();
  return (
    <OverviewState title="Choose or import a network" help={`Pick a network ${isMobile ? "below" : "in the bar above"} to see which locations are projected to run short, or import your own from the CSV templates.`}>
      {isMobile && <div className="w-full max-w-xs md:hidden"><NetworkSwitcher /></div>}
      <Button asChild size="lg"><Link href="/import">Import data</Link></Button>
    </OverviewState>
  );
}

export function OverviewNetworkError({ code }: { code: string }) {
  const { reload } = useNetwork();
  return (
    <OverviewState title="Networks could not be loaded" help="The Overview needs the list of networks before it can rank any locations.">
      <p role="alert" className="text-sm text-foreground">Network list unavailable ({code.replaceAll("_", " ").toLowerCase()}).</p>
      <Button size="lg" onClick={reload}>Try again</Button>
    </OverviewState>
  );
}
