import type { Metadata } from "next";
import { NetworkAtlas } from "@/components/overview/network-atlas";

export const metadata: Metadata = { title: "Network Atlas · PantryPulse" };

// `?state=empty|unavailable|loading` previews the honest empty, failure and loading states of the
// static fixture adapter. Any other value shows the static fixture.
export default async function OverviewPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { state } = await searchParams;
  return <NetworkAtlas statePreview={typeof state === "string" ? state : undefined} />;
}
