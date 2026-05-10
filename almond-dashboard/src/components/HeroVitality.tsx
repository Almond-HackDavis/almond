import { Sparkline } from "@/components/Sparkline";
import { CardEyebrow } from "@/components/Card";
import type { OutputDocument } from "@/lib/api";
import {
  fmtDelta,
  fmtPercent,
  RISK_BAND_LABELS,
  RISK_BAND_FG,
  RISK_BAND_BG,
  vitalityBand,
} from "@/lib/format";
import { vitalityStats } from "@/lib/derive";

interface HeroProps {
  latest: OutputDocument;
  history: OutputDocument[];
}

export function HeroVitality({ latest, history }: HeroProps) {
  const stats = vitalityStats(history) ?? {
    current: latest.scores.vitality_score?.value ?? 0,
    previous: latest.scores.vitality_score?.value ?? 0,
    delta: 0,
    series: [latest.scores.vitality_score?.value ?? 0],
  };
  const band = vitalityBand(stats.current);
  const raw2yr = latest.scores.nhanes_mortality_2yr?.value ?? 0;
  const fitness = latest.scores.fitness_age;

  return (
    <section className="grid grid-cols-12 items-end gap-x-12 gap-y-8 pt-12 pb-14">
      <div className="col-span-12 lg:col-span-8 rise-in">
        <CardEyebrow>Vitality Score · Latest snapshot</CardEyebrow>
        <div className="mt-5 flex items-end gap-6">
          <span
            className="font-display tabular-nums leading-[0.85] text-ink tracking-[-0.02em]"
            style={{ fontSize: "clamp(96px, 13vw, 168px)", fontVariationSettings: "'opsz' 144" }}
          >
            {stats.current.toFixed(1)}
          </span>
          <div className="mb-3 flex flex-col">
            <span className="font-mono text-[12.5px] uppercase tracking-[0.16em] text-label-tertiary">
              of 100
            </span>
            <span
              className={`mt-1 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.14em] ${RISK_BAND_BG[band]} ${RISK_BAND_FG[band]}`}
            >
              <span
                className={`inline-block h-1.5 w-1.5 rounded-full ${
                  band === "low"
                    ? "bg-risk-low"
                    : band === "moderate"
                      ? "bg-risk-moderate"
                      : band === "elevated"
                        ? "bg-risk-elevated"
                        : "bg-risk-high"
                }`}
              />
              {RISK_BAND_LABELS[band]}
            </span>
          </div>
        </div>
        <p className="mt-5 max-w-[44ch] text-[15px] leading-relaxed text-label-secondary">
          A composite of NHANES-trained 2-yr mortality, ASCVD &amp; Framingham
          10-yr CVD risk, the AHA Life&rsquo;s Essential 8 score, and live
          wearable telemetry. Higher is better; movement of more than three
          points week-on-week typically signals a behavior change worth a
          follow-up note.
        </p>
      </div>

      <div className="col-span-12 lg:col-span-4 lg:pl-6 lg:border-l lg:border-hairline">
        <CardEyebrow>{stats.series.length}-snapshot arc</CardEyebrow>
        <div className="mt-5">
          <Sparkline data={stats.series} width={360} height={88} className="w-full" />
        </div>
        <div className="mt-4 flex items-baseline justify-between font-mono text-[11.5px] tabular-nums">
          <span className="text-label-tertiary">earliest</span>
          <span
            className={`font-medium ${
              stats.delta >= 0 ? "text-risk-low" : "text-risk-elevated"
            }`}
          >
            {fmtDelta(stats.delta, 1, " pts vs. ~1 wk ago")}
          </span>
          <span className="text-label-tertiary">today</span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4 text-[12.5px] leading-snug">
          <div>
            <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-label-tertiary">
              2-yr mortality
            </p>
            <p className="mt-1 font-mono tabular-nums text-ink">
              {fmtPercent(raw2yr, 2)}
            </p>
          </div>
          <div>
            <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-label-tertiary">
              Fitness age
            </p>
            <p className="mt-1 font-mono tabular-nums text-ink">
              {fitness ? `${fitness.value.toFixed(1)} yr` : "—"}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
