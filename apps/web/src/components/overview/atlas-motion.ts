import { useSyncExternalStore } from "react";
import "./supply-flow.css";

/** The design lab's spring (PP-52 decision 3), shared by markers, drag settle, panels and press feedback. */
export const SPRING = { type: "spring", stiffness: 250, damping: 22 } as const;

/** Press feedback for chips and buttons (a transform, so MotionConfig reducedMotion="user" skips it). */
export const PRESS = { whileTap: { scale: 0.96 }, transition: SPRING } as const;

// Pause for the always-on supply-link flow (WCAG 2.2.2; PP-52 #4 kept by Gabriel 2026-11-12). A viewing
// convenience remembered per browser; storage that is unavailable or blocked means the flow plays.
const FLOW_PAUSE_KEY = "pp-atlas-flow-paused";
let flowPaused: boolean | null = null;
const flowListeners = new Set<() => void>();

function readFlowPaused() {
  if (flowPaused === null) {
    try {
      flowPaused = window.localStorage.getItem(FLOW_PAUSE_KEY) === "1";
    } catch {
      flowPaused = false;
    }
  }
  return flowPaused;
}

export function setFlowPaused(next: boolean) {
  flowPaused = next;
  try {
    if (next) window.localStorage.setItem(FLOW_PAUSE_KEY, "1");
    else window.localStorage.removeItem(FLOW_PAUSE_KEY);
  } catch {
    // Not remembered; the pause still applies to this page view.
  }
  for (const listener of flowListeners) listener();
}

/** Whether the supply-link flow is paused; the server render (and first paint) assumes it plays. */
export const useFlowPaused = () => useSyncExternalStore(
  (listener) => { flowListeners.add(listener); return () => { flowListeners.delete(listener); }; },
  readFlowPaused,
  () => false,
);
