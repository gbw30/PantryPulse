"use client";

import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import { formatMeals, type Outlook, type OutlookPoint } from "./outlook-data";

type Props = { outlook: Outlook; animate: boolean };

function OutlookTooltip({ active, payload, label }: TooltipContentProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload as OutlookPoint;
  const rows: [string, number | undefined, string][] = [
    ["Observed", point.observed, "var(--lab-fg)"],
    ["Without route", point.withoutRoute, "var(--lab-forecast)"],
    ["With route", point.withRoute, "var(--lab-accent)"],
  ];
  return (
    <div className="lab-tip">
      <strong>{label}</strong>
      {rows.filter(([, value]) => value !== undefined).map(([name, value, color]) => (
        <span key={name}><i style={{ background: color }} />{name}<b>{formatMeals(value as number)} meals</b></span>
      ))}
      {point.range && point.range[0] !== point.range[1] ? <small>Raw quantile range {formatMeals(point.range[0])} to {formatMeals(point.range[1])}</small> : null}
    </div>
  );
}

function EndTag({ x, y, value, color, index, last }: { x?: number; y?: number; value?: number; color: string; index?: number; last: number }) {
  if (index !== last || x === undefined || y === undefined || value === undefined) return null;
  return <text x={x + 9} y={y} dy="0.35em" fill={color} className="lab-end-tag">{formatMeals(value)}</text>;
}

export function ForecastChart({ outlook, animate }: Props) {
  const { points } = outlook;
  const last = points.length - 1;
  const lows = points.flatMap((p) => [p.observed, p.withoutRoute, p.withRoute, p.range?.[0]]).filter((v): v is number => v !== undefined);
  const highs = points.flatMap((p) => [p.observed, p.withoutRoute, p.withRoute, p.range?.[1]]).filter((v): v is number => v !== undefined);
  const floor = Math.min(0, Math.floor((Math.min(...lows) - 8) / 40) * 40);
  const ceiling = Math.ceil((Math.max(...highs) + 8) / 40) * 40;
  const ticks = Array.from({ length: (ceiling - floor) / 40 + 1 }, (_, index) => floor + index * 40);
  const hasRoute = outlook.endWith !== null;

  return (
    <div className="lab-chart">
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 800, height: 280 }}>
        <ComposedChart data={points} margin={{ top: 18, right: 52, bottom: 4, left: 0 }} accessibilityLayer>
          <defs>
            <pattern id="labUnmet" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="7" stroke="var(--lab-attention)" strokeWidth="2" opacity="0.4" />
            </pattern>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--lab-border-soft)" />
          {floor < 0 ? <ReferenceArea y1={floor} y2={0} fill="url(#labUnmet)" ifOverflow="hidden" /> : null}
          <XAxis dataKey="day" tickLine={false} axisLine={{ stroke: "var(--lab-border)" }} tick={{ fill: "var(--lab-muted)", fontSize: 12 }} interval="preserveStartEnd" minTickGap={14} />
          <YAxis domain={[floor, ceiling]} ticks={ticks} tickLine={false} axisLine={false} width={44} tick={{ fill: "var(--lab-muted)", fontSize: 12 }} tickFormatter={formatMeals} />
          <ReferenceLine y={0} stroke="var(--lab-fg)" strokeOpacity={0.55} />
          <ReferenceLine x={outlook.forecastStart} stroke="var(--lab-muted)" strokeDasharray="2 4" label={{ value: "Forecast starts", position: "insideTopLeft", fill: "var(--lab-muted)", fontSize: 11, dx: 6 }} />
          <Area dataKey="range" type="linear" stroke="none" fill="var(--lab-forecast)" fillOpacity={0.14} isAnimationActive={animate} connectNulls={false} />
          <Line dataKey="observed" type="linear" stroke="var(--lab-fg)" strokeWidth={2.4} dot={{ r: 3, fill: "var(--lab-fg)", strokeWidth: 0 }} activeDot={{ r: 5 }} isAnimationActive={animate} />
          <Line dataKey="withoutRoute" type="linear" stroke="var(--lab-forecast)" strokeWidth={2.2} strokeDasharray="7 5" dot={false} activeDot={{ r: 5 }} isAnimationActive={animate} label={<EndTag color="var(--lab-forecast)" last={last} />} />
          {hasRoute ? <Line dataKey="withRoute" type="linear" stroke="var(--lab-accent)" strokeWidth={2.8} strokeDasharray="2 4" strokeLinecap="round" dot={false} activeDot={{ r: 5 }} isAnimationActive={animate} label={<EndTag color="var(--lab-accent)" last={last} />} /> : null}
          {outlook.firstShortageDay ? <ReferenceDot x={outlook.firstShortageDay} y={points.find((p) => p.day === outlook.firstShortageDay)?.withoutRoute} r={6} fill="var(--lab-bg)" stroke="var(--lab-attention)" strokeWidth={2.5} /> : null}
          <Tooltip content={OutlookTooltip} cursor={{ stroke: "var(--lab-muted)", strokeDasharray: "2 3" }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
