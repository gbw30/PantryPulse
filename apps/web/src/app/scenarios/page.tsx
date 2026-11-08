import type { Metadata } from "next";
import { ScenarioLab } from "@/components/scenario-lab/scenario-lab";

export const metadata: Metadata = { title: "Scenario Lab · PantryPulse" };

// Reads ?comparison=<id> (deep link from Recommendations) and ?job=<id> (resume a durable job) on the
// client. `?forecast_run_id=` names the v1 forecast run the method comparison freezes (CR-w1-web-2).
export default async function ScenariosPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { forecast_run_id: run } = await searchParams;
  return <ScenarioLab forecastRunId={typeof run === "string" ? run : undefined} />;
}
