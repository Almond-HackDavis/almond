import { ClinicalNotesPanel } from "@/components/ClinicalNotesPanel";
import { HeroVitality } from "@/components/HeroVitality";
import { RiskEquationsPanel } from "@/components/RiskEquationsPanel";
import { SiteHeader } from "@/components/SiteHeader";
import { TopDriversPanel } from "@/components/TopDriversPanel";
import { VitalityTimeline } from "@/components/VitalityTimeline";
import { Card, CardEyebrow, CardKicker, CardTitle } from "@/components/Card";
import { getDashboardData } from "@/lib/api";
import { vitalityTimeline } from "@/lib/derive";
import { PATIENT } from "@/lib/patient";
import { fmtAbsoluteDate } from "@/lib/format";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function Page() {
  let dashboard;
  try {
    dashboard = await getDashboardData();
  } catch (err) {
    return <FailureState message={(err as Error).message} />;
  }

  const { latest, history } = dashboard;

  if (!latest) {
    return (
      <div>
        <SiteHeader lastSync={null} />
        <EmptyState />
      </div>
    );
  }

  const lastSync = new Date(latest.computed_at);
  const timeline = vitalityTimeline(history);

  return (
    <div>
      <SiteHeader lastSync={lastSync} />
      <main className="mx-auto max-w-[1280px] px-8 pb-24 lg:px-12">
        <div className="flex flex-col gap-2 border-b border-hairline pt-10 pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-label-tertiary">
              Continuous monitoring · {history.length}-snapshot window
            </p>
            <h1
              className="mt-3 font-display text-[40px] leading-[1.05] tracking-[-0.01em] text-ink md:text-[52px]"
              style={{ fontVariationSettings: "'opsz' 144, 'SOFT' 60" }}
            >
              {PATIENT.preferred_name}&rsquo;s health, at a glance
            </h1>
            <p className="mt-3 max-w-[58ch] text-[15px] leading-relaxed text-label-secondary">
              A synthesized view across NHANES-trained survival modeling,
              ACC/AHA-validated risk equations, and the live wearable
              telemetry uploaded from {PATIENT.preferred_name}&rsquo;s Apple Watch.
              Every figure on this page is sourced from the most recent
              sync at <span className="font-mono text-ink">{fmtAbsoluteDate(lastSync)}</span>.
            </p>
          </div>
          <aside className="grid grid-cols-1 gap-y-2 text-[12.5px] leading-snug">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-label-tertiary">
                Patient
              </p>
              <p className="mt-1 text-ink">{PATIENT.full_name}</p>
            </div>
          </aside>
        </div>

        <HeroVitality latest={latest} history={history} />

        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12">
            {timeline.length >= 2 ? (
              <VitalityTimeline data={timeline} />
            ) : (
              <PendingTimelineCard count={timeline.length} />
            )}
          </div>

          <div className="col-span-12 xl:col-span-7">
            <TopDriversPanel latest={latest} history={history} />
          </div>
          <div className="col-span-12 xl:col-span-5">
            <ClinicalNotesPanel latest={latest} />
          </div>

          <div className="col-span-12">
            <RiskEquationsPanel latest={latest} history={history} />
          </div>
        </div>

        <footer className="mt-16 flex flex-col items-start gap-2 border-t border-hairline pt-6 text-label-tertiary md:flex-row md:items-center md:justify-between">
          <p className="font-mono text-[10.5px] uppercase tracking-[0.18em]">
            Almond · Patient Dossier · For clinician review only
          </p>
          <p className="text-[12px] leading-snug">
            {latest.disclaimer}
          </p>
        </footer>
      </main>
    </div>
  );
}

function PendingTimelineCard({ count }: { count: number }) {
  return (
    <Card className="p-12 lg:p-16 text-center">
      <CardEyebrow>Vitality Timeline · Awaiting history</CardEyebrow>
      <CardTitle className="mt-3">Trend builds with each sync</CardTitle>
      <CardKicker className="mt-3 mx-auto max-w-[44ch]">
        We have {count === 0 ? "no" : `only ${count}`} prior snapshot{count === 1 ? "" : "s"}
        {" "}so far. After the next telemetry upload, this panel will draw the
        full vitality arc with risk-band reference zones.
      </CardKicker>
    </Card>
  );
}

function EmptyState() {
  return (
    <main className="mx-auto flex min-h-[80vh] max-w-[760px] flex-col items-center justify-center px-8 text-center">
      <p className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-label-tertiary">
        Almond · Patient Dossier
      </p>
      <h1
        className="mt-4 font-display text-[44px] leading-[1.05] text-ink"
        style={{ fontVariationSettings: "'opsz' 144, 'SOFT' 60" }}
      >
        No telemetry yet
      </h1>
      <p className="mt-4 max-w-[52ch] text-[15px] leading-relaxed text-label-secondary">
        {PATIENT.full_name} hasn&rsquo;t synchronized any HealthKit data
        through the iOS app. As soon as the first
        {" "}<span className="font-mono">POST /input</span> lands, this
        dashboard will populate with the current vitality score, validated
        risk panel, and the model synthesis.
      </p>
    </main>
  );
}

function FailureState({ message }: { message: string }) {
  return (
    <main className="mx-auto flex min-h-[80vh] max-w-[760px] flex-col items-center justify-center px-8 text-center">
      <p className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-risk-high">
        Almond · API unreachable
      </p>
      <h1
        className="mt-4 font-display text-[40px] leading-[1.05] text-ink"
        style={{ fontVariationSettings: "'opsz' 144, 'SOFT' 60" }}
      >
        Cannot reach the inference service
      </h1>
      <p className="mt-4 max-w-[60ch] text-[14px] leading-relaxed text-label-secondary">
        Verify the FastAPI server is running and that
        {" "}<span className="font-mono">ALMOND_API_BASE_URL</span> resolves
        to it. The dashboard talks to the API; it never reads MongoDB
        directly.
      </p>
      <pre className="mt-6 max-w-full overflow-auto rounded-lg border border-hairline bg-cream-tint px-4 py-3 text-left font-mono text-[11px] text-label-secondary">
        {message}
      </pre>
    </main>
  );
}
