"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { AppShell } from "@/components/shell/app-shell";
import { useNetwork } from "@/components/shell/network-switcher";
import { networkApi, type ImportStatus, type TemplateCatalog, type TemplateName } from "@/lib/network-api";
import { ApiError } from "@/lib/planning-api";
import { ImportErrors } from "./import-errors";
import { ImportProgress, PHASE_LABEL } from "./import-progress";
import { asOfDateToSend, lastHistoryDate, NetworkSettings, type NetworkSettingsValue } from "./network-settings";
import { TemplateGuide } from "./template-guide";
import { UploadForm, type ChosenFiles } from "./upload-form";

type CatalogState = { status: "loading" } | { status: "signed_out" } | { status: "error"; code: string } | { status: "ready"; catalog: TemplateCatalog };
type Run =
  | { step: "idle" }
  | { step: "uploading"; done: number; total: number }
  | { step: "tracking"; status: ImportStatus | null }
  | { step: "request_failed"; code: string }
  /** The commit may have been accepted, but no status could be read or understood: the import may still finish. */
  | { step: "lost"; importId: string; reason: string };

const POLL_MS = 1000;
const TERMINAL = new Set<ImportStatus["phase"]>(["done", "failed"]);
const describe = (code: string) => code.replaceAll("_", " ").toLowerCase();
const codeOf = (error: unknown) => (error instanceof ApiError ? error.code : "REQUEST_FAILED");
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** The template catalog for the chosen mode. A mode change keeps the previous catalog while it reloads. */
function useTemplateCatalog(mode: NetworkSettingsValue["mode"]) {
  const [state, setState] = useState<CatalogState>({ status: "loading" });
  const [reasons, setReasons] = useState<Partial<Record<TemplateName, string>>>({});
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    networkApi.templates(mode ?? undefined).then(
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
  }, [mode, attempt]);
  return { state, reasons, retry: () => { setState({ status: "loading" }); setAttempt((n) => n + 1); } };
}

const defaultTimezone = () => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; } catch { return "UTC"; } };

export function ImportView() {
  return <AppShell active="import"><ImportContent /></AppShell>;
}

/** Inside AppShell so it can read the chosen network. */
function ImportContent() {
  const { network, reload: reloadNetworks, select: selectNetwork } = useNetwork();
  const [target, setTarget] = useState<"new" | "existing">("new");
  const reimport = target === "existing" && network !== null && !network.is_sample ? network : null;
  const [settings, setSettings] = useState<NetworkSettingsValue>(() => ({ name: "", mode: null, timezone: defaultTimezone(), asOfDate: null }));
  const { state, reasons, retry } = useTemplateCatalog(reimport?.mode ?? settings.mode);
  const [files, setFiles] = useState<ChosenFiles>({});
  const [formKey, setFormKey] = useState(0); // remounts the file inputs on "Start a new import"
  const [lastHistory, setLastHistory] = useState<string | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [run, setRun] = useState<Run>({ step: "idle" });
  const alive = useRef(true);
  const scan = useRef(0); // only the latest demand_history scan may set the default date
  const uploadHeading = useRef<HTMLHeadingElement>(null);
  // Set on mount too: Strict Mode runs the cleanup once before the real mount.
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  const templates = state.status === "ready" ? state.catalog.templates : [];
  // "lost": the accepted import may still commit, so a second submit could save a second copy.
  const busy = run.step === "uploading" || run.step === "lost" || (run.step === "tracking" && (!run.status || !TERMINAL.has(run.status.phase)));

  function chooseFile(name: TemplateName, file: File | null) {
    setFiles((current) => {
      const next = { ...current };
      if (file) next[name] = file; else delete next[name];
      return next;
    });
    if (name === "demand_history") {
      setLastHistory(null);
      const token = ++scan.current;
      if (file) lastHistoryDate(file).then((last) => { if (alive.current && token === scan.current) setLastHistory(last); }, () => undefined);
    }
  }

  function check(): string[] {
    const missing: string[] = [];
    if (!reimport) {
      if (!settings.name.trim()) missing.push("Enter a network name.");
      if (!settings.mode) missing.push("Choose a network mode.");
    }
    const absent = templates.filter((t) => t.required && !files[t.name]).map((t) => `${t.name}.csv`);
    if (absent.length) missing.push(`Choose the required files: ${absent.join(", ")}.`);
    return missing;
  }

  async function submit() {
    const missing = check();
    setProblems(missing);
    if (missing.length) return;
    const chosen = templates.filter((t) => files[t.name]).map((t) => [t.name, files[t.name]!] as const);
    let importId: string | null = null;
    try {
      setRun({ step: "uploading", done: 0, total: chosen.length });
      const created = await networkApi.createImport(reimport
        ? { network_id: reimport.id }
        : { network: { name: settings.name.trim(), mode: settings.mode!, timezone: settings.timezone } });
      for (const [index, [name, file]] of chosen.entries()) {
        await networkApi.uploadImportFile(created.import_id, name, file);
        if (alive.current) setRun({ step: "uploading", done: index + 1, total: chosen.length });
      }
      importId = created.import_id;
      await networkApi.commitImport(importId, { as_of_date: asOfDateToSend(settings, lastHistory) });
    } catch (error) {
      // Nothing is saved before the commit or when it is refused (4xx). A commit with no answer may have been accepted: read the run.
      const refused = error instanceof ApiError && error.status >= 400 && error.status < 500;
      if (importId === null || refused) {
        if (alive.current) setRun({ step: "request_failed", code: codeOf(error) });
        return;
      }
    }
    await track(importId);
  }

  /** Poll an accepted import until it is done or failed. */
  async function track(importId: string) {
    setRun({ step: "tracking", status: null });
    try {
      for (;;) {
        const status = await networkApi.importStatus(importId);
        if (!alive.current) return;
        if (!Object.hasOwn(PHASE_LABEL, status.phase)) {
          setRun({ step: "lost", importId, reason: `The import reported a status this page doesn't know (${describe(status.phase)}).` });
          return;
        }
        setRun({ step: "tracking", status });
        if (TERMINAL.has(status.phase)) {
          if (status.phase === "done") {
            reloadNetworks();
            if (status.network_id) selectNetwork(status.network_id);
          }
          return;
        }
        await sleep(POLL_MS);
      }
    } catch (error) {
      if (alive.current) setRun({ step: "lost", importId, reason: `Lost contact with the import (${describe(codeOf(error))}).` });
    }
  }

  function startOver() {
    scan.current += 1;
    setRun({ step: "idle" });
    setFiles({});
    setLastHistory(null);
    setProblems([]);
    setFormKey((n) => n + 1);
    // The button that called this goes away; keyboard focus continues at the files to choose again.
    uploadHeading.current?.focus();
  }

  const status = run.step === "tracking" ? run.status : null;
  return (
    <div className="flex flex-1 flex-col gap-6 px-4 pt-3 pb-6 md:px-6 md:py-5">
      <header className="grid gap-1">
        <p className="font-condensed text-xs font-semibold tracking-[0.16em] text-muted-foreground uppercase">Bring your own network</p>
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight md:text-[28px]">Import your network</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Fill in the CSV templates with your locations, products, stock and daily history, then upload them together.
          Nothing is saved unless every file passes.
        </p>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Addresses without latitude and longitude are sent to the US Census Geocoder (a free public lookup, no key) after the import, to find their
          coordinates and census tract. Locations with coordinates are never sent. If the lookup can&apos;t be reached, those values stay unknown and
          Settings offers a retry.
        </p>
      </header>

      <section aria-labelledby="templates-heading" className="grid gap-3">
        <h2 id="templates-heading" className="text-lg font-semibold">1. Get the templates</h2>
        {state.status === "loading" && <p className="text-sm text-muted-foreground" role="status">Loading templates…</p>}
        {state.status === "signed_out" && <p className="text-sm">Sign in to download templates and import data.</p>}
        {state.status === "error" && (
          <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
            Templates unavailable ({describe(state.code)}).
            <Button variant="outline" size="sm" onClick={retry}>Retry</Button>
          </div>
        )}
        {state.status === "ready" && <TemplateGuide catalog={state.catalog} exampleReasons={reasons} />}
      </section>

      {state.status === "ready" && (
        <>
          <section aria-labelledby="settings-heading" className="grid gap-3">
            <h2 id="settings-heading" className="text-lg font-semibold">2. Network settings</h2>
            {network && !network.is_sample && (
              <fieldset disabled={busy} className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                <legend className="sr-only">What are you importing?</legend>
                <label className="flex items-center gap-2"><input type="radio" name="import-target" checked={target === "new"} onChange={() => setTarget("new")} /> A new network</label>
                <label className="flex items-center gap-2"><input type="radio" name="import-target" checked={target === "existing"} onChange={() => setTarget("existing")} /> A newer snapshot of {network.name}</label>
              </fieldset>
            )}
            {reimport && (
              <p className="text-sm text-muted-foreground">
                Re-importing creates a new dataset version of {reimport.name}; its mode and timezone ({reimport.timezone}) stay fixed, and earlier scenarios keep the version they used.
              </p>
            )}
            <NetworkSettings value={settings} onChange={setSettings} lastHistoryDate={lastHistory} existing={reimport !== null} disabled={busy} />
          </section>

          <section aria-labelledby="upload-heading" className="grid gap-3">
            <h2 id="upload-heading" ref={uploadHeading} tabIndex={-1} className="text-lg font-semibold outline-none">3. Upload your files</h2>
            <UploadForm key={formKey} templates={templates} files={files} onChange={chooseFile} disabled={busy} />
            {problems.length > 0 && (
              <div role="alert" className="rounded-lg border border-pp-warning/50 bg-card px-4 py-3 text-sm">
                <p className="font-medium">Before importing:</p>
                <ul className="ml-5 list-disc">{problems.map((p) => <li key={p}>{p}</li>)}</ul>
              </div>
            )}
            {/* Busy stays focusable (aria-disabled): disabling the focused button would drop keyboard focus to the page. */}
            <Button className="h-11 justify-self-start aria-disabled:opacity-50" onClick={busy ? undefined : submit} aria-disabled={busy || undefined}>Check and import</Button>
            {run.step === "uploading" && <p role="status" className="text-sm">Uploading files: {run.done} of {run.total}</p>}
            {run.step === "tracking" && !status && <p role="status" className="text-sm">Starting the checks…</p>}
            {run.step === "request_failed" && (
              <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-pp-danger/40 bg-card px-4 py-3 text-sm">
                Import request failed ({describe(run.code)}). Nothing was saved.
                <Button variant="outline" size="sm" onClick={startOver}>Start a new import</Button>
              </div>
            )}
            {run.step === "lost" && (
              <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-pp-warning bg-card px-4 py-3 text-sm">
                {run.reason} It may still finish; nothing is known yet about what was saved.
                <Button variant="outline" size="sm" onClick={() => { const { importId } = run; void track(importId); }}>Check again</Button>
              </div>
            )}
            {status && <ImportProgress status={status} />}
            {status?.phase === "failed" && <ImportErrors status={status} onStartOver={startOver} />}
          </section>
        </>
      )}
    </div>
  );
}
