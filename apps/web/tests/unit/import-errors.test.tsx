// covers: V1-A07, V1-A23
import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { ImportErrors } from "@/components/import/import-errors";
import { ImportProgress } from "@/components/import/import-progress";
import { lastHistoryDate, NetworkSettings, type NetworkSettingsValue } from "@/components/import/network-settings";
import { example } from "./contract-examples";

const failed = example("ImportStatus");

function done(patch: Partial<ReturnType<typeof example<"ImportStatus">>> = {}) {
  return { ...example("ImportStatus"), phase: "done" as const, failure: null, errors: [], error_count: 0,
    network_id: "8b2f4c1e-3a5d-4e6f-9a7b-1c2d3e4f5a60", dataset_version_id: "2d4e6f80-1a3b-4c5d-8e9f-0a1b2c3d4e5f", as_of_date: "2026-11-05", ...patch };
}

it("renders file, line, column and reason per error", () => {
  render(<ImportErrors status={failed} onStartOver={() => {}} />);
  const table = screen.getByRole("table", { name: /Rows to fix/ });
  for (const error of failed.errors) {
    const row = within(table).getByRole("row", { name: new RegExp(`${error.file}\\.csv.*\\b${error.line}\\b.*${error.column}`) });
    expect(row).toHaveTextContent(error.reason);
    expect(row).toHaveTextContent(error.fix);
    if (error.value !== null && error.value !== undefined) expect(row).toHaveTextContent(error.value);
  }
});

it('shows "first 1,000 of N errors" when error_count > 1000', () => {
  const many = { ...failed, error_count: 2345, errors_truncated: true,
    errors: Array.from({ length: 1000 }, (_, i) => ({ ...failed.errors[0], line: i + 2 })) };
  render(<ImportErrors status={many} onStartOver={() => {}} />);
  expect(screen.getByText("Showing the first 1,000 of 2,345 errors.")).toBeVisible();
  const { container } = render(<ImportErrors status={failed} onStartOver={() => {}} />);
  expect(container).not.toHaveTextContent(/first 1,000 of/);
});

it('failure panel shows ImportStatus.failure: message, reason and every next step, plus a "start a new import" action', async () => {
  const onStartOver = vi.fn();
  render(<ImportErrors status={failed} onStartOver={onStartOver} />);
  const panel = screen.getByRole("alert");
  expect(panel).toHaveTextContent(failed.failure!.message);
  expect(panel).toHaveTextContent(failed.failure!.reason);
  const steps = within(panel).getAllByRole("listitem");
  expect(steps.map((s) => s.textContent)).toEqual(failed.failure!.next_steps);
  await userEvent.click(screen.getByRole("button", { name: "Start a new import" }));
  expect(onStartOver).toHaveBeenCalledOnce();
});

it("outside-horizon inbound listed", () => {
  const status = done({
    files: [...failed.files, { name: "inbound", bytes: 120, sha256: "c".repeat(64) }],
    outside_horizon_inbound: [{ line: 7, location_id: "P12", product_id: "WATER", quantity: 40, arrival_date: "2026-11-20" }],
  });
  render(<ImportProgress status={status} />);
  const table = screen.getByRole("table", { name: /outside the 7-day horizon/ });
  expect(within(table).getByRole("row", { name: /\b7\b.*P12.*WATER.*40.*2026-11-20/ })).toBeVisible();
  expect(screen.queryByText("no scheduled deliveries provided")).not.toBeInTheDocument();
});

it('"no scheduled deliveries provided" when no inbound.csv', () => {
  render(<ImportProgress status={done()} />);
  expect(screen.getByText("no scheduled deliveries provided")).toBeVisible();
  expect(screen.queryByRole("table", { name: /outside the 7-day horizon/ })).not.toBeInTheDocument();
});

function Settings({ last }: { last: string | null }) {
  const [value, setValue] = useState<NetworkSettingsValue>({ name: "", mode: null, timezone: "America/New_York", asOfDate: null });
  return <NetworkSettings value={value} onChange={setValue} lastHistoryDate={last} />;
}

it("one timezone field with the single-timezone note", () => {
  render(<Settings last={null} />);
  expect(screen.getAllByLabelText(/timezone/i)).toHaveLength(1);
  expect(screen.getByText(/Every location plans on this network's day boundaries; per-location timezones are not supported\./)).toBeVisible();
});

it("as_of_date defaults to day after last history and is editable", async () => {
  const user = userEvent.setup();
  render(<Settings last="2026-11-04" />);
  const input = screen.getByLabelText("Stock snapshot date (as_of_date)");
  expect(input).toHaveValue("2026-11-05");
  expect(screen.getByText(/Defaults to the day after your last history date \(2026-11-04\)/)).toBeVisible();
  await user.clear(input);
  await user.type(input, "2026-11-07");
  expect(input).toHaveValue("2026-11-07");
});

it("reads the last date from demand_history.csv, whatever the row order", async () => {
  const csv = "﻿location_id,product_id,date,quantity,basis\r\nP1,W,2026-11-03,4,demand\r\n\"P,2\",W,2026-11-04,,sales\r\nP1,W,2026-10-30,2,demand\r\n";
  expect(await lastHistoryDate(new Blob([csv]))).toBe("2026-11-04");
  expect(await lastHistoryDate(new Blob(["location_id,product_id,quantity\n"]))).toBeNull();
});

it("ignores impossible dates, so the as_of_date default is always a real day", async () => {
  // Each bad value sorts after 2026-11-04; the server reports those rows, the default ignores them.
  const csv = ["location_id,product_id,date,quantity,basis", "P1,W,2026-11-04,3,demand", "P1,W,2026-13-45,1,demand",
    "P1,W,2026-11-31,1,demand", "P1,W,9999-12-31,1,demand"].join("\n");
  expect(await lastHistoryDate(new Blob([csv]))).toBe("2026-11-04");
  expect(await lastHistoryDate(new Blob(["date\n2026-00-10\n"]))).toBeNull();
});
