"use client";

import { useRef, useState } from "react";
import { LogIn, LogOut, ShieldCheck, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { signInMessage, usePresenter } from "./presenter-session";

/** Sidebar footer identity: the only place the session appears (blueprint §2, no duplicate identity). */
export function PresenterFooter() {
  const { state, signIn, signOut } = usePresenter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);

  async function submit(form: FormData) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true); setError("");
    try {
      await signIn(String(form.get("username") ?? ""), String(form.get("password") ?? ""));
    } catch (e) {
      setError(signInMessage(e));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  if (state === "presenter") {
    return (
      <div className="flex flex-col gap-2 rounded-lg border border-sidebar-border px-3 py-2.5 text-xs">
        <span className="flex items-center gap-2.5 text-foreground">
          <ShieldCheck className="size-4 shrink-0 text-pp-teal" aria-hidden="true" />
          <span>Presenter session · simulated demo</span>
        </span>
        <Button variant="outline" size="sm" className="justify-start gap-2" disabled={busy}
          onClick={() => { setBusy(true); void signOut().finally(() => setBusy(false)); }}>
          <LogOut className="size-4" aria-hidden="true" />Sign out
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-dashed border-sidebar-border px-3 py-2.5 text-xs text-muted-foreground">
      <span className="flex items-center gap-2.5">
        <UserRound className="size-4 shrink-0" aria-hidden="true" />
        <span>No account · read-only demo</span>
      </span>
      <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setError(""); }}>
        <DialogTrigger asChild>
          <Button variant="outline" size="sm" className="justify-start gap-2" disabled={state === "checking"}>
            <LogIn className="size-4" aria-hidden="true" />Presenter sign in
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Presenter sign in</DialogTitle>
            <DialogDescription>Use the presenter credentials configured for your isolated demo. Visitors stay read-only.</DialogDescription>
          </DialogHeader>
          <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void submit(new FormData(e.currentTarget)); }}>
            <div className="grid gap-1.5">
              <Label htmlFor="presenter-username">Username</Label>
              <Input id="presenter-username" name="username" autoComplete="username" required maxLength={128} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="presenter-password">Password</Label>
              <Input id="presenter-password" name="password" type="password" autoComplete="current-password" required maxLength={256} />
            </div>
            {error && <p role="alert" className="text-sm text-foreground">{error}</p>}
            <DialogFooter>
              <Button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
