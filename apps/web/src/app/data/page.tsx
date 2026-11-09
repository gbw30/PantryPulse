import type { Metadata } from "next";
import { DataExplorerScreen } from "@/components/data-explorer/data-explorer";

export const metadata: Metadata = { title: "Data Explorer · PantryPulse" };

export default async function DataExplorerPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  // `?forecast_run_id=` names the v1 forecast run whose accuracy is shown (until runs can be listed, CR-w1-web-2).
  const { product, forecast_run_id: run } = await searchParams;
  return <DataExplorerScreen view="dashboard" initialProductId={typeof product === "string" ? product : null} forecastRunId={typeof run === "string" ? run : undefined} />;
}
