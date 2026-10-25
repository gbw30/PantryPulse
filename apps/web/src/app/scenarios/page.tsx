import type { Metadata } from "next";
import { ScenarioLab } from "@/components/scenario-lab/scenario-lab";

export const metadata: Metadata = { title: "Scenario Lab · PantryPulse" };

// Reads ?comparison=<id> (deep link from Recommendations) and ?job=<id> (resume a durable job) on the client.
export default function ScenariosPage() {
  return <ScenarioLab />;
}
