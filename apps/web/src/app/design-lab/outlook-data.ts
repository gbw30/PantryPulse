// Illustrative cumulative meals balances for the design lab only. Simulated data: no inventory,
// forecast model output or allocation result is read from the API here.
// Negative balances represent cumulative shortfall, never physical stock.

export type OutlookPoint = {
  day: string;
  observed?: number;
  withoutRoute?: number;
  withRoute?: number;
  range?: [number, number];
};

export type Outlook = {
  points: OutlookPoint[];
  forecastStart: string;
  firstShortageDay: string | null;
  endWithout: number;
  endWith: number | null;
  transferQty: number;
  transferDay: string | null;
  coverDays: number;
  coverFraction: number;
  summary: string;
};

const DAYS = ["Thu 15", "Fri 16", "Sat 17", "Sun 18", "Mon 19", "Tue 20", "Wed 21", "Thu 22", "Fri 23", "Sat 24", "Sun 25"];
const FORECAST_FROM = 3;
const WEEKDAY: Record<string, string> = { Mon: "Monday", Tue: "Tuesday", Wed: "Wednesday", Thu: "Thursday", Fri: "Friday", Sat: "Saturday", Sun: "Sunday" };

type Params = { start: number; demand: number[]; transfer?: { dayIndex: number; qty: number } };

const params: Record<string, Params> = {
  riverbend: { start: 40, demand: [26, 22, 20, 18, 21, 26, 27], transfer: { dayIndex: 1, qty: 80 } },
  oak: { start: 60, demand: [20, 19, 18, 17, 22, 27, 27] },
  cedar: { start: 150, demand: [18, 17, 17, 16, 19, 22, 21] },
  maple: { start: 120, demand: [15, 14, 14, 13, 16, 18, 17] },
  willow: { start: 140, demand: [16, 15, 15, 14, 17, 20, 19] },
  pine: { start: 130, demand: [17, 16, 15, 15, 18, 21, 20] },
};

export function coverFor(siteId: string): { days: number; fraction: number } | null {
  const p = params[siteId];
  if (!p) return null;
  const daily = p.demand.reduce((sum, value) => sum + value, 0) / p.demand.length;
  const days = p.start / daily;
  return { days, fraction: Math.min(days, 7) / 7 };
}

export function formatMeals(value: number) {
  return `${value < 0 ? "−" : ""}${Math.abs(value)}`;
}

export function buildOutlook(siteId: string, siteName: string): Outlook | null {
  const p = params[siteId];
  const cover = coverFor(siteId);
  if (!p || !cover) return null;
  const avg = p.demand.reduce((sum, value) => sum + value, 0) / p.demand.length;

  // Observed on-hand stock before the forecast starts, stepping back from the opening balance.
  const observed = [0, 0, 0, p.start];
  observed[2] = p.start + Math.round(avg * 0.9);
  observed[1] = observed[2] + Math.round(avg);
  observed[0] = observed[1] + Math.round(avg * 1.1);

  const withoutRoute: number[] = [];
  const withRoute: number[] = [];
  let balance = p.start;
  let routed = p.start;
  p.demand.forEach((demand, index) => {
    balance -= demand;
    routed -= demand;
    if (p.transfer && index >= p.transfer.dayIndex) routed += index === p.transfer.dayIndex ? p.transfer.qty : 0;
    withoutRoute.push(balance);
    withRoute.push(routed);
  });

  const points: OutlookPoint[] = DAYS.map((day, index) => {
    const point: OutlookPoint = { day };
    if (index <= FORECAST_FROM) point.observed = observed[index];
    if (index >= FORECAST_FROM) {
      const step = index - FORECAST_FROM;
      const value = step === 0 ? p.start : withoutRoute[step - 1];
      point.withoutRoute = value;
      // This hand-authored spread illustrates a band; it is not model quantiles or a calibrated interval.
      const spread = step === 0 ? 0 : Math.round(3 + step * 2.6);
      point.range = [value - spread, value + spread];
      if (p.transfer) point.withRoute = step === 0 ? p.start : withRoute[step - 1];
    }
    return point;
  });

  const firstShortageIndex = withoutRoute.findIndex((value) => value < 0);
  const firstShortageDay = firstShortageIndex >= 0 ? DAYS[FORECAST_FROM + 1 + firstShortageIndex] : null;
  const endWithout = withoutRoute[withoutRoute.length - 1];
  const endWith = p.transfer ? withRoute[withRoute.length - 1] : null;
  const transferDay = p.transfer ? DAYS[FORECAST_FROM + 1 + p.transfer.dayIndex] : null;
  const dayName = (label: string | null) => (label ? WEEKDAY[label.split(" ")[0]] : "");

  let summary: string;
  if (firstShortageDay && p.transfer && endWith !== null) {
    summary = `Without the proposed route, ${siteName} runs out of meals on ${dayName(firstShortageDay)} and ends the week ${Math.abs(endWithout)} meals short. With ${p.transfer.qty} meals from Gator Hub on ${dayName(transferDay)}, it ends ${Math.abs(endWith)} short.`;
  } else if (firstShortageDay) {
    summary = `${siteName} runs out of meals on ${dayName(firstShortageDay)} and ends the week ${Math.abs(endWithout)} meals short. No route is proposed in this sample.`;
  } else {
    summary = `Current stock covers the forecast demand for ${siteName}. It ends the week with ${endWithout} meals on hand.`;
  }

  return {
    points,
    forecastStart: DAYS[FORECAST_FROM],
    firstShortageDay,
    endWithout,
    endWith,
    transferQty: p.transfer?.qty ?? 0,
    transferDay,
    coverDays: cover.days,
    coverFraction: cover.fraction,
    summary,
  };
}
