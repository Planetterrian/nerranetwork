# Anthology books — ebook + audiobook from the narrative shows (Aug 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Anthology books — ebook + audiobook from the narrative shows (Aug 2026)

Product B6 (operator-directed): a SERIES machine, not one-off books.
`books/series/<show>.yaml` is the branding contract (author **Patrick
Novak**, series title, subtitle template, show brand colors, Grok-art
style guides, `volume_chapters` — a series-level PRODUCT decision,
default 60, band 10–80, never 20: the 20-chapter volumes priced ~5x
market rate per word); `plan_next_volumes()`
(`engine/book_compiler.py`) cuts the next thin
`books/volumes/<id>.yaml` automatically as episodes accrue
(append-only — published volumes never change; **retired** volumes
are ignored for coverage and numbering; it can never emit volume 0 or
an episode already in a live volume — `TestWO12SeriesVolumes`;
`--plan-preview` is the dry run), and
`scripts/build_book.py` (Actions "Build Book": manual per-volume, or
monthly-cron planner mode that plans + builds everything pending)
compiles digests into a store-ready EPUB 3 + Grok-TTS-narrated
chaptered M4B. Text transform is **deterministic — no LLM**; art is
`engine/book_art.py` on **pinned** `grok-imagine-image-quality` (never
a floating -latest alias): one 16:9 illustration per chapter (embedded
in the EPUB, re-encoded ≤~1000px JPEG for KDP delivery fees) + fresh
portrait cover art per volume under FIXED series typography
(`compose_cover` — consistency is the series branding; style guides ban
text inside generated images). Every generated image also uploads to
the show's public gallery with `intended_use` `book_chapter`/
`book_cover` — values the video scene selector must NEVER match (the
thumbnail_variant precedent). Cost/volume ≈ $1 art + $2 TTS, gated by
`--max-image-cost-usd` / `--max-tts-cost-usd`. Rules that bind: chapter
titles are CURATED (`chapter_titles:` map in each volume YAML — never
derived from the episode hook, which is a full sentence and truncated
in every store TOC on the first submission attempt, 2026-08-22) and
clip via `engine.titles.BOOK_CHAPTER_TITLE_MAX`; narration speaks only
"Chapter N." (deliberately decoupled from the printed title so title
edits re-mux, never re-narrate); planner mode builds any committed
volume with no cataloged artifacts (not just same-run plans), a
no-upload build never writes the catalog, narrated tracks persist to
R2 `books/<id>/audio/` keyed by narration-text hash (true CI
resumability + the stores' per-chapter MP3s), and
`scripts/verify_book_catalog.py` asserts claimed artifacts answer 200
after every workflow build; EVERY
reader-facing link goes through `engine.funnel` `kind="book"` (campaign
carries the VOLUME number; each chapter ends on a funnel-tagged link to
its source episode page); artifacts to R2 keyspace `books/<id>/` ONLY
(never a show's audio prefix); `outputs/books/` gitignored (landmine
#1); **the EPUB embeds display-size images only** (Sept 2026 — the
first 73-chapter collected edition shipped at 15.4 MB, 96% images, a
4.8 MB PNG cover: $2.25 of KDP delivery fee per sale and over the 10 MB
upload cap; now chapter art at 720 px under a ~45 KB budget, the cover a
1200×1920 JPEG, documents deflated, `build_epub` refuses anything over
`EPUB_MAX_BYTES` = 5 MB — tune `engine.book_art`'s `EPUB_*` constants,
never the cap; full-res art stays on R2/gallery); **store-level digital-narration DECLARATIONS are non-negotiable
(KDP AI questionnaire stays YES, Spotify's digital-narration box stays
ticked, Google Play stays declared — never remove any of them;
Audible/ACX takes no third-party AI narration at all), but the SPOKEN
in-file disclosure line was removed from the audiobook credits Aug 2026
(WO-8, operator-directed) — no retail channel requires a spoken line,
only the upload declaration; an earlier note here conflated the two.** Committed record: series + volume
YAMLs + `books/catalog.json` → `/books.html` (`generate_html.py
--books`, in `--all` + sitemap + footer). **Store links live in the
volume YAML** (`buy_links`: `direct`, `audiobook_direct`, `books2read`,
retailers) — `/books.html` reads them from the YAML at render time
(`books_page_volumes`, YAML wins per key); the catalog copy refreshes
only on a build, so never hand-edit it for links (WO-15). **Audiobook
masters reach the operator only via Actions "Export audiobook"**
(`scripts/export_audiobook.py`): private-bucket zip (tracks + retail
sample + 3000² cover + manifest), the zip and M4B attached to the run as
3-day **artifacts** with a sha256 table in the step summary — never a
download URL anywhere in CI (WO-15b: GitHub masks the endpoint secret
out of the summary, so a presigned link renders dead; `--print-url` is
local-only). Live (WO-12, Sept 2026): **UC Volume 1** (73 chapters, eps 1–80) and
**First Principles Volume 1** (58 chapters, eps 1–60) — the former
"Collected Editions", renumbered because they are Volume 1 of an
ongoing series (Volume 2 comes from ep 81 / ep 61); their volume ids
keep the historical `_collected` names on purpose (R2 keyspace +
narration cache; `_vol1` is taken). The 20-chapter vol1–4 / vol1–3
books are **retired** (`retired: true` — never on a store, hidden from
books.html and cross-promo, kept for provenance). Spot-listen +
eyeball art on a new volume before store submission (landmine-#17
habit). Store checklist + policies: [`docs/books.md`](docs/books.md).
Drift guards: `tests/test_book_compiler.py`.
