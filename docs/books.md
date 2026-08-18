# Books — anthology ebooks & audiobooks from the narrative shows

**Shipped:** 2026-08-18 (product B6 in
[`docs/product_opportunities_2026_08.md`](product_opportunities_2026_08.md)).
**First volume:** `uc_vol1` — *Unintended Consequences*, Volume 1: episodes
1–50, ~36k words, ~4h narrated.

## What the pipeline does

```
books/volumes/<id>.yaml          volume config (show, episodes, title, links)
        │
scripts/build_book.py --volume <id>          (or Actions: "Build Book")
        │
        ├─ engine/book_compiler.py   digests → chapters (DETERMINISTIC — no
        │                            LLM; digests verified free of
        │                            podcast-isms) → EPUB 3 + cover PNG +
        │                            free-sample EPUB
        ├─ engine/audiobook.py       chapters → Grok TTS (network voice) →
        │                            per-chapter MP3s → chaptered M4B
        ├─ R2 upload                 books/<id>/ keyspace on the audio bucket
        └─ books/catalog.json        committed metadata; /books.html renders
                                     it (generate_html.py --books; also in
                                     --all and the nightly regen)
```

Cost per 50-chapter volume: **$0 ebook** (pure transform of committed
digests) + **~$4 audiobook** (Grok TTS at $/char; the build prints the
estimate and refuses past `--max-tts-cost-usd`, default $10) + $0 cover
(typographic PIL render — replace `outputs/books/<id>/cover.png` before
store submission if a designed cover is worth it).

Chapter TITLES come from the show RSS ("Ep N: hook") clipped through
`engine.titles.BOOK_CHAPTER_TITLE_MAX` — the titles rule applies to books
like every other surface. Back-matter links are funnel-tagged through
`engine.funnel` (`kind="book"`, campaign `nn-<show>-en-book-ep<volume>`),
so book-driven site visits are attributable in `api/funnel.json` like any
other surface.

## Building a volume

From Actions: **Build Book** → volume id (`uc_vol1`), optional
ebook-only. Locally without credentials the EPUB + cover still build
(`python scripts/build_book.py --volume uc_vol1 --skip-audio --no-upload`);
narration and upload need `GROK_API_KEY` + `R2_*`, which live in Actions.

Artifacts land in `outputs/books/<id>/` (gitignored) and on R2 under
`books/<id>/`. The workflow commits only `books/catalog.json` + `books.html`.

**Listen before you ship.** The audiobook is new spoken audio on the
network voice — spot-listen the first and one middle chapter of every
volume before submitting to stores (the landmine-#17 habit applies to
paid audio more, not less).

## Adding the next volume

Copy `books/volumes/uc_vol1.yaml`, bump `volume_id`/`volume_number`,
set the episode list. Conventions: split volumes at equal word counts
(~35k); UC Volume 2 is episodes 51–100 once the show reaches Ep100.
First Principles Daily is the second candidate show (evergreen
narrative essays, same digest structure).

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
