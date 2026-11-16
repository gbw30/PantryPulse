"use client";

import { useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useSidebar } from "@/components/ui/sidebar";
import { BrandMark, NAV, type NavKey } from "./app-sidebar";
import { PresenterFooter } from "./presenter-footer";
import { TopBar, type TopBarSearch } from "./top-bar";

// The current page is marked by aria-current, weight and a 3 px underline, never by color alone.
export const ITEM = "flex min-h-11 items-center border-b-[3px] border-transparent px-2.5 text-sm font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring aria-[current=page]:border-pp-action aria-[current=page]:font-semibold aria-[current=page]:text-foreground";

function MenuLink({ href, current, children }: { href: string; current: boolean; children: React.ReactNode }) {
  return <Link href={href} aria-current={current ? "page" : undefined} className={ITEM}>{children}</Link>;
}

type Props = { active?: NavKey; search?: TopBarSearch; horizonLabel?: string; legacyOnly?: boolean };

/**
 * The shared header (W5A-02). At 768 px and up it has two rows: the menu (brand, Primary, Reference, Settings,
 * presenter control) over the context bar (TopBar). Below 768 px only the context bar shows, and the menu is
 * the "Open navigation" drawer (AppSidebar).
 */
export function AppTopNav({ active, search, horizonLabel, legacyOnly }: Props) {
  const { isMobile } = useSidebar();
  return (
    <header className="z-20 shrink-0 bg-card max-md:sticky max-md:top-0">
      {/* isMobile is false until hydration, so the row is also hidden by CSS below 768 px. */}
      {!isMobile && (
        <div className="flex flex-wrap items-center gap-x-1 border-b-[3px] border-double border-pp-rule px-7 pt-2.5 max-md:hidden">
          <Link href="/overview" className="mr-3 mb-2 flex items-center gap-2.5 rounded-md font-serif text-[21px] font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <BrandMark />
            <span>PantryPulse</span>
          </Link>
          <nav aria-label="Primary" className="flex flex-wrap items-center gap-x-1">
            {NAV.map((item) => item.built
              ? <MenuLink key={item.key} href={item.href} current={item.key === active}>{item.label}</MenuLink>
              : <span key={item.key} aria-disabled="true" className={ITEM}>{item.label}<span className="sr-only"> (not built yet)</span></span>)}
          </nav>
          <nav aria-label="Reference" className="flex">
            <MenuLink href="/methodology" current={active === "methodology"}>Methodology &amp; audit</MenuLink>
          </nav>
          <MenuLink href="/settings" current={active === "settings"}>Settings</MenuLink>
          <PresenterFooter inline />
        </div>
      )}
      <TopBar search={search} horizonLabel={horizonLabel} active={active} legacyOnly={legacyOnly} />
    </header>
  );
}

const subscribeNever = () => () => {};
const findSlot = () => document.querySelector("header [data-slot='page-actions']");

/**
 * Renders a page's own controls in the header's context bar.
 * shortcut: the slot is looked up by selector when this renders, so use it inside AppShell (the header mounts
 * with it); move the slot to a context ref if a header can ever mount after its page.
 */
export function PageActions({ children }: { children: React.ReactNode }) {
  const slot = useSyncExternalStore(subscribeNever, findSlot, () => null);
  return slot ? createPortal(children, slot) : null;
}
