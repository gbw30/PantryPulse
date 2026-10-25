import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar, type NavKey } from "./app-sidebar";
import { TopBar, type TopBarSearch } from "./top-bar";

type Props = {
  active: NavKey;
  horizonLabel?: string;
  search?: TopBarSearch;
  /** "div" when the page content provides its own <main> landmark. */
  contentElement?: "main" | "div";
  children: React.ReactNode;
};

/**
 * Shared navigation shell (blueprint §2): skip link, sidebar, top bar, main content.
 * Rendered by each page's client root; identical geometry on every main page.
 */
export function AppShell({ active, horizonLabel, search, contentElement = "main", children }: Props) {
  const Content = contentElement;
  return (
    <SidebarProvider style={{ "--sidebar-width": "clamp(15rem, 18.9vw, 17rem)" } as React.CSSProperties}>
      <a
        href="#main-content"
        className="sr-only z-50 rounded-md bg-card px-3 py-2 text-sm font-medium text-foreground focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:ring-2 focus:ring-ring"
      >
        Skip to main content
      </a>
      <AppSidebar active={active} />
      <div className="flex min-h-svh min-w-0 flex-1 flex-col bg-background">
        <TopBar search={search} horizonLabel={horizonLabel} />
        <Content id="main-content" tabIndex={-1} className="flex min-w-0 flex-1 flex-col outline-none">
          {children}
        </Content>
      </div>
    </SidebarProvider>
  );
}
