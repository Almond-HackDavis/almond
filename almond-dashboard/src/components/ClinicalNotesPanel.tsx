import { Card, CardEyebrow, CardKicker, CardTitle } from "@/components/Card";
import type { OutputDocument } from "@/lib/api";
import { CLINICAL_NOTES, PATIENT } from "@/lib/fixtures";
import { fmtAbsoluteDate } from "@/lib/format";

interface NotesProps {
  latest: OutputDocument;
}

export function ClinicalNotesPanel({ latest }: NotesProps) {
  const meta = latest.model_metadata;
  return (
    <Card className="p-7 lg:p-8">
      <div className="grid grid-cols-12 gap-x-10 gap-y-8">
        <div className="col-span-12 lg:col-span-7">
          <CardEyebrow>Latest Synthesis · Gemma narrative</CardEyebrow>
          <CardTitle className="mt-3">
            Model synthesis · <span className="italic text-cocoa">{PATIENT.preferred_name}</span>
          </CardTitle>
          <p
            className="mt-6 font-display text-[20px] leading-[1.55] text-ink"
            style={{ fontVariationSettings: "'opsz' 96, 'SOFT' 70" }}
          >
            <span className="text-cocoa">&ldquo;</span>
            {latest.gemma_summary}
            <span className="text-cocoa">&rdquo;</span>
          </p>
          <p className="mt-5 font-mono text-[10.5px] uppercase tracking-[0.18em] text-label-tertiary">
            {meta.llm_model} · prompt {meta.prompt_template_version} · {meta.horizon_months}-mo horizon
          </p>
        </div>

        <div className="col-span-12 lg:col-span-5 lg:border-l lg:border-hairline lg:pl-8">
          <CardEyebrow>Clinician Timeline</CardEyebrow>
          <CardTitle className="mt-3">Recent notes</CardTitle>
          <CardKicker className="mt-2">
            Manually-entered observations from the care team. Replace with
            scribe / EHR sync once approved.
          </CardKicker>
          <ol className="mt-5 space-y-5 border-l border-hairline pl-5">
            {CLINICAL_NOTES.map((n, idx) => (
              <li key={n.ts} className="relative">
                <span className="absolute -left-[27px] top-1.5 h-2 w-2 rounded-full bg-cocoa" />
                <div className="flex items-baseline justify-between gap-3">
                  <p className="text-[13px] font-medium text-ink">{n.author}</p>
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-label-tertiary">
                    {fmtAbsoluteDate(new Date(n.ts))}
                  </p>
                </div>
                <p className="mt-0.5 font-mono text-[10.5px] uppercase tracking-[0.16em] text-label-tertiary">
                  {n.role}
                </p>
                <p className="mt-2 text-[13.5px] leading-relaxed text-label-secondary">
                  {n.body}
                </p>
                {idx === 0 && (
                  <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-cream-tint px-2 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.16em] text-cocoa">
                    Most recent
                  </span>
                )}
              </li>
            ))}
          </ol>
        </div>
      </div>
    </Card>
  );
}
