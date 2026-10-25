import { redirect } from "next/navigation";

// The Scenario Lab (/scenarios) replaced the Optimization workspace (PP-55 decision 1). The old URL
// keeps working for bookmarks; durable-job and comparison parameters carry over.
export function GET(request: Request) {
  const incoming = new URL(request.url);
  redirect(`/scenarios${incoming.search}`);
}
