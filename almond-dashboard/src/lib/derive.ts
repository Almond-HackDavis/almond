/** Projections from raw API payloads to the shapes the dashboard renders.
 *
 * The API returns history newest-first; charts want chronological order.
 * These helpers handle the reversal and the per-equation extraction.
 */

import type { OutputDocument } from "@/lib/api";

export interface VitalityPoint {
  date: string;
  computed_at: string;
  vitality: number;
  raw_2yr: number;
  fitness_age: number | null;
  le8: number | null;
}

/** Convert API history (newest-first) to a chronological vitality timeline. */
export function vitalityTimeline(history: OutputDocument[]): VitalityPoint[] {
  return history
    .slice()
    .reverse()
    .map((row) => ({
      date: row.computed_at.slice(0, 10),
      computed_at: row.computed_at,
      vitality: row.scores.vitality_score?.value ?? 0,
      raw_2yr: row.scores.nhanes_mortality_2yr?.value ?? 0,
      fitness_age: row.scores.fitness_age?.value ?? null,
      le8: row.scores.le8?.value ?? null,
    }));
}

/** 90-point trend for an equation key across history (chronological). */
export function equationTrend(
  history: OutputDocument[],
  key: "ascvd_10yr" | "framingham_10yr" | "findrisc_10yr" | "le8",
): number[] {
  const ordered = history.slice().reverse();
  const out: number[] = [];
  for (const row of ordered) {
    const entry = row.scores[key as keyof typeof row.scores];
    if (entry && typeof (entry as { value: unknown }).value === "number") {
      out.push((entry as { value: number }).value);
    }
  }
  return out;
}

/** Best-effort 30-point trend for a driver feature across history.
 *  Pulls the driver's `value` from each row's top_drivers list whenever
 *  the feature appears. Sparse — drivers rotate as patient inputs shift —
 *  but we always have the latest 30 if the feature was the headliner.
 */
export function driverTrend(
  history: OutputDocument[],
  feature: string,
  limit = 30,
): number[] {
  const ordered = history.slice().reverse();
  const out: number[] = [];
  for (const row of ordered) {
    const driver = row.top_drivers.find((d) => d.feature === feature);
    if (driver) out.push(driver.value);
  }
  return out.slice(-limit);
}

export interface VitalityStats {
  current: number;
  previous: number; // ~7 days back, falls back to first available row
  delta: number;
  series: number[];
}

export function vitalityStats(history: OutputDocument[]): VitalityStats | null {
  if (history.length === 0) return null;
  const ordered = history.slice().reverse();
  const series = ordered.map((r) => r.scores.vitality_score?.value ?? 0);
  const current = series[series.length - 1];
  const lookbackIdx = Math.max(0, series.length - 8);
  const previous = series[lookbackIdx];
  return { current, previous, delta: current - previous, series };
}
