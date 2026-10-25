import type { Metadata } from "next";
import { DataExplorerScreen } from "@/components/data-explorer/data-explorer";

export const metadata: Metadata = { title: "Data Explorer · PantryPulse" };

export default async function DataExplorerPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { product } = await searchParams;
  return <DataExplorerScreen view="dashboard" initialProductId={typeof product === "string" ? product : null} />;
}
