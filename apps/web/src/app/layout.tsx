import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PantryPulse",
  description: "Research-inspired resource allocation — development scaffold",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

