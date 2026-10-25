"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/planning-api";

// Shared presenter session (PP-56 foundation). FastAPI owns authentication: the httpOnly pp_presenter
// cookie is invisible here, so the session is detected by probing one cheap presenter-only read.
// Visitors without a pp_csrf cookie are never probed. No name or avatar is ever shown: the login
// response carries only ids.

export type PresenterState = "checking" | "presenter" | "visitor";

type PresenterContext = {
  state: PresenterState;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** Call on any 401 from a presenter API: the session expired or was signed out elsewhere. */
  expired: () => void;
};

const Context = createContext<PresenterContext | null>(null);

const hasCsrfCookie = () => document.cookie.split("; ").some((item) => item.startsWith("pp_csrf="));

/** Plain-language copy for sign-in failures; the API only returns codes. */
export function signInMessage(error: unknown) {
  if (!(error instanceof ApiError)) return "Sign-in failed. Try again.";
  if (error.status === 401) return "Username or password not recognized.";
  if (error.status === 429) return "Too many attempts. Wait a minute and try again.";
  if (error.status === 0) return "Could not reach the server. Check your connection and try again.";
  if (error.status === 503) return "The planning service is unavailable right now.";
  return `Sign-in failed (${error.code}).`;
}

export function PresenterProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<PresenterState>("checking");

  useEffect(() => {
    let active = true;
    if (!hasCsrfCookie()) {
      queueMicrotask(() => { if (active) setState("visitor"); });
      return () => { active = false; };
    }
    api("allocation-methodology")
      .then(() => { if (active) setState("presenter"); })
      .catch(() => { if (active) setState("visitor"); });
    return () => { active = false; };
  }, []);

  // A full reload after sign-in/out makes every page (including ones that fetched as a visitor)
  // re-read with the new session instead of mixing visitor and presenter data.
  const signIn = useCallback(async (username: string, password: string) => {
    await api("presenter/login", { username, password });
    window.location.reload();
  }, []);
  const signOut = useCallback(async () => {
    try { await api("presenter/logout", {}); } finally { window.location.reload(); }
  }, []);
  const expired = useCallback(() => setState("visitor"), []);

  const value = useMemo(() => ({ state, signIn, signOut, expired }), [state, signIn, signOut, expired]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function usePresenter(): PresenterContext {
  const value = useContext(Context);
  if (!value) throw new Error("usePresenter must be used inside AppShell");
  return value;
}
