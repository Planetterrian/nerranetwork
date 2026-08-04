# Offshore North — Brand System

## Palette

| Token | Hex | Role |
|---|---|---|
| **Hull Navy** | `#0B3C5D` | The brand colour. `brand_color`, `brand_color_dark`, `theme_color` in `network_meta.yaml`. Primary surface. |
| **Deep Water** | `#071E2E` | Darkest ground. Top of the cover gradient, page background, footer. |
| **Spray** | `#7FD3E0` | Cold cyan accent. Rules, chart lines, kickers, links, metadata. Never for body text. |
| **Signal Red** | `#E23E2C` | The one warm accent. Compass north needle, section rules, live/new badges. Used sparingly — roughly 2% of any surface. |
| **Chart Paper** | `#F4F1EA` | Off-white. All display type and body copy on dark grounds. Never pure `#FFF` — the warm cast is what keeps the palette from reading clinical. |

**Why this palette:** no other Nerra show uses navy. The DP Pod is green
(`#0B7A45`), SpaceX Daily is electric blue (`#1A5CFF`), The Age of AI is
purple (`#7C3AED`). Deep navy with a cold cyan and a single red accent reads
unmistakably as cold-ocean, and the red does double duty — a compass north
needle, an offshore safety colour, and a quiet Canadian nod without ever
resorting to a maple leaf.

### Contrast (WCAG AA)

- Chart Paper on Hull Navy — **8.9:1** ✅ (body text, all sizes)
- Chart Paper on Deep Water — **15.4:1** ✅
- Spray on Hull Navy — **5.6:1** ✅ (large text and UI; fine for kickers)
- Signal Red on Deep Water — **4.1:1** — **large text and graphic marks only.** Never body copy.

## Typography

| Role | Face | Notes |
|---|---|---|
| Wordmark | **Anton** (OFL) | Display only. `OFFSHORE` / `NORTH` set at equal cap height, flush stacked, `NORTH` tracked out to match `OFFSHORE`'s measure. Never set the wordmark on one line; the two-line lockup is the mark. |
| Headings + UI | **Archivo** 600/700 (OFL) | Kickers and labels are all-caps with generous letter-spacing (0.18–0.24em). |
| Body | **Archivo** 400, or the network's existing body face | Sentence case, normal tracking. |

**Fallback stack:** `Anton, "Archivo Black", Impact, "Helvetica Neue Condensed", sans-serif`
for display; `Archivo, Inter, "Helvetica Neue", Arial, sans-serif` for text.

## The wordmark

```
OFFSHORE
N O R T H
```

Rules: equal cap height on both lines. `NORTH` letter-spaced so the two lines
are the same width. Line gap ≈ 0.14 × cap height. Always Chart Paper on a
dark ground, or Deep Water on Chart Paper for light contexts. Never outlined,
never gradient-filled, never set in a single line.

## The compass mark

A thin Spray ring with 24 tick marks, a Signal Red north needle and a pale
south needle. It is the show's standalone icon — usable alone at small sizes
(favicon, avatar, chapter art) where the full wordmark won't survive.

## Cover art

`graphics/make_cover.py` renders the 1200×1200 cover deterministically, so
edits are a code change rather than a re-design. It also emits a 55 px
legibility proof — the size the cover actually appears at in an Apple
Podcasts list. Any change to the cover should be checked at that size first,
because that is where podcast art either works or doesn't.

**Composition:** chart-grid ground with two labelled latitude lines (60°N and
49°N — the 49th parallel is the Canada–US border, which is the whole joke);
horizon at the upper third; a foiling IMOCA lifted clear of the water; the
wordmark occupying the centre; a Spray kicker rule; a Signal Red rule over
the network signature.

### Three concepts considered

1. **Latitude** *(built)* — chart ground, foiler on the horizon, big stacked wordmark. Reads at 55 px, and the chart grid gives the show an ownable texture that extends to the site and to episode art.
2. **Bow-on** — an IMOCA bow filling the frame head-on, spray exploding outward, wordmark reversed out of the dark water. More dramatic, less legible at thumbnail size, and much harder to reproduce consistently week to week.
3. **The Wall** — pure typography: the wordmark filling the square on Hull Navy with a single red latitude rule and no imagery at all. The most confident option and the most legible, but it tells a browsing listener nothing about the subject, which matters for a show nobody is searching for yet.

Concept 1 is the build because a new show has to survive the thumbnail *and*
say what it is.

## Applying it elsewhere

- **Show page** — Deep Water background, Hull Navy cards, Spray rules, Signal Red only on the "new episode" marker.
- **Episode art / Shorts title cards** — compass mark top-left, episode number in Anton, headline in Archivo 700, chart grid ground.
- **Social** — the chart grid plus a single Signal Red rule is enough to be recognisable without the wordmark.
