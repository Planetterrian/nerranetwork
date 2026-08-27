# Nerra Daily — quality review, 2026-08-25

First review pass on the combined daily edition (launched 2026-08-21;
four episodes shipped at review time). Nerra Daily is a **virtual show**
(registry-only, assembled by `scripts/build_daily_edition.py` +
`engine/daily_edition.py`, never `run_show.py`), so this pass adapts the
playbook: there are no Whisper transcripts of the edition itself — the
committed rundown `.md` files, chapters JSONs, credit files, and a
re-execution of the promo-cut detector against all 44 real segment
transcripts served as ears.

## Verdict up front

The core product works. Promo-cut detection hit **44/44 segments across
all four editions, every one `kind=promo`** (re-verified against the
committed transcripts with the shipped code — `find_promo_cut` never
fell back to the weaker `network_mention`/`disclosure` evidence and
never shipped a plug). Chapters are exact, the RSS validates
(OP3-prefixed enclosures, `podcast:chapters`, `podcast:funding`,
live R2 audio answers 200), blog links all resolve, cost is on-design
(~$0.073/episode measured across eps 1–4), and the fallback/honest-SKIP
safety shapes are sound. What was broken was the **surfaces around the
audio**: the blog titles, and every measurement loop.

## P1 — shipped this pass

### 1. Every blog post titled itself with the byline

`blog/nerra_daily/ep00*.html` all carried
`<title>`/`<h1>`/`og:title`/JSON-LD name of **"Hosted by Mira · Episode
N · every English show the Nerra…"** — near-identical junk across all
four posts (the June-2026 "identical titles kill per-episode SEO" bug in
a new costume). Chain: the rundown `.md` has no hook line →
`engine/blog.py`'s hook fallback elected the *italic byline* (full-line
italics weren't skipped) → the H1 ("Nerra Daily — Monday, August 24,
2026") starts with the show name, so the June-2026 normalization
replaced the title with that "hook".

Fixed threefold (`engine/daily_edition.py:build_digest_md`,
`engine/blog.py:extract_blog_metadata`, plus backfill):

- the rundown now emits the canonical `> **<Weekday> edition — <lead
  hook>**` blockquote (the PR #292 shape `_HOOK_PATTERNS` match), via a
  shared `edition_hook()` used by both the title and the digest;
- the blog hook fallback skips full-line-italic bylines (defense, all
  shows);
- the four committed rundowns were backfilled and the blog/show pages
  regenerated — titles now read "Monday edition — Proprietary alloys
  and a dedicated gas trader…", distinct per day.

Guards: `TestBlogSurface` in `tests/test_daily_edition.py`.

### 2. The edition was invisible to every measurement loop

Three independent gaps, one cause — every loop derives its show list
from the `shows/*.yaml` glob, and Nerra Daily deliberately has no YAML:

- **OP3**: `api/op3_stats.json` had no `nerra_daily` entry, so the
  flagship growth question ("does anyone listen to the edition?") was
  unanswerable — a show with no listeners looked exactly like one never
  measured (the July-2026 language-feeds hole, again).
  `scripts/fetch_op3_stats.py` now resolves registry-only virtual shows
  from `shows/network_meta.yaml` (`_virtual_show_targets`); nerra_daily
  episodes also become eligible for the popular-episodes rail.
- **Costs**: the dashboard cost rollup missed
  `digests/nerra_daily/credit_usage_*.json` entirely.
  `generate_dashboard.aggregate_costs` gained `_VIRTUAL_COST_SLUGS`;
  measured 30d spend now includes the edition ($0.29/4 eps).
- **Build observability**: the edition committed NO record of what each
  splice did. A trim silently failing, a fallback-links day, or an
  expected show missing the window looked identical to a healthy day —
  and Mira's handoffs (the only new spoken content) were committed
  NOWHERE, so no future review could run the tic detector on them.
  The build now writes `metrics_ep*.json` (per-segment `cut_kind`/
  `cut_final_seconds`, `segments_shipped_whole`, `missing_expected`,
  `segments_dropped`, `links_source`, `field_note_included`) and the
  rundown `.md` now commits each handoff under its show's section —
  which also turns the previously link-list-only blog post into ~400
  words of unique daily prose.

Guards: `TestVirtualShowTargets` (`tests/test_op3_stats.py`),
`TestVirtualShowCosts` (`tests/test_dashboard_growth.py`),
`TestEditionMetrics` (`tests/test_daily_edition.py`).

### 3. No cross-day memory (rotation-memory class)

- All four intros open **"Good morning."** (4/4) — the model never sees
  yesterday's opening, and instruction-only variety asks are a proven
  failure (dp_pod violated one six days straight).
- Nothing stops the field note from re-finding a recent item: the find
  prompt excludes only the *day's lineup*, never Mira's own recent
  notes.

Fixed data-side (the DP Pod lever-memory pattern):
`recent_intro_openers()` / `recent_field_note_topics()` parse the last
10 committed rundowns into do-not-repeat blocks injected via new
`{recent_openers}` / `{recent_field_notes}` placeholders. **Both prompt
files changed → A/B-listen required (landmine #17).** Guards:
`TestRotationMemory`.

### 4. Monday edition shipped without a show that published that day

2026-08-24: Offshore North published Ep2 at **17:04 UTC** (its slot is
10:01 — GitHub cron lateness; the Cloudflare dispatcher should have
fired it on time, worth checking why it didn't). The edition force-built
at **15:07** (past the 14:00 force hour), so the Monday edition shipped
without Offshore North, and the idempotency key means no catch-up. The
miss was a single `logger.warning` — now a `::warning::` annotation
plus a `missing_expected` field in the committed metrics, so the
dashboard/operator can count how often this happens before deciding
whether the Monday force hour needs to move. **Deliberately NOT
changed:** the force hour itself (a later hour delays every listener
for a straggler; that trade is the operator's).

## P2 — noted, not fixed

- **Sign-off convergence watch**: 3/4 sign-offs reach for "thread /
  through-line" framing; 2/3 field notes end on an "It is a/the kind
  of…" reflection. n=4 is too small to de-seed — logged as a ledger
  prediction to score next pass.
- **`podcast:person` absent** from the feed channel (Mira is not tagged
  as host); funding + chapters tags are present. Cosmetic.
- **Content lake / site search**: rundowns and field notes are not in
  the lake (`backfill_content_lake.py` also walks `shows/*.yaml`).
  Field notes are unique content findable only in blog posts. Cheap to
  add via the same registry mechanism if the operator wants edition
  content searchable.
- **Card cosmetics**: blog cards show hook == title twice (pre-existing
  network-wide behavior for hook-titled shows, not edition-specific).
- **UC + FPD skipped 2026-08-24 entirely** (no summaries entries) —
  outside this review's scope but worth a scheduler-forensics glance;
  the edition adapted correctly.
- **experiments register**: the launch had no entry; added
  `nerra-daily-launch` (readout 2026-09-22, kill-bar criteria include
  the Apple/Spotify submission still on the operator checklist).

## Operator items

1. **A/B-listen** the first post-merge edition: intro opening variety
   and field-note behavior are the two prompt-affected beats.
2. Submit `nerra_daily_podcast.rss` to Apple/Spotify if not yet done
   (`apple_podcasts_url`/`spotify_url` are still null in
   `network_meta.yaml`) — the launch experiment's readout is
   meaningless without distribution.
3. Check why the Cloudflare dispatcher didn't fire offshore_north at
   10:01 on 2026-08-24 (published 17:04 via the late GitHub cron).
4. OP3 will index the feed on its own; if `nerra_daily` still shows no
   entry weeks after nightly runs with the fixed fetcher, check the
   OP3 prefix first (the dp_pod/age_of_ai 404 lesson).
