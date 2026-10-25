"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2, LockKeyhole } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { usePresenter } from "@/components/shell/presenter-session";
import type { ImportFeedback } from "./api";

// Provisional Data Explorer header for the data-input subviews. At integration the lead swaps the tab
// strip for the Data Explorer's shared header (PP-53) so all subviews use one component.
const TABS = [
  { key: "dashboard", label: "Dashboard", href: "/data" },
  { key: "pulse", label: "Seven-Day Pulse", href: "/data/pulse" },
  { key: "operations", label: "Operations Board", href: "/data/operations" },
  { key: "inventory", label: "Inventory & Lots", href: "/data/inventory" },
  { key: "inputs", label: "Data input", href: "/data/inputs", presenterOnly: true },
] as const;

export function DataInputHeader({ active, title, description }: { active: "inventory" | "inputs"; title: string; description: string }) {
  const { state } = usePresenter();
  return (
    <header className="flex flex-col gap-3">
      <div>
        <p className="font-condensed text-xs font-semibold tracking-[0.16em] text-muted-foreground uppercase">Forecasts &amp; inventory</p>
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight md:text-[28px]">{title}</h1>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <nav aria-label="Data Explorer views" className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
        <ul className="flex min-w-max gap-1 border-b border-border">
          {TABS.filter((tab) => !("presenterOnly" in tab) || state === "presenter").map((tab) => (
            <li key={tab.key}>
              <Link href={tab.href} aria-current={tab.key === active ? "page" : undefined}
                className={`inline-flex h-10 items-center border-b-2 px-3 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring ${tab.key === active ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
                {tab.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
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
        <p>{message}</p>
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
