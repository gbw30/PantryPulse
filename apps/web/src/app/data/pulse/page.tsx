import type { Metadata } from "next";
import { DataExplorerScreen } from "@/components/data-explorer/data-explorer";

export const metadata: Metadata = { title: "Seven-Day Pulse · PantryPulse" };

export default async function SevenDayPulsePage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { product } = await searchParams;
  return <DataExplorerScreen view="pulse" initialProductId={typeof product === "string" ? product : null} />;
}
