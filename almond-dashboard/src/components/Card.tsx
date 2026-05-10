import { cn } from "@/lib/cn";
import { type HTMLAttributes } from "react";

/** Card surface — paper-white with a hairline cocoa-tinted border. */
export function Card({
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "relative rounded-2xl border border-hairline bg-surface-card",
        "shadow-[0_1px_0_rgb(61_41_27_/_0.04),0_8px_24px_-12px_rgb(61_41_27_/_0.08)]",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardEyebrow({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "text-[10.5px] font-mono font-medium uppercase tracking-[0.18em] text-label-secondary",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardTitle({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <h2 className={cn("font-display text-[22px] leading-tight text-ink", className)}>
      {children}
    </h2>
  );
}

export function CardKicker({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p className={cn("text-[13px] leading-relaxed text-label-secondary", className)}>
      {children}
    </p>
  );
}
