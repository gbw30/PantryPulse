import { Suspense } from "react";
import type { Metadata } from "next";
import { RecommendationsScreen } from "@/components/recommendations/recommendations-screen";

export const metadata: Metadata = { title: "Recommendations · PantryPulse" };

// The screen reads ?comparison= and ?tab= with useSearchParams, so prerendering needs a boundary.
export default function RecommendationsPage() {
  return (
    <Suspense>
      <RecommendationsScreen />
    </Suspense>
  );
}
