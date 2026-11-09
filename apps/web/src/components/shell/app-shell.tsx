import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar, type NavKey } from "./app-sidebar";
import { NetworkProvider, useNetworkOptional } from "./network-switcher";
import { PresenterProvider, usePresenterOptional } from "./presenter-session";
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
 * The session and network providers, mounted once: a page that must read the chosen network above its
 * AppShell (the overview picks its layout from it) mounts them itself, and the AppShell inside reuses them.
 */
export function ShellProviders({ children }: { children: React.ReactNode }) {
  const presenter = usePresenterOptional();
  const network = useNetworkOptional();
  return presenter && network ? children : <PresenterProvider><NetworkProvider>{children}</NetworkProvider></PresenterProvider>;
}

/**
 * Shared navigation shell (blueprint §2): skip link, sidebar, top bar, main content.
 * Rendered by each page's client root; identical geometry on every main page. Pages read the shared
 * presenter session with usePresenter().
 */
export function AppShell({ active, horizonLabel, search, contentElement = "main", children }: Props) {
  const Content = contentElement;
  return (
    <ShellProviders>
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
    </ShellProviders>
  );
}
