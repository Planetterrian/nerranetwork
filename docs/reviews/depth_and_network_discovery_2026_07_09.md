# Depth + Network Discovery Pass (July 9, 2026)

Operator report: news-show podcasts felt light on details (high-level
summaries), and show advertising should expand beyond sibling plugs to the
website, blogs, summaries, royalty-free gallery, and other network surfaces.

Drift guards: `tests/test_depth_and_network_discovery_2026_07_09.py`.

## Diagnosis — thin news coverage

Root cause is structural (confirmed across Tesla / FF / SpaceX / M&A reviews):

1. **Digest ceiling** — `{news_section}` is title + RSS/web-search snippet
   (1–3 sentences), not full article text. No full-text scrape exists.
2. **Podcast tracks digest ~1:1** — prompts ban invention and padding, so the
   script cannot outrun a thin brief.
3. **`digest_expand_below_target` was off** for all news shows (only First
   Principles + DP Pod had it). Podcast expand fired but plateaued.
4. **Show memory is continuity, not facts** — `{narrative_memory_section}` /
   Tesla narrative blocks add 1–2 arc sentences; they do not invent reporting.

## Shipped — depth (pilots)

### Digest-stage expand on four flagship news shows
| Show | `min_digest_words` | Notes |
|------|-------------------|-------|
| Tesla | 1600 | Deepens Top-12 + First Principles essay |
| Fascinating Frontiers | 1400 | Deepens Top-15 + Cosmic Deep Dive |
| SpaceX | 1200 | Deepens Top News + Engineering Deep Dive floor |
| Models & Agents | 1300 | Deepens Model Updates + memory continuity |

News-flavor `_build_digest_expansion_retry_prompt` now explicitly:
- prefers fewer items at full depth over many thin summaries,
- forbids inventing facts not in source text,
- lengthens licensed deep-dive / first-principles sections first,
- weaves memory continuity when a tracked program is touched.

### Prompt depth-over-breadth blocks
Each pilot digest prompt gained a **DEPTH OVER BREADTH** instruction.
SpaceX Engineering Deep Dive + FF Cosmic Deep Dive gained explicit word /
spoken-length floors (licensed-knowledge levers — A/B-listen).

⚠️ **A/B-listen required** for the next Tesla / FF / SpaceX / M&A episodes
(landmine #17). Revert per-show YAML `digest_expand_below_target: false` if
quality dips or cost spikes.

## Shipped — network discovery advertising

### Spoken outro (`engine/network_promo.py`)
- Added **First Principles Daily** + **The Do Positive Pod** to `ENGLISH_SHOWS`
  (appended — prior sibling rotations stay stable).
- Added **`NETWORK_SURFACES`** rotation: gallery (CC BY-SA), blogs/transcripts,
  summaries, story trackers, data hub, start-here, Age of AI apply, DP club.
- Every English closing now plugs one sibling **and** one surface sentence.
- Spoken copy avoids chapter-marker landmines (`under the hood`, `next time`).

### X reply (`run_show.py:_build_cross_promo_reply`)
- **Even days:** sibling show (legacy).
- **Odd days:** website surface with `utm_campaign=network_discovery`.

### YouTube descriptions (`engine/video_metadata.py`)
- Rotating discovery line after the subscribe CTA (metadata-only).

### Newsletter footer (`engine/newsletter_template.py`)
- Secondary links: gallery, data hub / story trackers, start-here.

## Not done (deferred)

| Item | Why |
|------|-----|
| Full-article fetch / scrape into `{news_section}` | Highest-leverage substrate fix; larger engineering + legal/ToS review |
| Digest expand on remaining news shows (OV, PT, MIT, EI, MAB, FP) | Pilot first; expand after A/B |
| Generalize DP Pod `FRESH ON THE NETWORK` to all shows | Needs shared hook + prompt A/B |
| Age of AI in spoken sibling rotation | Interview show, not a daily briefing — promoted via surface apply CTA only |

## Operator follow-ups

1. A/B-listen the first post-merge episodes of Tesla, FF, SpaceX, M&A.
2. Watch digest word counts + `digest_expand` cost in credit_usage JSONs.
3. If gallery / apply CTAs convert, consider a homepage rail (site-only).
4. Schedule full-text enrichment design when ready (fetcher + news_section).
