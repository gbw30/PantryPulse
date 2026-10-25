"use client";

import { AppShell } from "./app-shell";
import type { NavKey } from "./app-sidebar";

/**
 * Client entry for server pages that render the shared shell around content owning its own <main>
 * (the optimization workspace). Props stay serializable: no search handlers.
 */
export function ClientAppShell({ active, horizonLabel, children }: { active: NavKey; horizonLabel?: string; children: React.ReactNode }) {
  return <AppShell active={active} horizonLabel={horizonLabel} contentElement="div">{children}</AppShell>;
}
