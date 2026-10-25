import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Sans_Condensed } from "next/font/google";
import "./globals.css";

// next/font downloads and self-hosts these at build time, so the demo makes no runtime font request.
const plex = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex", display: "swap" });
const plexCondensed = IBM_Plex_Sans_Condensed({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-plex-condensed", display: "swap" });

export const metadata: Metadata = {
  title: "PantryPulse",
  description: "Research-inspired resource allocation — development scaffold",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={`${plex.variable} ${plexCondensed.variable}`}><body>{children}</body></html>;
}
