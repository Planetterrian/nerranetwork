# spacex — quality review (2026-08-15)

_Operator-directed flagship pass (Tesla + SpaceX together) run in a Claude Code
session — implement mode. Window Ep061–Ep070._

## Evidence

Snapshot: 6/10 below `min_podcast_words: 1300` (Ep61 863w). OP3 **609/7d,
1920/30d, weekly [259, 497, 504, 609] — the network's growth story**, at
$0.41/ep ($0.0046/download). RU Shorts: 380 views/video across 93 Shorts
(35,360 views), short_vpd 60.2 — the single hottest surface in the network.
`listener_value_overall` 6.5–8.6.

## Scoring prior predictions (2026-08-12 entry)

| Metric | Verdict | Evidence |
|---|---|---|
| `Title:` / bare-headline chapters | **miss → root-caused + shipped** | Sanitizer was never implemented (4th review); Ep58/60 junk still live in the public feed — AND the guard I added found four MORE polluted archive files no review had seen (Ep34/39/44/49). Root cause finally identified: the digest FORMATTING template's literal `**Title: Source Name**` line, reproduced verbatim by the model on Ep55/57/58/60/66/68/70 — the chapters were a downstream copy and every review scored the wrong surface. |
| "from an engineering standpoint" ≤6/10 | **miss** | 10/10, fifth consecutive review, zero movement; anchor-rotation prompt never applied. ESCALATED — not re-filed (two identical misses). |
| Market Watch fires on widened forms | **miss → shipped** | Widen never landed and the July transition de-seed made it WORSE: the model rotated to "quick note on the markets … closing at" (Ep68) and "quick look at the tape shows S P C X at" (Ep70), which the old pattern never knew — both shipped with no Market Watch chapter. Pattern widened; Closing-first ordering preserved. |
| xAI entity mis-attribution | **partial** | 0 clear mis-attrs in Ep61–70; entity-discipline prompt still unshipped (regression guard only). |

## P0 — root cause + shipped fixes

**The `Title:` class is a digest-generation bug, not a chapters bug.**
On Ep70 the model took BOTH halves of the placeholder literally and shipped
**every Top News headline as its publisher name** ("1. **Title:
ScienceBlog.com**" … ×8) — on the blog, summaries page, newsletter, and as
the podcast's substrate, which also drove Ep70's first non-zero
`spoken_url_count` (6 aggregator/domain attributions spoken on air,
including "according to Google News"). Defense in depth shipped:

1. Digest prompts (`spacex_digest.txt`, `dp_pod_digest.txt` — DP Pod leaks
   the same class): literal placeholder replaced with a bracketed
   instruction naming both observed failure modes. **A/B-flagged** (changes
   generated digests). This is the only layer that can fix the
   publisher-as-headline mutation.
2. `engine/newsletter_sanitizer.py`: scrub rule strips a leading `Title:`
   from bold headings in the canonical digest scrub (run_show.py:2020) —
   heals blog/RSS/summaries/newsletter/podcast substrate at once.
3. `engine/chapters.py` `_strip_title_label` in all three title helpers;
   `engine/grok_imagine.py` headline extractor strips it too.
4. Committed chapter files cleaned in place (titles only, URLs unchanged):
   Ep58 (7), Ep60 (3), Ep34/39/44/49 (18 more).
5. `scripts/review_snapshot.py` gained a **"Digest heading integrity"**
   section (catches the label leak AND the publisher mutation) — the
   tooling blind spot that let this survive four reviews. Also fixed the
   digit-blind tokenizer that produced Tesla's phantom closer tic.

**Market Watch pattern widened** (see scoring table). Guards:
`TestTitleLabelSanitation`, `TestMarketWatchPatternWiden`.

**Dub-title brand garbles** — shipped titles on @NerraRU/@NerraFR read
"Grog 4.6", «Спейс-Экс», "Cloud Fable 5", "Global Star". Deterministic
`restore_brand_names` now runs inside `translate_metadata` (finite verified
set, same class as `fix_phonetic_garbles`). Guard: `TestBrandNameRestore`.

**`spacex_podcast.ru.rss` channel title was untranslated English** ("SpaceX
Daily" while fr/zh/es siblings were localized — on the RU pilot's own feed).
Fixed in `channel_i18n.json` + live XML ("SpaceX Ежедневно").

## P1 — escalations (operator decisions; not re-filed)

- **Engineering-anchor tic** (10/10, 5 reviews): the prompt REQUIRES one of
  two phrases and the model always elects the first. The chapter pattern
  already accepts 4 variants, so a rotation-set de-seed costs no chapter
  coverage — but `tests/test_spacex_show.py` pins the current prompt string
  and two identical proposals have missed. Decision: ship the rotation
  de-seed (A/B) or accept the phrase as a brand anchor and close the item.
- **SPCX price spoken twice** (6/10 episodes, ~30s apart; 10th review; the
  pattern is structural — hook's closing always appends a price, digest's
  Market Watch supplies another). Decision: Market Watch qualitative +
  single quote in `closing_block` (coupled A/B), or accept as brand.
- **Length** (6/10 below 1300; Ep61 863w) — digest-substrate only, carried.
- **Deep-dive specials**: Ep59 shipped 1775w vs its own 2400 floor, and the
  earnings special was the worst RU performer in its neighbourhood by three
  orders of magnitude (3 RU views vs 2,469 on Ep060) — partly because 9
  uploads landed the same day. The pre-staged `flight-14-catch-reaction`
  special is time-critical (Ep70 reports a catch attempt this month);
  when forcing it, don't stack it on the daily's publish day.

## P2 — growth

- SpaceX momentum is real and RU Shorts are the engine. The funnel behind
  them is now instrumented end-to-end (see the network-surfaces notes in the
  PR body): show-page description links are funnel-tagged as of this pass.
- `api/shorts_ab.json` still reports "collecting" for an experiment the
  operator ended 2026-08-14 — the report builder should mark it ended
  (recommended, not shipped).
