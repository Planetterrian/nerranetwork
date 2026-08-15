# tesla — quality review (2026-08-15)

_Operator-directed flagship pass (Tesla + SpaceX together) run in a Claude Code
session — implement mode, not proposal-only. Window Ep564–Ep573._

## Evidence

Snapshot: 10/10 `_tts.txt` below `min_podcast_words: 2000` (1247–1733w).
OP3 219/7d, 900/30d, weekly [197, 208, 185, 219] — flat while SpaceX grew
+135% on the same pipeline. Cost $0.50/ep. YouTube: en tier A (long_vpd 9.8);
**ru Shorts 251 views/video across 77 Shorts (19,353 views)** — Tesla's
highest-reach surface, with no `funnel:` block in `shows/tesla.yaml` and no
localized destination.

## Scoring prior predictions (2026-08-01 entry)

| Metric | Verdict | Evidence |
|---|---|---|
| spoken closer matches /closed at (up\|down)/ | **n/a — invalid baseline** | The "tic" was a measurement artifact: `review_snapshot.py`'s tokenizer dropped digits, so the well-formed closer "TSLA closed at $328.58, up $9.05, 2.8%." tokenized to "tsla closed at up". Verified against both `_tts.txt` and Whisper in BOTH windows — the closer was never broken. Tokenizer fixed (numbers → `0` placeholder) so the phantom cannot be filed a fifth time. |
| "keep an eye on" teaser opener | **hit** (0/10) | Ban live at `tesla_podcast.txt:152` — but the de-seed was implemented as a MANDATED verbatim opener ("open the teaser with the words 'Before we go'"), manufacturing a 10/10 successor tic with a "should/could clarify" sub-template in 6/10. See P1. |
| single CTA bigram ≤3/10 | **n/a — lever not shipped** | Closer-tail rotation never merged (`hooks/tesla.py:605-631` unchanged); "rating or review" 4/10 structurally. |

## P0 — shipped fixes

1. **Fetch-filter gaps closed** (highest-yield class). Two leak paths
   verified: (a) all four `exclude_title_patterns` required the "… in tesla"
   form, so noun-first 13F spam sailed through — **Ep566 cold-opened the
   episode on "Deutsche Bank Boosts Tesla Stake by $623M"** and Ep569 spoke
   "Defender Capital LLC purchased 4,143 shares" on air; (b) **X posts
   bypassed the filter entirely** — `drop_excluded_titles` ran only on the
   RSS and web-search routes, and the X merge happened after both. Shipped:
   three new patterns (noun-first stake moves, "N shares of tesla",
   aggregator "consensus recommendation" spam — named-analyst calls with
   anchors deliberately still pass) + the filter applied at the X-merge
   site. Guards: `TestFetchFilterWiden`.
2. **Ep565-class chapter mislabel closed.** The bare `First Principles`
   marker fired on 1 of 26 episodes — and that hit was a casual mid-news
   mention at 186s opening a **417-second chapter mislabeling the entire
   news body** (the prompt forbids announcing the section, so the marker's
   only firing mode was a false positive). Removed; digest-driven headline
   titles cover the body. Also removed the verbatim-banned "keep an eye on"
   from the teaser marker alternates. Guards: `TestChapterMarkerHygiene`.
3. **`tesla-narrative.html` shipped an empty `<title></title>`** — the
   template's `{% block title %}` is dead markup (base.html.j2 renders a
   `page_title` VARIABLE) and the bespoke Tesla generator never passed it.
   Fixed + page regenerated. Guard: `test_narrative_page_carries_title`.
4. **`podcast.ru.rss` untranslated words in the channel description**
   ("buzzing", "bearish", "recap") — fixed in `channel_i18n.json` (the
   nightly rebuild source) and patched in the live XML.

## P1 — open (not re-filed; escalated or carried)

- **Teaser successor tic**: "Before we go, the next … should/could clarify …"
  now 10/10 (opener mandated for chapter keying) with 6/10 on "clarify" and
  3 of 5 recent teasers teasing the same story. A/B-gated de-seed proposed
  (keep the "Before we go" chapter anchor, ban the "clarify" reveal shape,
  require a different story than yesterday's teaser). Successor-tic
  prediction logged.
- **LENGTH — OPERATOR DECISION (4th consecutive 10/10-below window).**
  Podcast-side levers stay banned. The digest substrate itself missed its
  own floor 3/10 (1298–1543 vs `min_digest_words: 1600`). Options: (a) raise
  digest substrate (full-text fetch of top stories), (b) accept ~1250–1700
  and lower `min_podcast_words` + fix the "15 focused minutes" RSS copy
  (published durations run 8:56–12:17). No prediction filed until chosen.
- **Repetition**: the Fort Bend solar story ran in 5 of 10 episodes and
  4 times within Ep573 alone (`lookback_days: 2` + 0.72 threshold misses
  multi-day recurrence). Recommend a named-entity recurrence memory
  (data-side, like DP Pod's lever memory) rather than threshold tuning.
- **"Implication" filler**: 89 content-free "The move/This change …"
  paragraph openers across 10 episodes (Ep573: 20/110 = 18%) against an
  existing unenforced prompt ban. Deterministic detection is feasible
  (metric exists); enforcement is prompt-side → A/B.
- **Narrative tracker curation ~85 days stale** (auto-freshness works;
  `last_major_update` newest is Ep482/May 20; 6 programs never curated;
  status text contradicts on-air facts — "v12 → v13 → v14 series" vs Ep567's
  v14.1 Lite). Operator task: `scripts/update_tesla_narrative.py`.

## P2 — growth

- **Tesla RU is unfunneled.** 19,353 RU Short views resolve to the English
  `tesla.html` with no capture path — the exact shape the RU SpaceX pilot was
  built for. Recommend: add `funnel:` block + RU lander (reuse
  `generate_ru_landing_page`), pending the pilot's own click-through read.
- Weekend closer speaks Friday's close three days running with no "Friday's
  close" qualifier (hooks/tesla.py `_price_sentence`) — small A/B-gated fix.

## Not findings (do not chase)

Whisper ASR noise ("Gigatexus", "i'm patrick and vancouver"); the comma-number
formatter is holding (verified Ep566's $9,603,163 rendering); `tag_leaks: 0`.
