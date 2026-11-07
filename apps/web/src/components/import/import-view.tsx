"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { AppShell } from "@/components/shell/app-shell";
import { networkApi, type TemplateCatalog, type TemplateName } from "@/lib/network-api";
import { ApiError } from "@/lib/planning-api";
import { TemplateGuide } from "./template-guide";

type CatalogState = { status: "loading" } | { status: "signed_out" } | { status: "error"; code: string } | { status: "ready"; catalog: TemplateCatalog };

function useTemplateCatalog() {
  const [state, setState] = useState<CatalogState>({ status: "loading" });
  const [reasons, setReasons] = useState<Partial<Record<TemplateName, string>>>({});
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    networkApi.templates().then(
      (catalog) => {
        if (!active) return;
        setState({ status: "ready", catalog });
        for (const template of catalog.templates.filter((t) => !t.example_available)) {
          networkApi.exampleUnavailableReason(template.name).then(
            (reason) => { if (active && reason) setReasons((current) => ({ ...current, [template.name]: reason })); },
            () => undefined, // The disabled button still says "not available yet" without a reason.
          );
        }
      },
      (error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) setState({ status: "signed_out" });
        else setState({ status: "error", code: error instanceof ApiError ? error.code : "REQUEST_FAILED" });
      },
    );
    return () => { active = false; };
  }, [attempt]);
  return { state, reasons, retry: () => { setState({ status: "loading" }); setAttempt((n) => n + 1); } };
}

export function ImportView() {
  const { state, reasons, retry } = useTemplateCatalog();
  return (
    <AppShell active="import">
      <div className="flex flex-1 flex-col gap-6 px-4 pt-3 pb-6 md:px-6 md:py-5">
        <header className="grid gap-1">
          <p className="font-condensed text-xs font-semibold tracking-[0.16em] text-muted-foreground uppercase">Bring your own network</p>
          <h1 className="text-[26px] leading-tight font-semibold tracking-tight md:text-[28px]">Import your network</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Fill in the CSV templates with your locations, products, stock and daily history, then upload them together.
            Nothing is saved unless every file passes.
          </p>
        </header>

        <section aria-labelledby="templates-heading" className="grid gap-3">
          <h2 id="templates-heading" className="text-lg font-semibold">1. Get the templates</h2>
          {state.status === "loading" && <p className="text-sm text-muted-foreground" role="status">Loading templates…</p>}
          {state.status === "signed_out" && <p className="text-sm">Sign in to download templates and import data.</p>}
          {state.status === "error" && (
            <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
              Templates unavailable ({state.code.replaceAll("_", " ").toLowerCase()}).
              <Button variant="outline" size="sm" onClick={retry}>Retry</Button>
            </div>
          )}
          {state.status === "ready" && <TemplateGuide catalog={state.catalog} exampleReasons={reasons} />}
        </section>
      </div>
    </AppShell>
  );
}
