import { liveWithFallbackSource } from "./live-source";
import { OVERVIEW_STATE_PREVIEWS, type OverviewStatePreview } from "./static-fixture";
import type { OverviewDataSource } from "./types";

/**
 * `?state=empty|unavailable|loading` previews the fixture adapter's honest states. Anything else uses
 * live presenter data with the labelled static-fixture fallback.
 */
export function overviewSourceFor(preview: string | undefined): { source: OverviewDataSource; preview: OverviewStatePreview | null } {
  if (preview && Object.hasOwn(OVERVIEW_STATE_PREVIEWS, preview)) {
    const key = preview as OverviewStatePreview;
    return { source: OVERVIEW_STATE_PREVIEWS[key], preview: key };
  }
  return { source: liveWithFallbackSource, preview: null };
}
