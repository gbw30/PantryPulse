import Link from "next/link";
import { cn } from "@/lib/utils";
import { noticeHeadline } from "./notice-copy";
import { formatInstant } from "./status";
import { StatusGlyph } from "./status-glyph";
import type { LiveNotice } from "./types";

export const NOTICE_LINK = "font-medium text-foreground underline underline-offset-2 outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** Secondary line: when the forecast was recorded and the API code, never as the headline. */
export function NoticeMeta({ recorded, code }: { recorded?: string | null; code?: string }) {
  if (!recorded && !code) return null;
  return (
    <p className="text-xs text-muted-foreground">
      {recorded && <span>Forecast recorded {recorded}</span>}
      {recorded && code && <span aria-hidden="true"> · </span>}
      {code && <span>Error code <code data-notice-code className="font-mono text-[11px] break-all">{code}</code></span>}
    </p>
  );
}

/**
 * Why live statuses are absent although presenter data loaded; always with a path to fix it. A status
 * region (it appears after load); the integrity failure is an alert. No claim about the network is
 * made for an integrity failure.
 */
export function LiveNoticeBanner({ notice, timeZone }: { notice: LiveNotice; timeZone: string }) {
  const body = notice.kind === "stale" ? "Statuses are Not evaluated; inventory is live." : notice.kind === "not_ready" ? "Inventory is live; statuses are Not evaluated." : notice.kind === "demand_unavailable" ? "Inventory is live." : null;
  const link = notice.kind === "not_ready" ? "Run a forecast in the optimization workspace" : "Run a new forecast in the optimization workspace";
  return (
    <div
      data-live-notice={notice.kind}
      role={notice.kind === "integrity" ? "alert" : "status"}
      className={cn("flex items-start gap-2 rounded-lg border bg-card px-3 py-2 text-sm text-foreground", notice.kind === "integrity" ? "border-pp-danger" : "border-pp-warning")}
    >
      <StatusGlyph status="not_evaluated" className="mt-0.5" />
      <div className="grid min-w-0 gap-0.5">
        <p>
          <strong className="font-semibold">{noticeHeadline(notice)}</strong>
          {body && ` ${body}`}{" "}
          <Link className={NOTICE_LINK} href="/optimization">{link}</Link>
        </p>
        <NoticeMeta recorded={notice.recordedAt ? formatInstant(notice.recordedAt, timeZone) : null} code={notice.code} />
      </div>
    </div>
  );
}
