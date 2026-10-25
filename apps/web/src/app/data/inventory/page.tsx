import type { Metadata } from "next";
import { InventoryView } from "@/components/data-input/inventory-view";

export const metadata: Metadata = { title: "Inventory & Lots · PantryPulse" };

export default function InventoryPage() {
  return <InventoryView />;
}
