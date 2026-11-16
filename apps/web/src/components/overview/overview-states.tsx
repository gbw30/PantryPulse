"use client";

import Link from "next/link";
import { NetworkSwitcher } from "@/components/shell/network-switcher";
import { PresenterSignIn } from "@/components/shell/presenter-footer";
import { Button } from "@/components/ui/button";

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

export function OverviewNoNetwork() {
  return (
    <OverviewState title="Choose or import a network" help="Pick a network to see which locations are projected to run short, or import your own from the CSV templates.">
      <div className="w-full max-w-xs"><NetworkSwitcher /></div>
      <Button asChild size="lg"><Link href="/import">Import data</Link></Button>
    </OverviewState>
  );
}
