import { ClientAppShell } from "@/components/shell/client-app-shell";
import Workspace from "./workspace";

export const metadata = { title: "Optimization workspace · PantryPulse" };

// The workspace renders its own <main>, so the shell's content area is a plain container here.
export default function OptimizationPage() {
  return <ClientAppShell active="optimization"><Workspace /></ClientAppShell>;
}
