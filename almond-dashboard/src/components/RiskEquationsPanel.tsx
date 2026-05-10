import { Card, CardEyebrow, CardKicker, CardTitle } from "@/components/Card";
import { Sparkline } from "@/components/Sparkline";
import type { OutputDocument, ScoresBlock } from "@/lib/api";
import { equationTrend } from "@/lib/derive";
import { fmtPercent } from "@/lib/format";
import { cn } from "@/lib/cn";

interface EqMeta {
  key: "ascvd_10yr" | "framingham_10yr" | "findrisc_10yr" | "le8";
  label: string;
  long_label: string;
  citation: string;
  horizon_label: string;
  display: "percent" | "score_0_100";
}

const EQUATIONS: EqMeta[] = [
  {
    key: "ascvd_10yr",
    label: "ASCVD",
    long_label: "10-yr hard ASCVD risk",
    citation: "Goff 2013 · ACC/AHA Pooled Cohort Equations",
    horizon_label: "10 years",
    display: "percent",
  },
  {
    key: "framingham_10yr",
    label: "Framingham",
    long_label: "10-yr broader CVD risk",
    citation: "D\u2019Agostino 2008 · General CVD Profile",
    horizon_label: "10 years",
    display: "percent",
  },
  {
    key: "findrisc_10yr",
    label: "FINDRISC",
    long_label: "10-yr type-2 diabetes risk",
    citation: "Lindstr\u00f6m 2003 · partial mode (no waist)",
    horizon_label: "10 years",
    display: "percent",
  },
  {
    key: "le8",
    label: "LE8",
    long_label: "Cardiovascular health composite",
    citation: "Lloyd-Jones 2022 · AHA Life\u2019s Essential 8",
    horizon_label: "current",
    display: "score_0_100",
  },
];

interface RiskEquationsProps {
  latest: OutputDocument;
  history: OutputDocument[];
}

function readEquation(scores: ScoresBlock, key: EqMeta["key"]) {
  switch (key) {
    case "ascvd_10yr":
      return scores.ascvd_10yr;
    case "framingham_10yr":
      return scores.framingham_10yr;
    case "findrisc_10yr":
      return scores.findrisc_10yr;
    case "le8":
      return scores.le8;
  }
}

export function RiskEquationsPanel({ latest, history }: RiskEquationsProps) {
  return (
    <Card className="p-7 lg:p-8">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <CardEyebrow>Clinical Equations · Latest</CardEyebrow>
          <CardTitle className="mt-3">Validated risk panel</CardTitle>
        </div>
        <CardKicker className="hidden max-w-[44ch] text-right md:block">
          Computed from the same input snapshot every time the patient syncs.
          Equations outside their published applicability range are marked
          inactive and contribute zero to vitality.
        </CardKicker>
      </div>

      <div className="mt-7 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {EQUATIONS.map((eq) => {
          const entry = readEquation(latest.scores, eq.key);
          const present = entry !== undefined;
          const applicable = present && entry!.applicable !== false;
          const value = entry?.value;
          const trend = equationTrend(history, eq.key);

          const display =
            value === undefined
              ? "—"
              : eq.display === "percent"
                ? fmtPercent(value, 1)
                : `${value.toFixed(1)} / 100`;

          return (
            <article
              key={eq.key}
              className={cn(
                "group relative rounded-xl border border-hairline bg-cream/60 p-5",
                "transition-colors duration-300 hover:bg-cream-tint",
                !applicable && "opacity-60",
              )}
            >
              <header className="flex items-baseline justify-between gap-2">
                <span className="font-mono text-[10.5px] uppercase tracking-[0.2em] text-cocoa">
                  {eq.label}
                </span>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.16em]",
                    !present
                      ? "bg-cream-tint text-label-tertiary"
                      : applicable
                        ? "bg-risk-low-surface text-risk-low"
                        : "bg-cream-tint text-label-tertiary",
                  )}
                >
                  {!present ? "Not computed" : applicable ? "Active" : "Inactive"}
                </span>
              </header>
              <p
                className="mt-4 font-display tabular-nums leading-none text-ink"
                style={{ fontSize: "44px", fontVariationSettings: "'opsz' 96" }}
              >
                {display}
              </p>
              <p className="mt-2 text-[12.5px] leading-snug text-label-secondary">
                {eq.long_label}
              </p>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.16em] text-label-tertiary">
                {eq.horizon_label}
              </p>
              <div className="mt-4 -mb-1">
                {trend.length >= 2 ? (
                  <Sparkline
                    data={trend}
                    width={220}
                    height={26}
                    stroke="var(--color-cocoa)"
                    fill="var(--color-cocoa)"
                    className="w-full opacity-90"
                  />
                ) : (
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-label-tertiary">
                    Trend builds with history
                  </span>
                )}
              </div>
              <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-label-tertiary">
                {eq.citation}
              </p>
            </article>
          );
        })}
      </div>
    </Card>
  );
}
