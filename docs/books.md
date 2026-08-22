# Books — anthology ebooks & audiobooks from the narrative shows

**Shipped:** 2026-08-18 (product B6 in
[`docs/product_opportunities_2026_08.md`](product_opportunities_2026_08.md));
series machinery + Grok art + auto-planner same day (operator-directed).
**Author on every volume: Patrick Novak.**
**Live series:** *Unintended Consequences* Vols 1–4 (episodes 1–80) and
*First Principles* Vols 1–3 (episodes 1–60) — 20 stories per volume.

## What the pipeline does

```
books/series/<show>.yaml       SERIES config — author, series title,
        │                      subtitle template, brand colors, Grok art
        │                      style guides, volume_size (10-20)
        │  plan_next_volumes() cuts the next 20-episode volume config
        │  automatically as the show publishes (append-only; published
        │  volumes never change)
        ▼
books/volumes/<id>.yaml        thin volume config (episodes + buy links);
        │                      everything else inherits from the series
        │
scripts/build_book.py --volume <id>            (or Actions: "Build Book";
        │                                       monthly cron = planner mode)
        ├─ engine/book_art.py        Grok Imagine (quality tier, pinned):
        │                            one 16:9 editorial illustration PER
        │                            CHAPTER + fresh portrait cover art
        │                            per volume; every image also lands in
        │                            the show's public gallery
        │                            (intended_use book_chapter/book_cover
        │                            — invisible to the video scene
        │                            selector)
        ├─ engine/book_compiler.py   digests → chapters (DETERMINISTIC — no
        │                            LLM) → EPUB 3 with embedded chapter
        │                            art + per-chapter funnel-tagged
        │                            "hear this episode" links + series-
        │                            branded cover (fixed typography
        │                            composited over the fresh art) +
        │                            free-sample EPUB
        ├─ engine/audiobook.py       chapters → Grok TTS (network voice) →
        │                            per-chapter MP3s → chaptered M4B
        ├─ R2 upload                 books/<id>/ keyspace on the audio bucket
        └─ books/catalog.json        committed metadata; /books.html renders
                                     it (generate_html.py --books; also in
                                     --all and the nightly regen)
```

Cost per 20-chapter volume: **$0 ebook text** (pure transform of
committed digests) + **~$1.05 art** (21 images × $0.05 on
`grok-imagine-image-quality`, gated by `--max-image-cost-usd`, default
$5) + **~$2 audiobook** (Grok TTS, gated by `--max-tts-cost-usd`,
default $10). Chapter images are re-encoded to ~1000px JPEGs so a
volume's EPUB stays ~2 MB (Amazon charges per-MB delivery on the 70%
royalty plan).

Rules that bind:

- **Chapter titles are CURATED, never derived.** Each volume YAML
  carries a `chapter_titles:` map (episode number → 2-5-word title,
  e.g. `1: "The Cobra Bounty"`). The original design clipped the
  episode hook — a full podcast sentence — and every store TOC entry
  read "Delhi's British government paid for dead cobras to…" (the
  2026-08-22 launch blocker). A missing title prints as bare
  "Chapter N" with a loud build warning; the planner scaffolds empty
  placeholders in every new volume, and
  `tests/test_book_compiler.py::TestChapterTitles` requires full
  coverage on committed volumes. Titles still clip through
  `engine.titles.BOOK_CHAPTER_TITLE_MAX` (titles rule).
- **The spoken form is decoupled from the printed title.** Narration
  says only "Chapter N."; the curated title appears in the heading,
  TOC, and M4B chapter markers (metadata). Editing a title therefore
  re-muxes, never re-narrates — title polish is free after the fact.
- ALL reader-facing links are funnel-tagged through `engine.funnel`
  (`kind="book"`, campaign `nn-<show>-en-book-ep<volume>` — every
  chapter ends on a link to its source episode's page, the strongest
  podcast-conversion surface in the book).
- Art style guides in the series configs BAN text inside generated
  images (typography is composited separately so series branding stays
  identical across volumes while every cover's art is new).

## Building volumes

- **One volume:** Actions → **Build Book** → volume id
  (e.g. `unintended_consequences_vol2`).
- **Planner mode:** leave the volume input empty (or let the monthly
  cron run) — plans the next volume for every series with ≥
  `volume_size` uncollected episodes AND builds every committed volume
  whose catalog entry has no artifacts (the 2026-08-22 fix: planner
  mode originally built only volumes created in that same run, so the
  first live dispatch went green having built nothing). A volume that
  was already built is NOT rebuilt by planner mode — to rebuild one
  (new titles, re-rolled cover), dispatch it by name.
- **Locally without credentials** the EPUB + branded cover still build
  (text-only, flat-color cover):
  `python scripts/build_book.py --volume <id> --skip-audio --skip-images --no-upload`.
  A build that uploads nothing never touches `books/catalog.json` —
  the catalog records what SHIPPED.

Artifacts land in `outputs/books/<id>/` (gitignored) and on R2 under
`books/<id>/`. Narrated tracks + text-hash sidecars persist to R2 at
`books/<id>/audio/track_NNN.mp3` — this is what makes CI re-runs
genuinely resumable (an ephemeral runner restores the cache and only
re-bills tracks whose narration text changed), and it doubles as the
per-chapter MP3 delivery audiobook stores ingest. The workflow commits
`books/catalog.json`, any new volume YAMLs the planner wrote, and
`books.html`, then verifies every claimed artifact answers 200 on R2
(`scripts/verify_book_catalog.py` — the original verify step passed on
a zero-output run).

**Listen and look before you ship.** The audiobook is new spoken audio
and the cover/chapter art is fresh generation — spot-listen two
chapters and eyeball the cover + a few illustrations of every volume
before submitting to stores (the landmine-#17 habit applies to paid
product more, not less). A weak cover: delete
`outputs/books/<id>/art/cover_art.png` and rebuild for a fresh roll, or
drop in your own art at that path.

## Adding a new series

Copy a file in `books/series/`, set the show, author, subtitle
template, brand colors (match the show page's brand color), and the two
art style guides. The planner picks it up on the next run. Series files
are the branding contract — editing one rebrands every FUTURE build of
that series.

## Store submission checklist (operator work, per volume)

The build gives you: `uc_vol1.epub` (store-ready EPUB 3),
`uc_vol1.m4b` (chaptered audiobook), `cover.png` (1600×2560), per-chapter
MP3s in `outputs/books/<id>/audio/` (aggregator ingest format), and the
free sample EPUB. As each listing goes live, paste its URL into
`books/volumes/<id>.yaml` → `buy_links` and re-run the workflow (or just
`generate_html.py --books` after editing catalog) so /books.html shows
the button.

**AI disclosure is mandatory and non-optional at every store below** —
both the AI-assisted text production and the digital-voice narration.
The book's copyright page and the audiobook's opening/closing credits
already carry it; the store forms ask separately. Policies move — verify
each at submission time.

1. **Amazon KDP** (ebook + paperback) — kdp.amazon.com, free.
   - KDP requires declaring AI-generated content at upload. Declare it.
   - Ebook: upload EPUB + cover; price $2.99–9.99 keeps the 70% royalty
     band; enroll the series so Vol 2 links automatically.
   - Paperback: KDP will want an interior PDF — a future `--paperback`
     flag can render one; not built yet.
   - Audiobook: Audible/ACX **does not accept third-party AI narration**
     (their "virtual voice" program is Amazon's own tool only). Do not
     submit the M4B there; sell audio through the channels below.
2. **Apple Books** — via Draft2Digital (easiest, no Mac needed) or
   directly with an Apple Books Connect account. D2D takes ~10% of net
   and also lands Kobo, Barnes & Noble, and library channels (OverDrive)
   from one upload. Apple accepts digitally narrated audiobooks through
   approved aggregators with narration labelled as digital.
3. **Google Play Books** — play.google.com/books/publish, free, accepts
   EPUB directly and accepts uploaded audiobooks (including digital
   narration, labelled). Also offers its own auto-narration — ignore it,
   ours is the network voice.
4. **Kobo Writing Life** — direct or via D2D; Kobo also takes audiobooks
   via Kobo/Findaway paths.
5. **Spotify (Findaway Voices)** — the audiobook aggregator route with
   explicit digital-narration acceptance (disclosure required). Ingests
   per-chapter MP3s — the `audio/` directory is already in their format
   (192k CBR 44.1kHz mono).
6. **Direct on nerranetwork.com** — /books.html lists volumes with buy
   buttons + the free sample EPUB (email-capture lead magnet). Direct
   *sales* (Stripe/Gumroad checkout delivering the EPUB/M4B) are the
   Gallery-Pro payment-rail work item — when that rail exists, books
   plug into it; until then the page routes to the stores.

Pricing guidance (from the product doc's market research): $4.99–6.99
ebook, $9.99–14.99 audiobook. The audiobook's unit economics are absurd
in a good way (~$4 to produce), so price for perceived value, not cost.

## Drift guards

`tests/test_book_compiler.py` — digest→chapter parsing on both digest
eras (real Ep005 + Ep093 fixtures), titles-rule compliance, EPUB 3
structural validity (mimetype-first, XML well-formedness, nav/spine
coverage), narration text cleanliness (no markdown, no speech tags),
AI-disclosure presence in both credits, M4B chapter-offset math and
ffmpeg command shape, funnel round-trip for `kind="book"`, catalog
upsert idempotence, volume-config episode existence, and the workflow's
wiring.
