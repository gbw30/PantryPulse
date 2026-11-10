import type { Metadata } from "next";
import { PrintPlan } from "@/components/decisions/print-plan";

export const metadata: Metadata = { title: "Plan export · PantryPulse" };

// Print-friendly copy of the actions chosen on /decisions: `?network_id=&comparison_id=&method=`. The chosen
// action ids come from browser storage (see readSelection), never the URL, which hundreds of ids would overflow.
export default async function DecisionsPrintPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { network_id: network, comparison_id: comparison, method } = await searchParams;
  const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : undefined);
  return <PrintPlan networkId={one(network)} comparisonId={one(comparison)} method={one(method)} />;
}
