import { cn } from "@/lib/utils";
import type { MarkerStatus } from "./types";

// Shape carries the status alongside colour: diamond, triangle, circle, dashed ring, square.
export function StatusGlyph({ status, size = 14, className }: { status: MarkerStatus; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" className={cn("shrink-0", className)}>
      {status === "shortfall" && <path d="M8 1 L15 8 L8 15 L1 8 Z" fill="var(--pp-danger)" stroke="var(--pp-surface)" strokeWidth="1" />}
      {status === "watch" && <path d="M8 1.5 L15 14.5 H1 Z" fill="var(--pp-warning)" stroke="var(--pp-surface)" strokeWidth="1" strokeLinejoin="round" />}
      {status === "covered" && <circle cx="8" cy="8" r="6.5" fill="var(--pp-teal)" stroke="var(--pp-surface)" strokeWidth="1" />}
      {status === "not_evaluated" && <circle cx="8" cy="8" r="6" fill="var(--pp-surface)" stroke="var(--pp-neutral)" strokeWidth="2" strokeDasharray="2.6 2" />}
      {status === "hub" && <rect x="2" y="2" width="12" height="12" rx="1.5" fill="var(--pp-ink)" stroke="var(--pp-surface)" strokeWidth="1" />}
    </svg>
  );
}
