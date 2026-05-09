# almond

Wearable-driven long-term health-risk app for HackDavis 2026.

The user wears their Apple Watch normally, completes a 30-second onboarding form once, and the app continuously computes long-term risk scores (10-year cardiovascular event risk, 10-year diabetes risk, fitness age, AHA Life's Essential 8, NHANES-trained mortality risk) using HealthKit data. A trained ML model plus published clinical risk equations produce the scores; Gemini turns the score breakdown into specific, personalized lifestyle recommendations.

## Repo layout

- `almond-app/` — SwiftUI iPhone app (iOS Engineer's territory)
- `almond-ml/` — FastAPI service + ML model + Gemini integration (Deniz's territory)
- `AGENTS.md` — **READ THIS BEFORE OPENING A PR.** API contracts, tech stack, git rules, code ownership.

## Local development

See `AGENTS.md` for the full spec. Short version:

- **iOS**: open `almond-app/Almond.xcodeproj` in Xcode 15+, set the bundle ID to `com.almond.app`, run on a Watch + iPhone pair (or the simulator with seeded HealthKit data).
- **Backend**: `cd almond-ml && pip install -e . && uvicorn main:app --reload`. Requires Python 3.11+. Copy `almond-ml/.env.example` to `almond-ml/.env` and fill in the keys before running.

## Contributing

Read `AGENTS.md` first — particularly **The Daddy Rule** at the top. Short version:

- All work on feature branches (`feat/<desc>`, `fix/<desc>`, etc.)
- All changes via PR to `main`
- Only Deniz (`@3arii`) merges PRs
