"use client";

import Link from "next/link";
import { formatInstant, noticeHeadline } from "./format";
import { StatusGlyph } from "./marks";
import type { ExplorerNotice } from "./types";

const LINK = "font-medium text-foreground underline underline-offset-2 outline-none focus-visible:ring-2 focus-visible:ring-ring";

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

/** Why projections are absent although live inventory loaded; always with a path to fix it. */
export function ExplorerNoticeBanner({ notice, timezone }: { notice: ExplorerNotice; timezone: string }) {
  const alert = notice.kind === "integrity" || notice.kind === "projection_unavailable";
  const body = notice.kind === "projection_visitor"
    ? "Inventory is shown; projections need a presenter sign-in."
    : "Inventory is live; projections are Not evaluated.";
  const link = notice.kind === "not_ready" ? "Run a forecast in the optimization workspace" : notice.kind === "projection_visitor" ? "Sign in through the sidebar" : "Run a new forecast in the optimization workspace";
  return (
    <div
      data-explorer-notice={notice.kind}
      role={alert ? "alert" : "status"}
      className={`flex items-start gap-2 rounded-lg border bg-card px-3 py-2 text-sm text-foreground ${alert ? "border-pp-danger" : "border-pp-warning"}`}
    >
      <StatusGlyph status="not_evaluated" className="mt-0.5" />
      <div className="grid min-w-0 gap-0.5">
        <p>
          <strong className="font-semibold">{noticeHeadline(notice)}</strong>
          {` ${body}`}{" "}
          {notice.kind !== "projection_visitor" && <Link className={LINK} href="/optimization">{link}</Link>}
        </p>
        <NoticeMeta recorded={notice.recordedAt ? formatInstant(notice.recordedAt, timezone) : null} code={notice.code} />
      </div>
    </div>
  );
}
