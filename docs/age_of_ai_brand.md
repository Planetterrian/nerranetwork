# The Age of AI — brand system

Generated assets are reproducible: `python scripts/generate_age_of_ai_brand.py`
(then `python scripts/generate_webp.py` for the responsive cover variants).
The same script draws the sister show with `--show nerra_voices` (see
[Nerra Voices — the sister brand](#nerra-voices--the-sister-brand)).
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

## Nerra Voices — the sister brand

Nerra Voices (September 2026) is The Age of AI's sister interview show:
same host, same pipeline, no AI angle required. It shares the brand system
one-for-one — the same Dialogue mark, the same geometry, the same rules —
and differs in exactly one thing: **Mira wears the show teal instead of
violet.** The human amber wave is byte-identical between the two covers
(rule 2: amber = the human, and the human does not change between shows).

Generate: `python scripts/generate_age_of_ai_brand.py --show nerra_voices`,
then `python scripts/generate_webp.py`. The generator is parameterised by a
`BrandSpec` (palette, wordmark lines, subtitle, output stem); `AGE_OF_AI`
and `NERRA_VOICES` are the two registered specs and the Age of AI palette
constants (`SIGNAL_VIOLET` etc.) stay module-level so the
`test_generator_palette_matches_registered_brand_color` drift guard keeps
pinning them against `network_meta.yaml`.

### Palette

| Token | Hex | Age of AI equivalent | Usage |
|---|---|---|---|
| Signal Teal | `#0F766E` | Signal Violet | Primary brand (registered in `network_meta.yaml` `brand_color`, `brand_color_dark`, `theme_color` and the show yaml `voices.brand_color`); Mira's waveform; links/CTAs on show surfaces |
| Teal Bright | `#2DD4BF` | Violet Bright | Bar-gradient highlight toward the meeting point; hover states |
| Human Amber | `#FBBF24` | Human Amber | Unchanged — the guest's wave, the lockup rule |
| Deep Water | `#071E20` | Deep Field | Background base (cover bottom; mark tile) |
| Tide | `#0F3B3E` | Midnight | Background gradient top |
| Sea Glass | `#99F6E4` | Lavender | Aperture ring; secondary text ("WITH MIRA") |
| Tide White | `#F6FFFD` | Signal White | Wordmark; primary text on dark |

Why `#0F766E` and not a brighter teal: the network's newsletter contrast
guard (`tests/test_newsletter_template.py::test_every_show_brand_color_passes_aa_on_white`)
requires every `brand_color` / `brand_color_dark` to clear WCAG AA 4.5:1
against white, because the brand colour is used as text on white email
surfaces. `#0EA5A4` (the first draft) is 3.03:1 and fails; `#0F766E` is
5.47:1. The brighter `#2DD4BF` is reserved for the bar highlight and hover
states on dark surfaces, never for text on white.

### Wordmark

**NERRA / VOICES** on two lines, tracked caps, with the amber rule and
`WITH MIRA` beneath — the same lockup grid as THE AGE / OF AI.

### Assets

| File | Use |
|---|---|
| `assets/covers/nerra-voices.jpg` (3000×3000) | Podcast directories / RSS `<itunes:image>` / episode pages |
| `assets/covers/nerra-voices{,-800,-400}.webp` | Site `<picture>` variants (nav, cards) |
| `assets/nerra-voices-mark.svg` | Square mark: avatars, favicons, social profile |
| `assets/nerra-voices-logo.svg` | Horizontal lockup: page headers, the apply page, email headers |

All four rules above apply unchanged. Show notes and the launch runbook:
[`docs/nerra_voices.md`](nerra_voices.md).
