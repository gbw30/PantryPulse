import { IBM_Plex_Sans, IBM_Plex_Sans_Condensed } from "next/font/google";

// Self-host the prototype fonts without changing production page typography.
const plex = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex", display: "swap" });
const plexCondensed = IBM_Plex_Sans_Condensed({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-plex-condensed", display: "swap" });

export default function DesignLabLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <div className={`${plex.variable} ${plexCondensed.variable}`}>{children}</div>;
}
