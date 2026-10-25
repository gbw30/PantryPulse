import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Sans_Condensed } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
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
    <html lang="en" className={`${plex.variable} ${plexCondensed.variable}`}>
      <body><TooltipProvider>{children}</TooltipProvider></body>
    </html>
  );
}
