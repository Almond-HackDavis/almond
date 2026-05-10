import { Wordmark } from "@/components/Wordmark";
import { PATIENT } from "@/lib/fixtures";
import { fmtAbsoluteDate, fmtRelativeDate } from "@/lib/format";

/** Top chrome — wordmark left, patient identifier center, sync state right. */
export function SiteHeader({ lastSync }: { lastSync: Date }) {
  return (
    <header className="sticky top-0 z-30 border-b border-hairline bg-cream/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between gap-8 px-8 lg:px-12">
        <div className="flex items-center gap-3">
          <Wordmark height={22} />
          <span className="hidden h-4 w-px bg-hairline-strong sm:block" />
          <span className="hidden font-mono text-[11px] uppercase tracking-[0.2em] text-label-secondary sm:block">
            Patient Dossier
          </span>
        </div>

        <div className="hidden flex-col items-center md:flex">
          <p className="font-display text-[15px] leading-tight text-ink">
            {PATIENT.full_name}
          </p>
          <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-label-tertiary">
            MRN {PATIENT.mrn} · {PATIENT.age} {PATIENT.sex} · {PATIENT.pronouns}
          </p>
        </div>

        <div className="flex items-center gap-3 text-right">
          <div className="hidden flex-col items-end sm:flex">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-label-tertiary">
              Last sync
            </p>
            <p className="font-mono text-[12.5px] tabular-nums text-ink">
              {fmtRelativeDate(lastSync)}
              <span className="ml-1.5 text-label-tertiary">· {fmtAbsoluteDate(lastSync)}</span>
            </p>
          </div>
          <span className="relative inline-flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sage opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-sage" />
          </span>
        </div>
      </div>
    </header>
  );
}
