# Nerra Network — Brand Guidelines

**Version:** Refresh 2026 · **Type:** Refresh & systematize · **Feeling:** Energy & momentum
**Status:** Proposed for deployment. Nothing here is live until you ship it.

---

## 1. The idea

Nerra Network began as a single show, Tesla Shorts Time. It is now a multi-show, multilingual daily podcast network with shows in English, French, Russian and Chinese. This refresh keeps everything that already works — the name, the constellation mark, the dark intelligent base, the electric gradient — and fixes the system underneath so it scales cleanly as the roster grows.

> A note on numbers: this system is deliberately **count-agnostic**. Public-facing brand copy and assets avoid stating an exact number of shows, because the roster keeps growing and we don't want to re-version everything each time a show launches. Use "daily shows," "a growing network," or name a few flagships instead.

The organizing feeling is **energy and momentum**: a network that ships something new every single day. The promise stays human: *feed your curiosity, not your anxiety.*

What this refresh deliberately does **not** do: rename, redraw from scratch, or disrupt subscribers. Every podcast feed, RSS URL, and R2 path is untouched.

---

## 2. Logo

### Components

The identity has two parts that can travel together or apart:

The **mark** is a broadcast constellation — a bright central hub pushing signal out to six nodes inside a faint pulse ring. It reads simultaneously as a *network* and as *energy radiating outward*. It is built from pure geometry, so it reproduces perfectly at any size and in any renderer.

The **wordmark** sets *Nerra* in solid white (or ink, on light) and *Network* in the signal gradient. It is drawn as a fixed vector outline based on Poppins Bold, so it never depends on a font being installed.

### The lockups (files in `/assets/`)

| File | Use |
|---|---|
| `nerra-logo-horizontal.svg` | Primary. Site header, dark backgrounds. |
| `nerra-logo-horizontal-light.svg` | Pale/white backgrounds, print, light email. |
| `nerra-logo-stacked.svg` | Square-ish spaces, hero, app splash. |
| `nerra-mark.svg` | App icon, avatar, standalone badge. |
| `nerra-favicon.svg` | Favicon and anything under ~40px (simplified 4-node mark). |
| `nerra-mark-mono.svg` | Single-color contexts (uses `currentColor`). |

### Clear space & minimum size

Keep clear space on all sides equal to the mark's corner radius (~24% of the mark's height). Don't crowd it. Minimum sizes: full horizontal lockup no smaller than 150px wide; below ~40px switch to `nerra-favicon.svg`.

### Do

- Use the gradient wordmark on dark; the light lockup on pale backgrounds.
- Let the mark stand alone as an avatar or app icon.
- Scale the whole lockup proportionally.

### Don't

- Recolor the gradient, or substitute show colors into the network mark.
- Stretch, rotate, outline, or drop-shadow the wordmark.
- Rebuild the wordmark in a system font — it is a fixed outline.
- Place the gradient wordmark on a busy or mid-tone photo without a scrim.

---

## 3. Color

### The Nerra Signal gradient (locked)

```
linear-gradient(135deg, #6B47FF, #00D4FF)
```

The previous files carried **two** competing gradients (`#6B47FF→#00D4FF` and `#60A5FA→#8B5CF6`). Only the one above is blessed. Retire the blue/purple variant everywhere it appears (old master logo, social banner).

### Core palette

| Token | Hex | Role |
|---|---|---|
| Electric Violet | `#6B47FF` | Primary brand, gradient start, `theme-color` |
| Signal Cyan | `#00D4FF` | Secondary brand, gradient end, active/highlight |
| Nerra Ink | `#0B0F1A` | Base background |
| Deep Slate | `#0F172A` | Elevated surfaces |
| Paper | `#F8FAFC` | Primary text on dark |
| Mist | `#9FB0C9` | Muted text on dark |
| Slate-600 | `#475569` | Muted text on **light** (AA-safe) |

### Accessibility correction

The old muted greys `#64748B` and `#94A3B8` fall below WCAG 2.1 AA (4.5:1) when used as body-weight text on white. Rule going forward: muted text is **Mist `#9FB0C9`** on dark surfaces and **`#475569`** on light surfaces. Reserve `#94A3B8` for large/secondary labels on dark only.

---

## 4. The constellation system — one node per show

The network mark stays pure gradient. Each **show** owns one accent color — its node in the constellation, its cover-art glow, and its on-air signature. Distinct, deliberately spaced hues keep the family from blurring together; assign the next free hue when a show launches. Current roster:

| # | Show | Cadence | Accent |
|---|---|---|---|
| 1 | Tesla Shorts Time | Daily | `#E31937` |
| 2 | Omni View | Daily | `#2563EB` |
| 3 | SpaceX Daily | Daily | `#4F46E5` |
| 4 | Fascinating Frontiers | Daily | `#7C5CFF` |
| 5 | Planetterrian Daily | Daily | `#06B6D4` |
| 6 | Models & Agents | Daily | `#8B5CF6` |
| 7 | Models & Agents for Beginners | Daily | `#F59E0B` |
| 8 | Modern Investing Techniques | Weekdays | `#10B981` |
| 9 | Environmental Intelligence | Odd weekdays | `#1B7F3B` |
| 10 | First Principles Daily | Daily | `#0EA5E9` |
| 11 | Unintended Consequences | Weekdays | `#C2410C` |
| 12 | Финансы Просто | Even days | `#EC4899` |
| 13 | Привет, Русский! | Even days | `#F43F5E` |

New shows take the next visually distinct hue and slot into the constellation automatically.

> Implementation note: this maps directly onto the existing `show_color` token in `templates/base.html.j2`. Align the per-show YAML `show_color` values to this table to make the website, covers, and node art agree.

---

## 5. Typography

A three-voice system — two already loaded on the site today.

**Display / Logo — Poppins** (weights 600–800). Headlines, the wordmark, big stat numbers. Geometric and confident: the "momentum" voice.

**UI / Body — DM Sans** (400–700). Navigation, buttons, captions, all interface text. Already the site font.

**Editorial — Source Serif 4** (400/600). Long-form blog reading. Already the site serif. Signals human-written, not content-mill.

Pairing rule: Poppins for anything that should feel like a *statement*; DM Sans for anything that should feel like an *interface*; Source Serif only inside article bodies. The logo wordmark is outlined, so adding Poppins as a webfont is optional — only needed if you also want Poppins headings on the site (recommended for the momentum feel, ~1 extra font load).

---

## 6. Show cover artwork

One template, every show. Use `nerra-show-cover-template.svg` and change **three** variables per show:

- `SHOW-COLOR` — the show's accent from §4
- `SHOW-TITLE` — the show name
- `SHOW-KICKER` — the one-line descriptor

Locked across every cover: dark base, the accent glow, the show's node motif, the Poppins title, and the fixed Nerra Network badge at the bottom. This is what makes the catalog read as one family in Apple Podcasts and Spotify. Export covers at 3000×3000 (Apple's max) or at least 1400×1400.

---

## 7. Voice & messaging

### Personality

Energetic, plain-spoken, trustworthy. Nerra is the daily habit that leaves you *more* informed and *less* anxious — the opposite of doomscrolling. Unhurried confidence: we ship every day, so we never need to shout.

### Taglines

**Primary (keep):** *Feed your curiosity. Not your anxiety.* — it already does the heavy lifting; do not retire it.

**Momentum lines** (rotate by surface):

- *Every day. Every angle. One signal.* — banners, YouTube
- *The whole world, every morning.* — app store, newsletter
- *Independent, daily, ad-free intelligence.* — About, press
- *Smarter in fifteen minutes.* — social, Shorts

### Boilerplate (one line)

> Nerra Network is an independent, ad-free daily podcast network — Tesla, world news, space, science, AI, investing and more — produced in Vancouver, in English, French, Russian and Chinese. Feed your curiosity, not your anxiety.

### Boilerplate (paragraph)

> Nerra Network is an independent daily podcast network spanning Tesla and EV markets, balanced world news, space and astronomy, science and longevity, AI, modern investing, environmental policy, first-principles thinking, narrative case studies, and Russian-language finance and language learning. Every show is produced daily in Vancouver, Canada, is completely ad-free, and is available free in English, French, Russian and Chinese. The mission: stimulate curiosity, support developments that benefit everyone, and cover the world from every angle — so you can decide for yourself.

### Sounds like / never sounds like

| Sounds like | Never sounds like |
|---|---|
| Clear, energetic, curious | Clickbait, fear-driven |
| Balanced, multi-perspective | Partisan, editorializing |
| Unhurried confidence | Hype-y startup jargon |
| Human and warm | Robotic, content-mill |

---

## 8. Rollout checklist (suggested order, low-risk first)

1. **Favicon + site logo** — swap `assets/nerra-logo-icon.svg` for the refreshed `nerra-mark.svg` / `nerra-favicon.svg`. Update header lockup to `nerra-logo-horizontal.svg`.
2. **`theme-color` + OG image** — confirm `#6B47FF`; replace `assets/og-preview.png` with a PNG export of `nerra-og-preview.svg` (1200×630).
3. **Lock the gradient** — replace the `#60A5FA→#8B5CF6` gradient in the old master logo / social SVGs with the Signal gradient.
4. **Color tokens** — align per-show `show_color` YAML values to §4; correct muted-grey usage per §3.
5. **YouTube** — upload `nerra-youtube-banner.svg` (rasterized to 2560×1440) as channel art.
6. **Show covers** — regenerate each show's cover from the template as accent budget allows.
7. **Type** — optionally add Poppins for headings to bring the momentum voice to the site.
8. **Messaging** — update About, press kit, app-store and newsletter copy from §7.

Each step is independent and reversible. No feed URLs change at any point.

---

*Source assets: `/brand-refresh-2026/assets/`. Interactive board: `/brand-refresh-2026/brand-board.html`.*
