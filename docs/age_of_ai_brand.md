# The Age of AI — brand system

Generated assets are reproducible: `python scripts/generate_age_of_ai_brand.py`
(then `python scripts/generate_webp.py` for the responsive cover variants).
Never hand-edit the JPG/SVGs — change the generator and re-run, so the cover,
mark, and lockup can never drift apart.

## The idea: "The Dialogue"

Inside a circular aperture (the frame of a documentary lens / an open line),
two waveforms meet at the centerline:

- **Mira — quantized violet bars.** Discrete, precise, machine-sampled.
  Uses the show's registered brand violet, brightening toward the meeting
  point (the machine leaning in to listen).
- **The guest — one smooth amber wave.** Continuous, organic, calmer than
  the machine's signal, ending in a full stop of a dot: a person finishing
  a thought.

The mark literalizes the show's premise — an AI asking, a human answering —
and stays legible at 160 px podcast-thumbnail size (the two-color split
reads before any detail does).

## Palette

| Token | Hex | Usage |
|---|---|---|
| Signal Violet | `#7C3AED` | Primary brand (registered in `network_meta.yaml` `brand_color`); Mira's waveform; links/CTAs on show surfaces; waveform-video fallback card |
| Violet Bright | `#A770FF` | Bar-gradient highlight toward the meeting point; hover states |
| Human Amber | `#FBBF24` | The guest's wave; the underline rule in the lockup; small accents ONLY — amber is the human's color, never used for machine/UI chrome |
| Deep Field | `#120D2E` | Background base (cover bottom; mark tile) |
| Midnight | `#291B5C` | Background gradient top |
| Lavender | `#C4B5FD` | Aperture ring; secondary text ("WITH MIRA"); muted UI text on dark |
| Signal White | `#F8F7FF` | Wordmark; primary text on dark |

Site integration: the pages already receive `--show-color: #7C3AED` from
`network_meta.yaml` — no CSS token changes needed. The dark-first site
palette (docs/design_system.md) and Deep Field are adjacent by design.

## Typography

Cover/raster: DejaVu Sans Bold (the container-safe stand-in with DM-Sans-like
proportions), tracked caps. Web: the site's standard `DM Sans` stack — the
SVG lockup declares `'DM Sans', system-ui, sans-serif` so it inherits the
site font where loaded.

Wordmark is always tracked uppercase: **THE AGE OF AI**, with the amber rule
and `WITH MIRA` beneath. Don't set the show name in mixed case in brand
surfaces (body prose is fine).

## Assets

| File | Use |
|---|---|
| `assets/covers/age-of-ai.jpg` (3000×3000) | Podcast directories / RSS `<itunes:image>` / episode pages |
| `assets/covers/age-of-ai{,-800,-400}.webp` | Site `<picture>` variants (nav, cards) |
| `assets/age-of-ai-mark.svg` | Square mark: avatars, favicons, social profile |
| `assets/age-of-ai-logo.svg` | Horizontal lockup: page headers, the apply page, email headers |

## Rules

1. The wave meeting is the brand — never separate the bars from the wave.
2. Amber = the human. Machine/UI elements never wear it.
3. Dark surfaces only for brand lockups (Deep Field/Midnight); on light
   surfaces use the mark tile (it carries its own background).
4. Every episode surface keeps the disclosure adjacency: where the brand
   appears at full size, "AI host, real humans" phrasing should be nearby
   (the apply page and show page already do this).
