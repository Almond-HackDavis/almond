"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardEyebrow, CardKicker, CardTitle } from "@/components/Card";
import { fmtAbsoluteDate } from "@/lib/format";
import type { VitalityPoint } from "@/lib/derive";

const TICKS = [50, 65, 80];

interface TimelineProps {
  data: VitalityPoint[];
}

export function VitalityTimeline({ data }: TimelineProps) {
  const decorated = data.map((p) => ({
    ...p,
    label: fmtAbsoluteDate(new Date(p.computed_at)),
  }));

  return (
    <Card className="p-7 lg:p-8">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <CardEyebrow>Vitality Timeline · {data.length} snapshots</CardEyebrow>
          <CardTitle className="mt-3">Trend overview</CardTitle>
        </div>
        <CardKicker className="hidden max-w-[42ch] text-right md:block">
          Each tick is one synchronized telemetry batch. Bands mark the published
          risk thresholds used for the at-a-glance chip on the dashboard.
        </CardKicker>
      </div>

      <div className="mt-6 -ml-2 h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={decorated} margin={{ top: 12, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="vitFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--color-cocoa)" stopOpacity="0.30" />
                <stop offset="80%" stopColor="var(--color-cocoa)" stopOpacity="0.02" />
              </linearGradient>
            </defs>

            <ReferenceArea y1={0}  y2={50}  fill="var(--color-risk-high-surface)"     fillOpacity={0.55} stroke="none" />
            <ReferenceArea y1={50} y2={65}  fill="var(--color-risk-elevated-surface)" fillOpacity={0.5}  stroke="none" />
            <ReferenceArea y1={65} y2={80}  fill="var(--color-risk-moderate-surface)" fillOpacity={0.45} stroke="none" />
            <ReferenceArea y1={80} y2={100} fill="var(--color-risk-low-surface)"      fillOpacity={0.4}  stroke="none" />

            <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
            <XAxis
              dataKey="computed_at"
              tickFormatter={(d: string) => {
                const date = new Date(d);
                return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
              }}
              minTickGap={48}
              stroke="var(--color-label-tertiary)"
              tick={{ fontFamily: "var(--font-mono)", fontSize: 10.5, letterSpacing: "0.06em" }}
              tickLine={false}
              axisLine={{ stroke: "var(--color-hairline)" }}
            />
            <YAxis
              domain={[40, 100]}
              ticks={TICKS}
              stroke="var(--color-label-tertiary)"
              tick={{ fontFamily: "var(--font-mono)", fontSize: 10.5 }}
              tickLine={false}
              axisLine={false}
              width={36}
            />
            <Tooltip
              cursor={{ stroke: "var(--color-cocoa)", strokeOpacity: 0.4, strokeWidth: 1 }}
              content={({ active, payload, label }) => {
                if (!active || !payload || !payload.length) return null;
                const v = Number(payload[0]?.value ?? 0);
                return (
                  <div
                    className="rounded-xl border border-hairline-strong bg-cream px-3.5 py-2.5 shadow-[0_12px_28px_-16px_rgb(61_41_27_/_0.20)]"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    <p className="text-[10px] uppercase tracking-[0.16em] text-label-tertiary">
                      {fmtAbsoluteDate(new Date(String(label)))}
                    </p>
                    <p className="mt-1 text-[13px] tabular-nums text-ink">
                      Vitality <span className="text-cocoa">{v.toFixed(1)}</span>
                    </p>
                  </div>
                );
              }}
            />
            <Area
              type="monotone"
              dataKey="vitality"
              stroke="var(--color-cocoa)"
              strokeWidth={1.6}
              fill="url(#vitFill)"
              activeDot={{ r: 3.2, stroke: "var(--color-cream)", strokeWidth: 1.5 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <ul className="mt-6 grid grid-cols-2 gap-x-6 gap-y-2 font-mono text-[11px] uppercase tracking-[0.14em] text-label-secondary md:grid-cols-4">
        <li className="flex items-center gap-2">
          <span className="h-2 w-3 rounded-sm bg-risk-low" /> Low (≥ 80)
        </li>
        <li className="flex items-center gap-2">
          <span className="h-2 w-3 rounded-sm bg-risk-moderate" /> Moderate (65–79)
        </li>
        <li className="flex items-center gap-2">
          <span className="h-2 w-3 rounded-sm bg-risk-elevated" /> Elevated (50–64)
        </li>
        <li className="flex items-center gap-2">
          <span className="h-2 w-3 rounded-sm bg-risk-high" /> High (&lt; 50)
        </li>
      </ul>
    </Card>
  );
}
