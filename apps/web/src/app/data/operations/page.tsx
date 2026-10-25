import type { Metadata } from "next";
import { DataExplorerScreen } from "@/components/data-explorer/data-explorer";

export const metadata: Metadata = { title: "Operations Board · PantryPulse" };

export default async function OperationsBoardPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { product } = await searchParams;
  return <DataExplorerScreen view="operations" initialProductId={typeof product === "string" ? product : null} />;
}
