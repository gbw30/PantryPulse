"use client";

import { useRef, useState } from "react";
import { LogIn, LogOut, ShieldCheck, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { signInMessage, usePresenter } from "./presenter-session";

// Inline (menu row): a label gives way to the links where the row would wrap; the button keeps its name. The presenter's
// fits from 1280 px (W5A-03c); the visitor's longer label beside the wider sign-in button needs 1400.
const INLINE = "ml-auto flex items-center gap-2 pb-2 text-xs";
const PRESENTER_LABEL = "max-[1279px]:sr-only";
const VISITOR_LABEL = "max-[1399px]:sr-only";

/**
 * The "Presenter sign in" button and its dialog. `trigger` replaces the menu's button where a page offers the
 * same sign-in itself (the Overview's signed-out state, W5A-03).
 */
export function PresenterSignIn({ trigger }: { trigger?: React.ReactElement }) {
  const { state, signIn } = usePresenter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const password = useRef<HTMLInputElement>(null);

  async function submit(form: FormData) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true); setError("");
    try {
      await signIn(String(form.get("username") ?? ""), String(form.get("password") ?? ""));
    } catch (e) {
      setError(signInMessage(e));
      // No password stays on the page after a failed sign-in, where a snapshot or screenshot could capture it.
      if (password.current) { password.current.value = ""; password.current.focus(); }
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setError(""); }}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline" size="sm" className="justify-start gap-2" disabled={state === "checking"}>
            <LogIn className="size-4" aria-hidden="true" />Presenter sign in
          </Button>
        )}
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
            <Input ref={password} id="presenter-password" name="password" type="password" autoComplete="current-password" required maxLength={256} />
          </div>
          {error && <p role="alert" className="text-sm text-foreground">{error}</p>}
          <DialogFooter>
            <Button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/**
 * The presenter control and the only place the session appears (blueprint §2, no duplicate identity): `inline`
 * in the header's menu row at 768 px and up, boxed in the navigation drawer below that.
 */
export function PresenterFooter({ inline = false }: { inline?: boolean }) {
  const { state, signOut } = usePresenter();
  const [busy, setBusy] = useState(false);

  if (state === "presenter") {
    return (
      <div className={inline ? INLINE : "flex flex-col gap-2 rounded-lg border border-sidebar-border px-3 py-2.5 text-xs"}>
        <span className="flex items-center gap-2.5 text-foreground">
          <ShieldCheck className="size-4 shrink-0 text-pp-action" aria-hidden="true" />
          <span className={inline ? PRESENTER_LABEL : undefined}>Presenter session</span>
        </span>
        <Button variant="outline" size="sm" className="justify-start gap-2" disabled={busy}
          onClick={() => { setBusy(true); void signOut().finally(() => setBusy(false)); }}>
          {/* Inline, the text alone names it: the icon's width lets "Presenter session" show from 1280 px. */}
          {!inline && <LogOut className="size-4" aria-hidden="true" />}Sign out
        </Button>
      </div>
    );
  }

  return (
    <div className={inline ? `${INLINE} text-muted-foreground` : "flex flex-col gap-2 rounded-lg border border-dashed border-sidebar-border px-3 py-2.5 text-xs text-muted-foreground"}>
      <span className="flex items-center gap-2.5">
        <UserRound className="size-4 shrink-0" aria-hidden="true" />
        <span className={inline ? VISITOR_LABEL : undefined}>No account · read-only demo</span>
      </span>
      <PresenterSignIn />
    </div>
  );
}
