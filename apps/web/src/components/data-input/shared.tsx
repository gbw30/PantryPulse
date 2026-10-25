"use client";

import { AlertTriangle, CheckCircle2, LockKeyhole } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataExplorerHeader } from "@/components/data-explorer/header";
import type { ImportFeedback } from "./api";

// The shared Data Explorer chrome (PP-53) carries the tab strip; each data-input subview adds its
// own section heading under it.
export function DataInputHeader({ active, title, description }: { active: "inventory" | "inputs"; title: string; description: string }) {
  return (
    <div className="flex flex-col gap-3">
      <DataExplorerHeader active={active} />
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

export function PresenterRequired({ what }: { what: string }) {
  return (
    <Alert>
      <LockKeyhole aria-hidden="true" />
      <AlertTitle>Presenter sign-in required</AlertTitle>
      <AlertDescription>{what} Visitors stay read-only; use Presenter sign in in the sidebar.</AlertDescription>
    </Alert>
  );
}

export function ErrorAlert({ message, onRetry, retryLabel = "Retry" }: { message: string; onRetry?: () => void; retryLabel?: string }) {
  return (
    <Alert variant="destructive" role="alert">
      <AlertTriangle aria-hidden="true" />
      <AlertTitle>Not saved</AlertTitle>
      <AlertDescription className="text-foreground">
        {/* The destructive variant tints the description; keep the message at body contrast. */}
        <p className="text-foreground">{message}</p>
        {onRetry && <Button type="button" variant="outline" size="sm" className="mt-2" onClick={onRetry}>{retryLabel}</Button>}
      </AlertDescription>
    </Alert>
  );
}

export function SavedAlert({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <Alert role="status">
      <CheckCircle2 aria-hidden="true" className="text-pp-teal" />
      <AlertTitle>{title}</AlertTitle>
      {children && <AlertDescription className="text-foreground">{children}</AlertDescription>}
    </Alert>
  );
}

/** Atomic import rejection: nothing was saved; every rejected row is listed (1-based). */
export function ImportFeedbackTable({ feedback }: { feedback: ImportFeedback }) {
  const errors = feedback.errors ?? [];
  return (
    <div className="grid gap-2" role="alert">
      <p className="text-sm font-medium">No rows were saved. {feedback.rejected_count ?? "?"} row(s) submitted; the import is all-or-nothing.</p>
      <Table>
        <TableCaption>Rejected rows (row numbers start at 1)</TableCaption>
        <TableHeader><TableRow><TableHead>Row</TableHead><TableHead>Field</TableHead><TableHead>Problem code</TableHead></TableRow></TableHeader>
        <TableBody>
          {errors.map((error, index) => (
            <TableRow key={`${error.row_index}-${error.field}-${index}`}>
              <TableCell className="tabular-nums">{error.row_index === null ? "Whole request" : error.row_index + 1}</TableCell>
              <TableCell>{error.field}</TableCell>
              <TableCell className="font-mono text-xs">{error.code}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

/** Label + control + optional hint/error, wired with aria-describedby. */
export function Field({ id, label, hint, error, children }: { id: string; label: string; hint?: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p id={`${id}-hint`} className="text-xs text-muted-foreground">{hint}</p>}
      {error && <p id={`${id}-error`} className="text-xs font-medium text-foreground">⚠ {error}</p>}
    </div>
  );
}

export const describedBy = (id: string, hint?: string, error?: string) =>
  [hint ? `${id}-hint` : "", error ? `${id}-error` : ""].filter(Boolean).join(" ") || undefined;

export const nativeSelect = "h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50";
