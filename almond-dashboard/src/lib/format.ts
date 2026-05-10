/** Display formatters used across the dashboard. */

export function fmtNumber(n: number, fractionDigits = 0): string {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(n);
}

export function fmtPercent(n: number, fractionDigits = 1): string {
  return `${(n * 100).toFixed(fractionDigits)}%`;
}

export function fmtDelta(n: number, fractionDigits = 1, suffix = ""): string {
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  const abs = Math.abs(n);
  return `${sign}${abs.toFixed(fractionDigits)}${suffix}`;
}

export function fmtRelativeDate(d: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.round(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hr ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 7) return `${diffDay} d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function fmtAbsoluteDate(d: Date): string {
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export type RiskBand = "low" | "moderate" | "elevated" | "high";

export function vitalityBand(v: number): RiskBand {
  if (v >= 80) return "low";
  if (v >= 65) return "moderate";
  if (v >= 50) return "elevated";
  return "high";
}

export const RISK_BAND_LABELS: Record<RiskBand, string> = {
  low: "Low risk",
  moderate: "Moderate risk",
  elevated: "Elevated risk",
  high: "High risk",
};

export const RISK_BAND_FG: Record<RiskBand, string> = {
  low: "text-risk-low",
  moderate: "text-risk-moderate",
  elevated: "text-risk-elevated",
  high: "text-risk-high",
};

export const RISK_BAND_BG: Record<RiskBand, string> = {
  low: "bg-risk-low-surface",
  moderate: "bg-risk-moderate-surface",
  elevated: "bg-risk-elevated-surface",
  high: "bg-risk-high-surface",
};
