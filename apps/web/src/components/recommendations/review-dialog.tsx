"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, planningApi, type Schema } from "@/lib/planning-api";
import { METHOD_LABEL, shortId } from "./model";

export type ReviewOutcome = "reviewed" | "stale" | "expired";

/**
 * The screen's only primary action (presenter + verified saved plan). Records a simulation-only review
 * marker: no stock, purchase or dispatch effect. One Idempotency-Key per review intent, reused when the
 * same POST is retried after a network error; repeated clicks while it is in flight are ignored.
 */
export function ReviewDialog({ plan, scenarioId, onOutcome }: { plan: Schema["PlanResult"]; scenarioId: string; onOutcome: (outcome: ReviewOutcome) => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const pending = useRef(false);
  const intentKey = useRef<string | null>(null);

  function change(next: boolean) {
    if (busy) return;
    setOpen(next);
    setError("");
    if (next) { intentKey.current = crypto.randomUUID(); setNote(""); }
  }

  async function submit() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    const body: Schema["ReviewRequest"] = { action: "REVIEWED", expected_result_hash: plan.result_hash, ...(note.trim() ? { note: note.trim() } : {}) };
    try {
      await planningApi.reviewPlan(plan.id, body, intentKey.current ?? undefined);
      intentKey.current = null;
      setOpen(false);
      onOutcome("reviewed");
    } catch (e) {
      const status = e instanceof ApiError ? e.status : -1;
      if (status === 0) {
        setError("Could not reach the server. Try again; the retry repeats this same review, it does not add another.");
      } else if (status === 409) {
        setOpen(false);
        onOutcome("stale");
      } else if (status === 401 || status === 403) {
        setOpen(false);
        onOutcome("expired");
      } else {
        intentKey.current = crypto.randomUUID();
        setError(`The review was not recorded (${e instanceof ApiError ? e.code : "REQUEST_FAILED"}).`);
      }
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogTrigger asChild>
        <Button className="h-10 w-full">Mark reviewed — simulation</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Mark reviewed — simulation</DialogTitle>
          <DialogDescription>
            Records that you reviewed the {METHOD_LABEL[plan.method]} plan on frozen scenario {shortId(scenarioId)}. No stock, purchase or dispatch effect; nothing is reserved or sent.
          </DialogDescription>
        </DialogHeader>
        <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          <div className="grid gap-1.5">
            <Label htmlFor="review-note">Note (optional)</Label>
            <Textarea id="review-note" value={note} maxLength={500} onChange={(event) => setNote(event.target.value)} disabled={busy} />
          </div>
          {error && <p role="alert" className="text-sm text-foreground">{error}</p>}
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="outline" disabled={busy}>Cancel</Button></DialogClose>
            <Button type="submit" disabled={busy}>{busy ? "Recording…" : "Mark reviewed"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
