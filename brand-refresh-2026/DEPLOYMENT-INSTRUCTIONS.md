# Brand Refresh — Deployment Instructions for Claude Code

**Context:** The refreshed brand assets + copy live in `/brand-refresh-2026/`. None of it is deployed yet. The site is **template-generated** (`templates/*.j2` + `generate_html.py`) and **regenerated nightly**, so edit the SOURCE files below — never the generated `*.html` — then regenerate and commit.

Do not touch RSS feed URLs, R2 paths, or audio URLs at any point.

---

## 1. Swap in the refreshed visual assets

1. **Header / favicon mark** — replace the contents of `assets/nerra-logo-icon.svg` with `brand-refresh-2026/assets/nerra-mark.svg` (keeps every existing reference working). 
2. **Favicon** — copy `brand-refresh-2026/assets/nerra-favicon.svg` → `assets/nerra-favicon.svg`. In `templates/base.html.j2`, point the `<link rel="icon">` tags at it (and `assets/png/favicon-32.png` / `favicon-16.png` as raster fallbacks, also in `brand-refresh-2026/assets/png/`).
3. **Share image** — copy `brand-refresh-2026/assets/png/og-preview-1200x630.png` → `assets/og-preview.png` (overwrite). This is the file the OG/Twitter meta tags already reference, so no template change needed.
4. **Add the logo lockups** for reuse — copy `nerra-logo-horizontal.svg`, `nerra-logo-stacked.svg`, `nerra-logo-horizontal-light.svg`, `nerra-mark-mono.svg` into `assets/`.
5. **Optional (recommended):** swap the text header for the real wordmark — in `templates/base.html.j2` the header currently renders the icon + plain "Nerra Network" text; replace with `assets/nerra-logo-horizontal.svg` for the locked lockup.

---

## 2. Make all copy count-agnostic (no exact show number)

The homepage uses `{{ all_shows | length }}` in several places. An auto-count never needs manual updating, but per the brief we want **no explicit show number** at all. Replace the number with qualitative phrasing:

| File : line | Current | Change to |
|---|---|---|
| `generate_html.py` : ~2468 | `f"Nerra Network \| {len(NETWORK_SHOWS)} Daily Shows"` | `"Nerra Network — Daily Podcast Network"` |
| `generate_html.py` (meta description near page_title) | `"… 13 daily podcasts …"` | drop the number: `"Daily podcasts keeping you informed…"` |
| `templates/network_page.html.j2` : 104 | `{{ all_shows \| length }} ad-free shows covering…` | `Ad-free daily shows covering Tesla, world news, space, science, AI, investing, and more. Produced daily in Vancouver.` |
| `templates/network_page.html.j2` : 409 | `{{ all_shows \| length }} ad-free shows on the ideas…` | `Ad-free shows on the ideas shaping tomorrow.` |
| `templates/network_page.html.j2` : ~133 (hero stat) | `{{ all_shows \| length }} daily shows` | `Daily` / label `fresh episodes` |
| `templates/network_page.html.j2` : ~174 (stats bar "Shows") | `{{ all_shows \| length }}` / `Shows` | `Daily` / `New episodes`  (or remove this stat item) |
| `templates/base.html.j2` : 152 (footer, EN + RU) | `(all_shows\|length) ~ ' shows. Zero fluff. …'` | `'Daily, ad-free, independent — produced in Vancouver, Canada.'` (and localize the RU string the same way, no count) |

---

## 3. Fix the language references (4 production languages: English, French, Russian, Chinese)

Replace every hardcoded **"2 languages"** with **"4"**, and update the multilingual copy:

| File : line | Current | Change to |
|---|---|---|
| `templates/network_page.html.j2` : 138–139 | `2` / `languages` | `4` / `languages` |
| `templates/network_page.html.j2` : 186–187 | `2` / `Languages` | `4` / `Languages` |
| `templates/editorial.html.j2` : 132 | `>2<` languages | `>4<` |
| `templates/show_page.html.j2` : 235 | `>2<` languages | `>4<` |
| `templates/network_page.html.j2` : 331–332 (Multilingual card) | `Shows in English and Russian, with more languages planned.` | `Shows produced in English, French, Russian and Chinese. Knowledge shouldn't have a language barrier.` |

Note: the **audio-language switcher** (globe menu: EN/FR/ES/RU/ZH) is a *translation* layer and is separate — leave it as-is. The "4 languages" claim refers to languages shows are *produced* in. If you'd rather not hardcode `4` either, use the word **"Multilingual"** instead of a number.

---

## 4. Align per-show accent colors (optional polish)

Per-show colors live in two places — make them agree with the table in `Nerra-Network-Brand-Guidelines.md` §4:

- `generate_html.py` → `NETWORK_SHOWS` dict: `brand_color` / `brand_color_dark` / `theme_color` per show (e.g. line 162 Tesla `#E31937`).
- `shows/network_meta.yaml` → per-show `color:`.

Lock the network gradient too: search the repo for the legacy gradient `#60A5FA` / `#8B5CF6` and replace those stops with `#6B47FF` → `#00D4FF`.

---

## 5. Regenerate, verify, commit

1. Regenerate the static site from templates (the repo's standard build — e.g. `python generate_html.py` and the blog/shared-pages step the pipeline uses). Do **not** hand-edit generated HTML.
2. Verify locally: homepage title has no show count; hero/stats/footer have no show count; languages read "4" / "Multilingual"; the new mark + OG image load.
3. Commit the source changes (templates, `generate_html.py`, `assets/`, YAML) and push. GitHub Pages will deploy.

---

## 6. Manual (not code) — do these by hand

- **YouTube channel banner:** upload `brand-refresh-2026/assets/png/youtube-banner-2560x1440.png` in YouTube Studio.
- **Social headers (X/LinkedIn):** upload `social-banner-1500x500.png`.
- **Show cover art:** regenerate each show's cover from `nerra-show-cover-template.svg` (swap SHOW-COLOR / SHOW-TITLE / SHOW-KICKER), export ≥1400², and replace `assets/covers/*` as accent budget allows.
