import type { Metadata } from "next";
import { SettingsView } from "@/components/enrichment/settings-view";

export const metadata: Metadata = { title: "Settings · PantryPulse" };

export default function SettingsPage() {
  return <SettingsView />;
}
