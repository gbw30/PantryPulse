"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { usePresenter } from "@/components/shell/presenter-session";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/planning-api";
import { dataInputApi, describeError, type OperationalCatalog } from "./api";
import { ImportsSection } from "./imports-section";
import { ProductsSection } from "./products-section";
import { ReceiptsSection } from "./receipts-section";
import { SuppliesSection } from "./supplies-section";
import { DataInputHeader, ErrorAlert, nativeSelect, PresenterRequired } from "./shared";

const SECTIONS = [
  { key: "demand", label: "Demand history" },
  { key: "coverage", label: "Donation coverage" },
  { key: "receipts", label: "Receipts" },
  { key: "supplies", label: "Expected supplies" },
  { key: "products", label: "Products" },
] as const;
type SectionKey = (typeof SECTIONS)[number]["key"];

function InputsContent() {
  const { state, expired } = usePresenter();
  const [catalog, setCatalog] = useState<OperationalCatalog | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [section, setSection] = useState<SectionKey>("demand");

  useEffect(() => {
    if (state !== "presenter") return;
    let active = true;
    dataInputApi.catalog().then((value) => { if (active) setCatalog(value); }).catch((e) => {
      if (!active) return;
      if (e instanceof ApiError && e.status === 401) { expired(); return; }
      setError(e);
    });
    return () => { active = false; };
  }, [state, expired]);

  if (state === "checking") return <p role="status" className="text-sm text-muted-foreground">Checking presenter session…</p>;
  if (state === "visitor") return <PresenterRequired what="Entering demand history, donations, receipts, supplies and products changes the demo database." />;
  if (error) return <ErrorAlert message={describeError(error)} onRetry={() => { setCatalog(null); setError(null); dataInputApi.catalog().then(setCatalog).catch(setError); }} />;
  if (!catalog) return <Skeleton className="h-64 w-full" />;

  return (
    <div className="grid gap-4 lg:grid-cols-[14rem_1fr]">
      <nav aria-label="Data input sections" className="lg:border-r lg:border-border lg:pr-4">
        <label htmlFor="inputs-section" className="sr-only">Section</label>
        <select id="inputs-section" className={`${nativeSelect} lg:hidden`} value={section} onChange={(e) => setSection(e.target.value as SectionKey)}>
          {SECTIONS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        <ul className="hidden gap-1 lg:grid">
          {SECTIONS.map((s) => (
            <li key={s.key}>
              <button type="button" aria-current={section === s.key ? "true" : undefined} onClick={() => setSection(s.key)}
                className={`w-full rounded-md px-3 py-2 text-left text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring ${section === s.key ? "bg-pp-teal-soft text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <div className="min-w-0">
        {section === "demand" && <ImportsSection key="demand" catalog={catalog} coverage={false} />}
        {section === "coverage" && <ImportsSection key="coverage" catalog={catalog} coverage />}
        {section === "receipts" && <ReceiptsSection catalog={catalog} />}
        {section === "supplies" && <SuppliesSection catalog={catalog} />}
        {section === "products" && <ProductsSection catalog={catalog} onChanged={() => dataInputApi.catalog().then(setCatalog)} />}
      </div>
    </div>
  );
}

export function InputsView() {
  return (
    <AppShell active="data">
      <div className="flex flex-1 flex-col gap-4 px-4 pt-3 pb-6 md:gap-6 md:px-6 md:py-5">
        <DataInputHeader active="inputs" title="Data input" description="Presenter-only operational records for the simulated demo network: demand history, donation coverage, receipts, expected supplies and products." />
        <InputsContent />
      </div>
    </AppShell>
  );
}
