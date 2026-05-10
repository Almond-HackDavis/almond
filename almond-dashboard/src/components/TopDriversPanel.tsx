import { Card, CardEyebrow, CardKicker, CardTitle } from "@/components/Card";
import { Sparkline } from "@/components/Sparkline";
import type { OutputDocument, TopDriver } from "@/lib/api";
import { driverTrend } from "@/lib/derive";
import { fmtDelta, fmtNumber } from "@/lib/format";
import { cn } from "@/lib/cn";

function formatValue(d: TopDriver): string {
  switch (d.feature) {
    case "activity":
      return `${(d.value / 1_000_000).toFixed(2)} M MIMS`;
    case "le8":
      return `${d.value.toFixed(1)} / 100`;
    case "vo2":
      return `${d.value.toFixed(1)} mL/kg/min`;
    case "rhr":
      return `${fmtNumber(d.value, 0)} bpm`;
    case "walking_hr":
      return `${fmtNumber(d.value, 0)} bpm`;
    case "hrv":
      return `${fmtNumber(d.value, 0)} ms SDNN`;
    case "ascvd":
    case "framingham":
    case "findrisc":
      return `${(d.value * 100).toFixed(1)}%`;
    default:
      return fmtNumber(d.value, 0);
  }
}

interface TopDriversProps {
  latest: OutputDocument;
  history: OutputDocument[];
}

export function TopDriversPanel({ latest, history }: TopDriversProps) {
  const drivers = latest.top_drivers ?? [];
  const max = drivers.length
    ? Math.max(...drivers.map((d) => Math.abs(d.contribution_pts)))
    : 1;

  return (
    <Card className="p-7 lg:p-8">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <CardEyebrow>Top Drivers · This snapshot</CardEyebrow>
          <CardTitle className="mt-3">What is moving the score</CardTitle>
        </div>
        <CardKicker className="hidden max-w-[42ch] text-right md:block">
          Signed contribution in vitality points. Negative drivers are the most
          actionable items in conversation.
        </CardKicker>
      </div>

      {drivers.length === 0 ? (
        <p className="mt-8 text-[14px] text-label-secondary">
          No driver attribution available for the latest snapshot.
        </p>
      ) : (
        <ul className="mt-7 divide-y divide-hairline">
          {drivers.map((d) => {
            const positive = d.direction === "better";
            const widthPct = (Math.abs(d.contribution_pts) / max) * 100;
            const trend = driverTrend(history, d.feature, 30);
            return (
              <li
                key={d.feature}
                className="grid grid-cols-12 items-center gap-x-4 py-4 first:pt-0 last:pb-0"
              >
                <div className="col-span-5 md:col-span-4">
                  <p className="text-[14px] font-medium text-ink">{d.human_label}</p>
                  <p className="mt-0.5 font-mono text-[11px] tabular-nums text-label-tertiary">
                    {formatValue(d)}
                  </p>
                </div>

                <div className="col-span-3 md:col-span-3">
                  {trend.length >= 2 ? (
                    <Sparkline
                      data={trend}
                      width={140}
                      height={24}
                      stroke={positive ? "var(--color-sage)" : "var(--color-coral)"}
                      fill={positive ? "var(--color-sage)" : "var(--color-coral)"}
                      className="opacity-90"
                    />
                  ) : (
                    <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-label-tertiary">
                      Trend pending
                    </span>
                  )}
                </div>

                <div className="col-span-4 md:col-span-5">
                  <div className="flex items-center justify-end gap-3">
                    <div
                      className={cn(
                        "relative h-1.5 flex-1 overflow-hidden rounded-full bg-cream-tint",
                        "max-w-[180px]",
                      )}
                    >
                      <div
                        className={cn(
                          "absolute inset-y-0 left-0 rounded-full",
                          positive ? "bg-sage" : "bg-coral",
                        )}
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                    <span
                      className={cn(
                        "min-w-[68px] text-right font-mono text-[12.5px] font-medium tabular-nums",
                        positive ? "text-sage" : "text-coral",
                      )}
                    >
                      {fmtDelta(d.contribution_pts, 2, " pts")}
                    </span>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
