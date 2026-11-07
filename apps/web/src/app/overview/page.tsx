import type { Metadata } from "next";
import { NetworkAtlas } from "@/components/overview/network-atlas";

export const metadata: Metadata = { title: "Network Atlas · PantryPulse" };

// `?state=empty|unavailable|loading` previews the honest empty, failure and loading states of the
// static fixture adapter. Any other value shows the static fixture. `?forecast_run_id=` names the v1
// forecast run whose danger ranking is shown (until a network's runs can be listed, CR-w1-web-2).
export default async function OverviewPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { state, forecast_run_id: run } = await searchParams;
  return <NetworkAtlas statePreview={typeof state === "string" ? state : undefined} forecastRunId={typeof run === "string" ? run : undefined} />;
}
