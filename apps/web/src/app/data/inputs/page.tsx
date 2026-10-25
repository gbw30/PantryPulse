import type { Metadata } from "next";
import { InputsView } from "@/components/data-input/inputs-view";

export const metadata: Metadata = { title: "Data input · PantryPulse" };

export default function InputsPage() {
  return <InputsView />;
}
