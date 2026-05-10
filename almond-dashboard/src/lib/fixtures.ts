/** Synthetic 90-day patient timeline.
 *
 * All values are deterministic — fixed seed, no randomness on render —
 * so the dashboard renders identically server-side and client-side.
 *
 * Replace with the real `GET /history` payload once that endpoint lands.
 */

export interface VitalityPoint {
  date: string;        // YYYY-MM-DD
  vitality: number;    // 0–100
  raw_2yr: number;     // 0–1 probability
  fitness_age: number; // years
  le8: number;         // 0–100
}

export interface Driver {
  feature:
    | "activity"
    | "rhr"
    | "hrv"
    | "vo2"
    | "walking_hr"
    | "ascvd"
    | "framingham"
    | "findrisc"
    | "le8";
  human_label: string;
  value: number;
  unit: string;
  contribution_pts: number;
  direction: "better" | "worse";
  trend_30d: number[];
}

export interface Patient {
  full_name: string;
  preferred_name: string;
  pronouns: string;
  date_of_birth: string;
  age: number;
  sex: "M" | "F";
  mrn: string;
  primary_clinician: string;
  enrolled_at: string;
}

export interface RiskEquation {
  key: "ascvd" | "framingham" | "findrisc" | "le8";
  label: string;
  long_label: string;
  citation: string;
  value: number;            // raw equation output (probability or score)
  display: "percent" | "score_0_100";
  horizon_label: string;
  applicable: boolean;
  trend_90d: number[];
}

export interface ClinicalNote {
  ts: string;                 // ISO
  author: string;
  role: string;
  body: string;
}

// ── Deterministic synthesis ────────────────────────────────────────────────

/** xmu-shift PRNG seeded for repeatability. */
function seeded(seed: number) {
  let s = seed >>> 0;
  return () => {
    s ^= s << 13;
    s ^= s >>> 17;
    s ^= s << 5;
    return ((s >>> 0) % 1_000_000) / 1_000_000;
  };
}

function buildTimeline(): VitalityPoint[] {
  const rand = seeded(0xa12d0e);
  const out: VitalityPoint[] = [];
  // Anchor end-date to a fixed value so SSR == CSR.
  const end = new Date("2026-05-08T00:00:00Z");
  const baseVit = 73;
  const drift = 6; // gentle climb across 90 d
  for (let i = 89; i >= 0; i--) {
    const d = new Date(end.getTime() - i * 86_400_000);
    const t = (89 - i) / 89;
    const seasonal = Math.sin(t * Math.PI * 1.7) * 2.6;
    const noise = (rand() - 0.5) * 4.2;
    const vitality = Math.max(0, Math.min(100, baseVit + drift * t + seasonal + noise));

    // raw 2-yr risk is loosely inverse-correlated with vitality
    const raw_2yr = Math.max(0.0006, Math.min(0.04, 0.0050 - 0.00003 * vitality + (rand() - 0.5) * 0.0008));

    const fitness_age = Math.round((35 - 12 * t + (rand() - 0.5) * 1.2) * 10) / 10;
    const le8 = Math.max(50, Math.min(98, 70 + 18 * t + (rand() - 0.5) * 4));

    out.push({
      date: d.toISOString().slice(0, 10),
      vitality: Math.round(vitality * 10) / 10,
      raw_2yr: Math.round(raw_2yr * 10000) / 10000,
      fitness_age,
      le8: Math.round(le8 * 10) / 10,
    });
  }
  return out;
}

function trend(seed: number, base: number, amp: number, len = 30): number[] {
  const r = seeded(seed);
  return Array.from({ length: len }, (_, i) => {
    const t = i / (len - 1);
    return Math.round((base + amp * Math.sin(t * Math.PI * 1.5) + (r() - 0.5) * amp * 0.7) * 100) / 100;
  });
}

export const TIMELINE: VitalityPoint[] = buildTimeline();
export const LATEST: VitalityPoint = TIMELINE[TIMELINE.length - 1];
export const PRIOR: VitalityPoint = TIMELINE[TIMELINE.length - 8] ?? LATEST;

export const DRIVERS: Driver[] = [
  {
    feature: "activity",
    human_label: "Daily activity",
    value: 4_583_750,
    unit: "MIMS",
    contribution_pts: 2.38,
    direction: "better",
    trend_30d: trend(101, 4_400_000, 350_000, 30),
  },
  {
    feature: "le8",
    human_label: "Cardiovascular health (LE8)",
    value: 88.4,
    unit: "/ 100",
    contribution_pts: 1.94,
    direction: "better",
    trend_30d: trend(102, 86, 4, 30),
  },
  {
    feature: "hrv",
    human_label: "Heart-rate variability",
    value: 62,
    unit: "ms SDNN",
    contribution_pts: 1.29,
    direction: "better",
    trend_30d: trend(103, 60, 6, 30),
  },
  {
    feature: "vo2",
    human_label: "Cardiorespiratory fitness (VO\u2082 max)",
    value: 44.2,
    unit: "mL/kg/min",
    contribution_pts: 1.05,
    direction: "better",
    trend_30d: trend(104, 43, 1.6, 30),
  },
  {
    feature: "rhr",
    human_label: "Resting heart rate",
    value: 58,
    unit: "bpm",
    contribution_pts: 0.74,
    direction: "better",
    trend_30d: trend(105, 59, 2.5, 30),
  },
  {
    feature: "walking_hr",
    human_label: "Walking heart rate",
    value: 102,
    unit: "bpm",
    contribution_pts: -0.18,
    direction: "worse",
    trend_30d: trend(106, 103, 4, 30),
  },
];

export const PATIENT: Patient = {
  full_name: "Jane M. Doe",
  preferred_name: "Jane",
  pronouns: "she / her",
  date_of_birth: "1991-03-14",
  age: 35,
  sex: "F",
  mrn: "AL-2026-00148",
  primary_clinician: "Dr. R. Chen, MD",
  enrolled_at: "2026-02-08",
};

export const RISK_EQUATIONS: RiskEquation[] = [
  {
    key: "ascvd",
    label: "ASCVD",
    long_label: "10-yr hard ASCVD risk",
    citation: "Goff 2013 \u00b7 ACC/AHA Pooled Cohort Equations",
    value: 0.018,
    display: "percent",
    horizon_label: "10 years",
    applicable: true,
    trend_90d: trend(201, 0.020, 0.003, 90),
  },
  {
    key: "framingham",
    label: "Framingham",
    long_label: "10-yr broader CVD risk",
    citation: "D\u2019Agostino 2008 \u00b7 General CVD Profile",
    value: 0.041,
    display: "percent",
    horizon_label: "10 years",
    applicable: true,
    trend_90d: trend(202, 0.045, 0.005, 90),
  },
  {
    key: "findrisc",
    label: "FINDRISC",
    long_label: "10-yr type-2 diabetes risk",
    citation: "Lindstr\u00f6m 2003 \u00b7 partial mode (no waist)",
    value: 0.04,
    display: "percent",
    horizon_label: "10 years",
    applicable: false,
    trend_90d: trend(203, 0.04, 0.003, 90),
  },
  {
    key: "le8",
    label: "LE8",
    long_label: "Cardiovascular health composite",
    citation: "Lloyd-Jones 2022 \u00b7 AHA Life\u2019s Essential 8",
    value: 88.4,
    display: "score_0_100",
    horizon_label: "current",
    applicable: true,
    trend_90d: trend(204, 86, 4, 90),
  },
];

export const GEMMA_SUMMARY: string =
  "Jane\u2019s vitality has trended up roughly six points across the past 90 days, with the cleanest gains attributable to a sustained climb in cardiorespiratory fitness and tighter sleep regularity. Her LE8 score is now firmly in the high band, and her resting heart rate has settled around 58 bpm \u2014 unusual for her chronological age and consistent with the trajectory we\u2019d expect from a structured aerobic program. The only mild headwind is a slightly elevated walking heart rate, which usually responds to a four-week deload, not a clinical intervention.";

export const CLINICAL_NOTES: ClinicalNote[] = [
  {
    ts: "2026-05-08T18:42:00Z",
    author: "Dr. R. Chen",
    role: "Primary clinician",
    body:
      "Telemetry continues to corroborate the lifestyle plan from March. Discussed walking-HR drift; agreed to revisit at the 6-week follow-up. No new lab orders.",
  },
  {
    ts: "2026-04-22T15:08:00Z",
    author: "Dr. R. Chen",
    role: "Primary clinician",
    body:
      "Vitality crossed the 75-point threshold for the first time since enrollment. Patient self-reports better sleep quality. Maintain current plan.",
  },
  {
    ts: "2026-03-04T09:14:00Z",
    author: "M. Patel, RN",
    role: "Care navigator",
    body:
      "Onboarded patient to passive HealthKit upload. Verified Apple Watch fit + sleep-mode permission. Baseline labs filed.",
  },
];
