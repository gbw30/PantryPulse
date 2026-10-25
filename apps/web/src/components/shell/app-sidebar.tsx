import Link from "next/link";
import { FlaskConical, GitCompareArrows, ListChecks, Map as MapIcon, Settings, Table2, UserRound } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

export type NavKey = "overview" | "data" | "recommendations" | "scenarios";

// Proposed routes from the blueprint (§2). Only built destinations are links; the rest stay visible
// but disabled so the shell geometry is identical on every page without linking to missing screens.
const NAV: { key: NavKey; label: string; href: string; built: boolean; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: "overview", label: "Overview", href: "/overview", built: true, icon: MapIcon },
  { key: "data", label: "Data Explorer", href: "/data", built: false, icon: Table2 },
  { key: "recommendations", label: "Recommendations", href: "/recommendations", built: false, icon: ListChecks },
  { key: "scenarios", label: "Scenario Lab", href: "/scenarios", built: false, icon: FlaskConical },
];

function BrandMark() {
  return (
    <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground" aria-hidden="true">
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 13h4l3-7 5 13 3-6h5" />
      </svg>
    </span>
  );
}

export function AppSidebar({ active }: { active: NavKey }) {
  const hasUnbuilt = NAV.some((item) => !item.built);
  return (
    <Sidebar collapsible="offcanvas" aria-label="Main navigation">
      <SidebarHeader className="px-4 pt-5 pb-3">
        <Link href="/overview" className="flex items-center gap-2.5 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring">
          <BrandMark />
          <span className="text-lg font-semibold tracking-tight">PantryPulse</span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup className="px-3">
          <SidebarGroupContent>
            <nav aria-label="Primary">
              <SidebarMenu className="gap-1">
                {NAV.map((item) => (
                  <SidebarMenuItem key={item.key}>
                    {item.built ? (
                      <SidebarMenuButton asChild isActive={item.key === active} className="h-10 gap-3 px-3 text-[15px]">
                        <Link href={item.href} aria-current={item.key === active ? "page" : undefined}>
                          <item.icon className="size-[18px]" />
                          <span>{item.label}</span>
                        </Link>
                      </SidebarMenuButton>
                    ) : (
                      <SidebarMenuButton disabled className="h-10 gap-3 px-3 text-[15px]">
                        <item.icon className="size-[18px]" />
                        <span>{item.label}<span className="sr-only"> (not built yet)</span></span>
                      </SidebarMenuButton>
                    )}
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </nav>
            {hasUnbuilt && <p className="mt-3 px-3 text-xs text-muted-foreground">Other views are not built yet.</p>}
            {/* Utility link to the connected presenter workspace (origin/main); not one of the four blueprint pages. */}
            <nav aria-label="Workspaces" className="mt-4 border-t border-sidebar-border pt-3">
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton asChild className="h-10 gap-3 px-3 text-[15px]">
                    <Link href="/optimization">
                      <GitCompareArrows className="size-[18px]" />
                      <span>Optimization workspace</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
            </nav>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="gap-3 px-3 pb-5">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton disabled className="h-10 gap-3 px-3 text-[15px]">
              <Settings className="size-[18px]" />
              <span>Settings<span className="sr-only"> (not built yet)</span></span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <div className="flex items-center gap-2.5 rounded-lg border border-dashed border-sidebar-border px-3 py-2.5 text-xs text-muted-foreground">
          <UserRound className="size-4 shrink-0" aria-hidden="true" />
          <span>No account · read-only demo</span>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}

