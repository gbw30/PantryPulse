import type { Metadata } from "next";
import { DecisionsView } from "@/components/decisions/decisions-view";

export const metadata: Metadata = { title: "Decisions · PantryPulse" };

// `?comparison_id=&method=` name one compared method result of the chosen network (linked from Scenario Lab).
export default async function DecisionsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { comparison_id: comparison, method } = await searchParams;
  return <DecisionsView comparisonId={typeof comparison === "string" ? comparison : undefined} method={typeof method === "string" ? method : undefined} />;
}
