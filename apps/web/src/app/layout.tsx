import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Sans_Condensed } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { THEME_BOOT_SCRIPT } from "@/lib/theme";
import "./globals.css";

// Self-hosted at build time by next/font; no runtime font request during the demo.
const plex = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex", display: "swap" });
const plexCondensed = IBM_Plex_Sans_Condensed({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-plex-condensed", display: "swap" });

export const metadata: Metadata = {
  title: "PantryPulse",
  description: "Research-inspired resource allocation — development scaffold",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    // The boot script sets `.dark` before hydration, so <html>'s class can differ from the server render.
    <html lang="en" className={`${plex.variable} ${plexCondensed.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body><TooltipProvider>{children}</TooltipProvider></body>
    </html>
  );
}
