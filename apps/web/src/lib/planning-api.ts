import type { components } from "../../../../packages/contracts/src/schema";

export type Schema = components["schemas"];
export class ApiError extends Error {
  constructor(public code: string, public status: number) { super(code.replaceAll("_", " ").toLowerCase()); }
}
export async function api<T>(path: string, body?: unknown, idempotencyKey?: string): Promise<T> {
  const csrf = document.cookie.split("; ").find((item) => item.startsWith("pp_csrf="))?.slice(8);
  const response = await fetch(`/api/v1/${path}`, {
    method: body === undefined ? "GET" : "POST", cache: "no-store",
    headers: body === undefined ? {} : { "Content-Type": "application/json",
      "X-CSRF-Token": decodeURIComponent(csrf ?? ""), "Idempotency-Key": idempotencyKey ?? crypto.randomUUID() },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const value = await response.json();
  if (!response.ok) throw new ApiError(value.error?.code ?? "REQUEST_FAILED", response.status);
  return value as T;
}

export function localDay(timezone: string, offset = 0) {
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}
