/** Typed client for the Almond FastAPI backend.
 *
 * All fetches happen on the server (Next.js Route Handlers / Server
 * Components). The dashboard never reaches MongoDB directly — it goes
 * through the same `GET /output` and `GET /history` endpoints iOS uses.
 *
 * `cache: "no-store"` keeps the dashboard live; a clinician hitting
 * refresh sees the most recent `POST /input` even if it landed seconds
 * ago. Trade-off: no CDN caching. For an MVP single-user dashboard
 * that's the right call.
 */

import { cache } from "react";

const DEFAULT_BASE = "http://localhost:8000";

function baseUrl(): string {
  return process.env.ALMOND_API_BASE_URL?.replace(/\/+$/, "") ?? DEFAULT_BASE;
}

// ── Wire types — kept loose intentionally so backend can add fields without
// breaking the dashboard. Server's source of truth is almond-ml/schemas.py.

export interface ScoreScalar {
  value: number;
  max?: number;
  ci_low?: number | null;
  ci_high?: number | null;
}

export interface FitnessAge {
  value: number;
  chronological_age: number;
  delta: number;
}

export interface ASCVDScore {
  value: number;
  horizon_months: number;
  applicable: boolean;
}

export interface FINDRISCScore extends ASCVDScore {
  score: number;
  mode: "full" | "partial";
  missing: string[];
  coverage: number;
}

export interface LE8Score {
  value: number;
  max: number;
  mode: string;
  n_scoreable: number;
  coverage: number;
  applicable: boolean;
}

export interface ScoresBlock {
  vitality_score: ScoreScalar;
  nhanes_mortality_2yr: ScoreScalar;
  fitness_age?: FitnessAge;
  ascvd_10yr?: ASCVDScore;
  framingham_10yr?: ASCVDScore;
  findrisc_10yr?: FINDRISCScore;
  le8?: LE8Score;
}

export interface TopDriver {
  feature: string;
  human_label: string;
  value: number;
  contribution_pts: number;
  direction: "better" | "worse";
}

export interface ModelMetadata {
  model_id: string;
  prompt_template_version: string;
  llm_model: string;
  horizon_months: number;
}

export interface OutputDocument {
  _id: string;
  computed_at: string;
  input_uploaded_at: string;
  input_id?: string | null;
  scores: ScoresBlock;
  top_drivers: TopDriver[];
  gemma_summary: string;
  disclaimer: string;
  model_metadata: ModelMetadata;
}

export interface ApiError {
  error: { code: string; message: string; details?: unknown };
}

// ── Fetchers ──────────────────────────────────────────────────────────────

/** GET /output — most recent prediction. Returns null when no rows yet. */
export const getLatestOutput = cache(
  async (): Promise<OutputDocument | null> => {
    const res = await fetch(`${baseUrl()}/output`, { cache: "no-store" });
    if (res.status === 404) return null;
    if (!res.ok) {
      throw new Error(
        `GET /output failed: ${res.status} ${res.statusText} :: ${await res.text()}`,
      );
    }
    return (await res.json()) as OutputDocument;
  },
);

/** GET /history?limit=N — N most recent outputs, newest-first. */
export const getHistory = cache(
  async (limit = 90): Promise<OutputDocument[]> => {
    const res = await fetch(`${baseUrl()}/history?limit=${limit}`, {
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error(
        `GET /history failed: ${res.status} ${res.statusText} :: ${await res.text()}`,
      );
    }
    return (await res.json()) as OutputDocument[];
  },
);

/** Convenience: shape the dashboard expects. */
export interface DashboardData {
  latest: OutputDocument | null;
  history: OutputDocument[];
}

export const getDashboardData = cache(async (): Promise<DashboardData> => {
  const [latest, history] = await Promise.all([
    getLatestOutput(),
    getHistory(90),
  ]);
  return { latest, history };
});
