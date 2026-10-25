import type { Metadata } from "next";
import { MethodologyView } from "@/components/methodology/methodology-view";

export const metadata: Metadata = { title: "Methodology · PantryPulse" };

export default function MethodologyPage() {
  return <MethodologyView />;
}
