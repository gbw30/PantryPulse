"use client";

import Link from "next/link";
import { usePresenter } from "@/components/shell/presenter-session";
import { cn } from "@/lib/utils";
import { EXPLORER_TABS, tabHref, type ExplorerTab, type ExplorerTabKey } from "./tabs";

const TAB = "inline-flex h-10 shrink-0 items-center rounded-lg border px-3.5 text-sm font-medium whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring max-md:h-11";

/** A link to a subview from the shared config; unbuilt subviews are visible but disabled. */
export function ExplorerTabLink({ tab, active, productId, className }: { tab: ExplorerTab; active?: boolean; productId?: string | null; className?: string }) {
  if (!tab.built) {
    return (
      <span aria-disabled="true" className={cn(TAB, "cursor-not-allowed border-dashed border-border bg-transparent text-muted-foreground", className)}>
        {tab.label}<span className="sr-only"> (not built yet)</span>
      </span>
    );
  }
  return (
    <Link
      href={tabHref(tab, productId)}
      aria-current={active ? "page" : undefined}
      className={cn(TAB, active ? "border-pp-teal/40 bg-pp-teal-soft text-foreground shadow-[inset_0_-2px_0_var(--pp-teal)]" : "border-border bg-card text-foreground hover:border-foreground/30", className)}
    >
      {tab.label}
    </Link>
  );
}

/**
 * DataExplorerHeader: eyebrow, title, description, a right-hand controls slot and the subview tab strip.
 * Exported for PP-56 (Inventory & Lots, Data input). Render inside AppShell (it reads the presenter session).
 */
export function DataExplorerHeader({ active, controls, meta, productId }: { active: ExplorerTabKey; controls?: React.ReactNode; meta?: React.ReactNode; productId?: string | null }) {
  const { state } = usePresenter();
  const tabs = EXPLORER_TABS.filter((tab) => !tab.presenterOnly || state === "presenter");
  return (
    <header data-explorer-header className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="font-condensed text-xs font-semibold tracking-[0.16em] text-muted-foreground uppercase">Forecasts &amp; inventory</p>
          <h1 className="text-[26px] leading-tight font-semibold tracking-tight md:text-[28px]">Data Explorer</h1>
          <p className="text-sm text-muted-foreground">Projected demand, service and stock by site and product across the simulated network.</p>
          {meta}
        </div>
        {controls && <div className="grid gap-2 sm:flex sm:flex-wrap sm:items-end lg:justify-end">{controls}</div>}
      </div>
      <nav aria-label="Data Explorer views" className="-mx-4 overflow-x-auto px-4 pb-1 md:mx-0 md:px-0">
        <ul className="flex w-max gap-2">
          {tabs.map((tab) => (
            <li key={tab.key}><ExplorerTabLink tab={tab} active={tab.key === active} productId={productId} /></li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
