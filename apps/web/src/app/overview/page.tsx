import type { Metadata } from "next";
import { NetworkAtlas } from "@/components/overview/network-atlas";

export const metadata: Metadata = { title: "Network Atlas · PantryPulse" };

// A chosen network's danger ranking uses its newest forecast run (W4-02); without a network the page
// asks for a sign-in, or for a network to choose or import (W5A-03).
export default function OverviewPage() {
  return <NetworkAtlas />;
}
