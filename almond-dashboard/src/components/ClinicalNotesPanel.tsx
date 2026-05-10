import { Card, CardEyebrow, CardKicker, CardTitle } from "@/components/Card";
import type { OutputDocument } from "@/lib/api";
import { PATIENT } from "@/lib/patient";

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
            Manually-entered observations from the care team.
          </CardKicker>
          <div className="mt-7 rounded-xl border border-dashed border-hairline-strong px-5 py-7 text-center">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-label-tertiary">
              No notes yet
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-label-secondary">
              When a clinician adds the first observation it will land here,
              ordered newest-first.
            </p>
          </div>
        </div>
      </div>
    </Card>
  );
}
