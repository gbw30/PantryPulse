"use client";

import { useEffect, useState } from "react";
import { ApiError, planningApi, type Schema } from "@/lib/planning-api";
import type { Loaded } from "./model";

// Saved-result reads only (no compute on GET). Each load is keyed by what it asked for; a response
// that arrives after the selection or retry moved on is dropped, so a slow earlier comparison can
// never replace the one on screen.

export type CatalogState =
  | { kind: "loading" }
  | { kind: "error"; code: string }
  | { kind: "ready"; comparisons: Schema["SavedItem"][]; productNames: Map<string, string> };

export type ComparisonState =
  | { kind: "loading" }
  | { kind: "computing" }
  | { kind: "error"; code: string }
  | { kind: "ready"; loaded: Loaded };

const codeOf = (error: unknown) => (error instanceof ApiError ? error.code : "REQUEST_FAILED");
const unauthorized = (error: unknown) => error instanceof ApiError && (error.status === 401 || error.status === 403);

export function useCatalog(enabled: boolean, onUnauthorized: () => void) {
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<{ key: number; value: CatalogState } | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    (async () => {
      // Product names are optional context; units still come from the frozen scenario.
      const [items, names] = await Promise.allSettled([planningApi.planningCatalog(), planningApi.forecastCatalog()]);
      if (!active) return;
      if (items.status === "rejected") {
        if (unauthorized(items.reason)) onUnauthorized();
        setResult({ key: nonce, value: { kind: "error", code: codeOf(items.reason) } });
        return;
      }
      const productNames = new Map(names.status === "fulfilled" ? names.value.products.map((product) => [product.id, product.name] as const) : []);
      setResult({ key: nonce, value: { kind: "ready", comparisons: items.value.comparisons, productNames } });
    })();
    return () => { active = false; };
  }, [enabled, nonce, onUnauthorized]);

  const state: CatalogState = result?.key === nonce ? result.value : { kind: "loading" };
  return { state, retry: () => setNonce((n) => n + 1) };
}

export function useComparison(comparisonId: string | null, productNames: Map<string, string> | null, onUnauthorized: () => void) {
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<{ key: string; value: ComparisonState } | null>(null);
  const key = `${comparisonId}:${nonce}`;

  useEffect(() => {
    if (!comparisonId || !productNames) return;
    let active = true;
    const finish = (value: ComparisonState) => { if (active) setResult({ key, value }); };
    (async () => {
      const [saved, results] = await Promise.allSettled([planningApi.comparison(comparisonId), planningApi.allocationResults(comparisonId)]);
      if (!active) return;
      if (saved.status === "rejected") {
        if (unauthorized(saved.reason)) onUnauthorized();
        const code = codeOf(saved.reason);
        return finish(code === "COMPARISON_NOT_PUBLISHED" ? { kind: "computing" } : { kind: "error", code });
      }
      let scenario: Schema["ScenarioResult"];
      try {
        scenario = await planningApi.scenario(saved.value.scenario_id);
      } catch (error) {
        if (active && unauthorized(error)) onUnauthorized();
        return finish({ kind: "error", code: codeOf(error) });
      }
      finish({ kind: "ready", loaded: {
        comparison: saved.value, scenario, productNames,
        plans: results.status === "fulfilled" ? results.value.plans : null,
        plansError: results.status === "rejected" ? codeOf(results.reason) : null,
      } });
    })();
    return () => { active = false; };
  }, [comparisonId, key, productNames, onUnauthorized]);

  const state: ComparisonState = result?.key === key ? result.value : { kind: "loading" };
  return { state, retry: () => setNonce((n) => n + 1) };
}
