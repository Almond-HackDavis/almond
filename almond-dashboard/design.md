# Almond Dashboard · Design Rationale

This document explains *why* the dashboard looks the way it looks. It is the
companion piece to the runtime brand tokens declared in
`src/app/globals.css` and the Swift design system in
`almond-app/Almond/Design/Color+Almond.swift`. Anyone touching this codebase
should read this file before changing colors, fonts, spacing, or layout
patterns.

If you disagree with a choice below, edit it here in the same PR that
changes the code. **The doc and the code must move together.**

---

## 1. Voice and audience

The dashboard is built for **clinicians reading the chart of a single
patient enrolled in continuous monitoring.** Not for the patient. Not for
the marketing site.

Two design implications fall out of that:

- **Editorial, not consumer.** The page reads like a private medical
  dossier — closer to *The New England Journal of Medicine* or Bloomberg
  Terminal than to a Whoop or Oura app. The information density is high
  but never noisy; numbers and prose alternate so a clinician can scan or
  read.
- **Calm, not gamified.** No streaks. No medals. No "you're on fire 🔥".
  The patient's vitality score is a number, not a leaderboard. We trust
  the clinician to interpret movement; the UI does not editorialize it.

Voice in copy follows the same rule: third-person clinical
("Telemetry continues to corroborate the lifestyle plan from March")
rather than second-person personal ("You're crushing it!").

---

## 2. Color system

The palette is a single warm earth-tone family with two accent species
and four risk semantics. Every value here is mirrored from
`Color+Almond.swift` so iOS and web stay in lockstep.

### 2.1 Base palette

| Role            | Hex       | Use                                                         |
| --------------- | --------- | ----------------------------------------------------------- |
| `cream`         | `#fff9f2` | Page background. Warm enough to read as paper, not white.   |
| `cream-tint`   | `#f4ede7` | Inset surfaces (driver-bar troughs, equation card hover).   |
| `paper`         | `#faf2e7` | Reserved for future "elevated paper" treatments.            |
| `tan`           | `#dfbb96` | Decorative only; not yet used in the dashboard.             |
| `cocoa`         | `#c08a6a` | **The accent.** Brand mark, primary chart line, key links. |
| `cocoa-strong` | `#a8472b` | Risk-high foreground; emergency emphasis only.              |
| `espresso`      | `#3d291b` | Body ink; warmer-than-black anchor.                         |
| `ink`           | `#2f241e` | Primary headings — slightly darker than espresso for hierarchy. |

### 2.2 Risk semantics

Four bands, each with a foreground (used for text/icons/badges) and a
soft surface tint (used for card backgrounds, chart reference areas):

| Band     | Foreground | Surface tint | Vitality range |
| -------- | ---------- | ------------ | -------------- |
| Low      | `#8aa67a` | `#ebf0e6`   | ≥ 80           |
| Moderate | `#d9a648` | `#f7ecd1`   | 65–79          |
| Elevated | `#d97757` | `#f7ddd1`   | 50–64          |
| High     | `#a8472b` | `#ecd0c5`   | < 50           |

These are not arbitrary. The bands trace the AHA Life's Essential 8
quartile cutpoints loosely, and the colors are deliberately picked from
the natural-pigment family (sage / honey / coral / terracotta) so a
gradient across them reads as **continuous** rather than jumping a hue
wheel. Red-yellow-green stoplights would be a) cliché, b) hostile to
colorblind users at the moderate / elevated boundary, c) too aggressive
for a patient who is doing fine.

### 2.3 Hairlines and label tints

Borders never use a flat gray. They are **8 % espresso**
(`rgb(61 41 27 / 0.08)`) so they carry a hint of warmth and never break
the cream/cocoa palette. Label hierarchy is also driven from espresso:

- `text-ink` — full opacity, primary headings and KPI numerals
- `text-label-secondary` — espresso at 65 % alpha, body copy
- `text-label-tertiary` — espresso at 42 % alpha, eyebrows, tick labels

This means dark mode (when we add it) only needs to flip the *base*
color from espresso to cream; the alpha levels carry over cleanly.

### 2.4 What is NOT in the palette

We deliberately do not have:

- **Pure black or pure white.** Both are too cold for the brand.
- **Blue.** Blue is the canonical "tech health" color and using it would
  dissolve us into the Whoop / Oura / Withings visual mass. Cocoa is a
  more memorable hue that reads as "natural / clinical / warm".
- **Purple gradients.** Banned. They are the universal AI-slop tell.

---

## 3. Typography

### 3.1 The three families

| Family             | Use                                       | Why                                                                                                                    |
| ------------------ | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **Fraunces**       | Display (eyebrow → headline → KPI numerals) | A variable serif with `opsz` (optical size) and `SOFT` axes. At display sizes it is dramatic and editorial; at 20 px it is gentle. One typeface covering the whole display range eliminates the "Cooper Black + Helvetica" mismatch. |
| **Geist Sans**     | Body, UI controls                          | Replaces Inter, which the industry has flattened into invisibility. Geist has more character (lower-case `g`, terminal cuts) without losing the systems-font legibility. |
| **Geist Mono**     | All numerics, eyebrows, tick labels        | `tabular-nums` prevents column-jitter when scores update. Mono in eyebrows + units gives the page a quiet "data product" texture. |

We deliberately do not use SF Pro (Apple's proprietary face) on the web
for legal reasons; Geist is the closest spiritual substitute that ships
on Vercel's CDN with no extra license.

### 3.2 Scale

| Tier             | Size              | Weight | Tracking | Where             |
| ---------------- | ----------------- | ------ | -------- | ----------------- |
| Hero numeral     | `clamp(96, 13vw, 168)` Fraunces | regular | -0.02em | Vitality score   |
| Display H1       | 40-52 px Fraunces | regular | -0.01em | Page headline     |
| Card title       | 22 px Fraunces    | regular | normal   | Card titles       |
| KPI mid          | 44 px Fraunces    | regular | normal   | Risk-equation cards |
| Editorial pull   | 20 px Fraunces    | regular | 1.55 lh  | Gemma synthesis   |
| Body             | 14-15 px Geist    | regular | 1.6 lh   | Paragraphs, kicker |
| UI primary       | 13 px Geist       | medium  | normal   | Card body, drivers |
| Eyebrow / tick   | 10-11 px Mono     | medium  | 0.16-0.22em | Eyebrows, units  |

Eyebrows always use **mono + uppercase + ≥0.14em letterspacing**. This
is the dashboard's most identifiable typographic tic.

### 3.3 Numerics

Every value that can change between syncs uses `tabular-nums`. Every
unit uses Geist Mono. The pairing of a Fraunces display numeral
(`81.9`) with a mono unit (`/ 100`) is intentional — the number gets
the editorial weight, the unit reads as metadata.

Optical sizing (`fontVariationSettings: "'opsz' 144"` on hero, `'opsz'
96` on card numerals) is the difference between a serif that looks
dignified at 96 px and one that looks bloated. Always set it explicitly
when you go above 32 px.

---

## 4. Layout and spatial composition

### 4.1 The grid

- 12-column CSS grid inside a `max-w-[1280px]` container with `px-8`
  (mobile) / `px-12` (large) gutters.
- Vertical rhythm is multiples of 4 px, with the most common inter-card
  gap at 24 px (`gap-6`).
- The hero breaks the grid intentionally: the giant numeral lives in a
  9 / 12 region, with the sparkline + delta in a 3 / 12 column separated
  by a hairline. Asymmetric, but anchored.

### 4.2 Density

Density is **higher than a marketing page** and **lower than an EHR**.
Cards have 28-32 px of internal padding. There is whitespace between
panels but no float-y margin pretending to be art-direction. A
clinician reading on a 1440 px display should be able to see the hero,
the timeline, and the top of the drivers list without scrolling.

### 4.3 Card surface

A single `Card` primitive (`src/components/Card.tsx`) defines all
cards. Every card is:

- `rounded-2xl` (16 px radius) — softer than 4 / 8 px (which reads
  technical) but stops short of 24 px (which reads consumer).
- A `1px` hairline border at 8 % espresso.
- A two-stop shadow: `0 1px 0 4%-espresso` (a subtle bottom edge that
  separates the card from cream) plus `0 8px 24px -12px 8%-espresso`
  (a faint atmospheric drop shadow). Combined, they give the cards
  presence without ever looking heavy.

There is no second card variant. If a region needs more emphasis, we
turn up the size of the typography inside, not the elevation of the
card.

---

## 5. Motion

The dashboard is **mostly motionless**. There is exactly one keyframe
animation defined (`rise-in`, used on the hero numeral), and one
ambient pulse (the green sync-status dot). Recharts contributes its
default tooltip transition.

We do not have:

- Scroll-triggered reveals
- Parallax
- Lottie animations
- Hover scale on cards
- Shine effects on borders

Motion is reserved for things that are **state changes**, not for
decoration. If a future PR adds an animation, it should be either a
state transition (a number changing) or a calming ambient cue (the
sync dot).

---

## 6. Iconography and ornament

**No icon library.** Lucide is installed in case we need it for a
nav-bar later, but the current dashboard uses zero icons. Information
is communicated through typography, position, and color — not glyphs.

Two ornaments do appear:

- **Quote glyphs** (`"`) around the Gemma synthesis, in cocoa, in
  Fraunces. They are doing real editorial work — the synthesis is a
  model utterance, and the quote marks set it apart.
- **Round dots** (2 px) in the clinician timeline, in cocoa. They mark
  events on a vertical hairline; they are not decorative.

---

## 7. Texture

The cream background carries a near-invisible **3.5 %-opacity SVG noise
overlay**, applied to `body::before` with `mix-blend-mode: multiply`.
At normal viewing distance you cannot see it; if you remove it, the
page reads as cheaper plastic. This is the only "texture" trick on the
page and it must remain subtle.

If you ever need to add another texture, do it inside a card and clip
it. Never add more grain to the page background.

---

## 8. Charts

Charts use Recharts. The treatment is:

- **One color per series**, drawn from the cocoa or extended palette.
- **Area fill is a vertical gradient** from 30 % opacity at the top to
  2 % at the bottom, using a per-chart `linearGradient` defined inline.
- **Stroke is 1.6 px** — heavier than 1 px so it carries through retina
  scaling, lighter than 2 px so it does not look like a stock template.
- **Reference areas** (used on the vitality timeline for the four risk
  bands) are the corresponding surface tints at 40-55 % opacity.
- **No grid lines on the y-axis**, only horizontal gridlines at the
  hairline opacity. The eye should follow the curve, not the grid.
- **All tick labels** are Geist Mono, 10.5 px, 0.06 em letterspacing.
- **Tooltip** is a custom card (cream background, hairline border,
  same radius as the page cards). The default Recharts tooltip looks
  like an admin panel and would break the editorial register.

The single `Sparkline` primitive (`src/components/Sparkline.tsx`) is
hand-rolled SVG, not Recharts, because Recharts ships ~70 KB of JS we
don't need for a 30-point inline trend.

---

## 9. Voice and information architecture

The page is composed top-to-bottom in this order, deliberately:

1. **Identification** (sticky top bar + editorial header) — answers
   "whose chart am I looking at?" before anything else.
2. **Headline number** (hero) — the score and its trajectory. If the
   clinician closes the page now, they leave knowing the patient's
   current vitality and recent direction.
3. **Trend** (timeline) — the long-form view of the same number with
   risk bands.
4. **Drivers** (left) and **synthesis + clinician notes** (right) —
   these are the two ways to interpret the trend: bottom-up (which
   inputs are moving the score) and top-down (the model's narrative
   plus the human notes).
5. **Validated equations** — the deepest, most clinical layer. Placed
   last because the doctor reaches it only when they want to dig.
6. **Disclaimer** — never the lead, always the footer.

This is the Bloomberg Terminal idea: **headlines on top, deep data on
bottom**, with the depth always reachable.

---

## 10. Accessibility commitments

- Color contrast: every body-copy color meets WCAG AA against cream
  (verified via the espresso-65% / espresso-42% alpha ladder).
- Fraunces and Geist both ship full Latin extended; we set
  `subsets: ["latin"]` only because the audience is currently English-
  primary.
- `tabular-nums` ensures numbers do not jump under screen-reader
  navigation.
- The sync-status dot has an accessible name in the `aria-hidden`
  parent element; future change-of-state announcements should land on
  the parent.
- Charts have visible numeric tick labels and a tooltip on hover; we
  will add a tabular fallback view in a follow-up PR for users who
  cannot perceive the line trend.

---

## 11. What the design **explicitly avoids**

A short list of things we considered and rejected:

- **Light/dark mode toggle.** Dark mode on a clinical page reads as
  "off-hours admin tool". The dossier is meant to be read in daylight.
  We can add a printer-friendly mode later if needed.
- **A side navigation rail.** We have one page. Adding a rail would
  imply a hierarchy that does not exist yet.
- **Skeleton loaders.** Server components fetch on the server; the page
  ships with content. No skeletons means no false sense of motion.
- **Glassmorphism / blurred panels.** They date a UI to 2021 and do not
  fit the editorial register.
- **Gradients on text or cards.** Reserved for charts only.

---

## 12. Files to read after this one

- `src/app/globals.css` — the CSS variables that operationalize this doc
- `src/app/layout.tsx` — font loading + html scaffold
- `src/components/Card.tsx` — the single card primitive
- `src/lib/format.ts` — number / date formatters and the risk-band map
- `src/lib/fixtures.ts` — synthetic data shape (replace with API
  payload once `/history` is wired)
- `almond-app/Almond/Design/Color+Almond.swift` — the iOS source of
  truth for color tokens; keep this and `globals.css` in sync

That's the whole design language. If you need to deviate, leave a
comment in the PR explaining which guideline you are breaking and why.
