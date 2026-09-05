# Flagship shows — quality review (2026-09-04)

_Operator-directed pass over the three shows that carry over half the
network's audience — SpaceX Daily (2,825 downloads/30d), Models & Agents
(991) and Tesla Shorts Time (810) — plus the shared pipeline and public
surfaces they depend on. Run in a Claude Code session, implement mode.
Windows: SpaceX Ep080–089, Tesla Ep584–593, M&A Ep153–162 (all
2026-08-25 → 09-03). Evidence gathered by four parallel read-only passes
(one per show, one cross-cutting) and verified against the working tree
before anything was changed._

## TL;DR

- **Models & Agents had been reviewed four times since Aug 2 with every
  proposal left unshipped** (`shipped: []` in each ledger entry). The
  "Everyone talks about…" deep-dive opener was 10/10 in the digests and
  9/10 on air because *both prompts supplied that sentence as an
  example*; three episodes shipped with no Under the Hood chapter; Ep161
  shipped a chapter titled `Training a Misaligned Reward Seeker:
  [@AnthropicAI](https`; and the review snapshot tool itself crashed on
  this show. All fixed, chapters for Ep143–162 rebuilt deterministically.
- **SpaceX's closing spoke a stale quote as live on 10/10 episodes.** The
  run lands ~07:30 UTC, before US pre-market, so `fast_info` always
  returns the prior close and the verb was chosen from the data source,
  not the clock. Saturday, Sunday and Monday aired Friday's move three
  days running; Ep080 said "down zero percent". Fixed in the hook.
- **Tesla spoke a false close on Ep585** ($351.73 "closed at" for a
  $345.82 close — an in-session retry) and its closer produced "one
  dollars", "one cents" and a comma-joined "up, ninety-two cents, zero
  point three percent" that Whisper heard as "up 92.3%". Fixed. Four
  more 13F-spam title shapes closed (one aired on Ep590).
- **Shared pipeline:** six memory shows' performance trackers were being
  written and discarded nightly (whitelist listed five literal paths);
  OP3-unindexed language feeds were reported as "0 downloads, measured"
  on the card the language cull reads from; every feed was serialized
  oldest-first; the dashboard's pipeline p50 was ~99 s for ~29-minute
  runs; every show page downloaded the whole 14 MB gallery manifest;
  blog plays were invisible to OP3; 656 regenerable intermediates (54 MB)
  were tracked. All fixed.
- **Not touched (escalated or A/B):** the length plateau on all three
  shows (operator decision, carried), SpaceX's mega-story retell (lever
  shipped Aug 26 and missed — escalated), M&A's 100-char title
  truncation, the Tesla same-URL cross-section double-telling
  (data-side design proposed), chapter anchoring landing mid-story
  (engine change proposed with replay tests), the multilingual
  workflow's wrong-show trigger.

## Scoring prior predictions

### SpaceX (2026-08-26 entry)

| Metric | Verdict | Evidence |
|---|---|---|
| chapters outside the known section set, next 10 | **hit** | 0/8 (Ep082–089); `known_sections_only: true` holds. Side effect noted: Introduction now spans 280–360 s on four episodes with no sub-navigation. |
| same-episode multi-section retell of one mega-story | **miss** (lever shipped) | Digest rule at `spacex_digest.txt:8` + podcast rule at `:48` both present; 6/8 episodes still retell across Top News / AI / Deep Dive (Ep083 Nvidia ×3, Ep085 Cursor ×4, Ep087 turbines ×4). Structural cause: Top News asks for 8–10 items while AI stories are routed into AI & Compute AND the podcast must cover both. Escalated — see deferred. |

Earlier escalated items, scored only: engineering-anchor monoculture 0/10
(rotation works); `Title:` heading leaks 0/10; SPCX dollar figure spoken
twice 0/10 (percent/direction still twice in 7/10, ~30 s apart); length
0/10 ≥ 1,500 words, 3/10 ≥ 1,300.

### Tesla (2026-08-15 entry)

| Metric | Verdict | Evidence |
|---|---|---|
| excluded-class 13F/fund items in digests, next 10 | **miss → shipped** | 3 in Ep584–593 (Ep590 X#5 Lynch 13F — spoken; Ep586 X#1 Ark position; Ep586 X#2 MarketBeat "Should You Buy?"); ≥4 more spam titles in the post-filter pool. Four uncovered title shapes (sub-million amounts, "shares of N Tesla", "N shares in Tesla … acquired by", "reveals … position on Tesla") plus the "Should you buy?" alert are now excluded (`shows/tesla.yaml`). |
| First Principles chapter mislabeling the news body | **hit** | 0/10 FP-titled chapters. The mislabel moved clothes: Ep584 4/7 wrong-story titles, FP essay absorbed into 116–160 s Introductions on 3 episodes (see deferred chapter-anchoring item). |
| successor teaser tic "should/could clarify" | **partial** | 2/10 (down from 6/10 with no lever shipped); successor shape "watch for (more details on how)…" 4/10 — below the ban threshold, watch. |

### Models & Agents (2026-08-11 entry)

| Metric | Verdict | Evidence |
|---|---|---|
| "Everyone talks/treats" UTH opener ≤2/10 | **miss → shipped** | 10/10 in digests, 9/10 spoken. Root cause was the *digest* prompt (`:144` literal example) plus the podcast prompt (`:152`); three reviews aimed at the podcast layer only. De-seeded by shape in both. |
| "Before we go" ≤4/10 | **miss** (by design) | 10/10 — the shipped prompt REQUIRES the phrase as the chapter anchor (same as Tesla/SpaceX). Closed as a brand anchor, not re-filed. |
| "keep an eye on" regression | **hit** | 0/10. |
| successor UTH-opener tic ≥6/10 | **hit** | none; companion seeds "In practice" 9/10 and "gotcha" 6/10 came from the same prompt lines and are de-seeded with them. |
| successor teaser-opener tic ≥6/10 | **hit** | max 3/10. |
| UTH chapter present when a deep dive exists ≥9/10 | **miss → shipped** | 6/10; marker alternate never shipped. Now "pop the hood" is REQUIRED in the deep dive's first sentence and the everyone-talks shapes are marker alternates; rebuilt chapters give 10/10. |
| spoken episode-number callbacks | **hit** | 0/10. |

## P0 — shipped

### Models & Agents

1. **Chapter title carried a raw markdown link** (Ep161 `chapters_ep161.json`:
   "Training a Misaligned Reward Seeker: [@AnthropicAI](https"). The
   digest headline's source tail was an X-profile link (22 digests carry
   this shape), the outlet-tail stripper only handled short plain names,
   and the clipper cut through the URL. `engine/grok_imagine.py` now
   flattens `[label](url)` before tail logic and rejects `#`-headed
   candidates (Ep148 shipped "# Models & Agents" as a chapter);
   `engine/chapters.py` flattens links and drops a lone `@handle` tail in
   every title helper. The M&A digest prompt's literal `**Title: Source
   Name**` placeholder (the SpaceX Aug-15 root cause, never ported here)
   is replaced with a bracketed instruction that also bans links/handles
   in headings. Ep161's committed chapters + blog post repaired.
2. **No Under the Hood chapter on Ep153/155/156** (and a 7-minute chapter
   mislabelled "Practical & Community" on 6/10): the podcast prompt
   offered "pop the hood" as one of two example openers and the model
   elected the other; the `open.source` marker alternate fired on the
   topic word "open-sourced" at 7–16 % of the script, which also cleared
   `min_chapters` and suppressed the digest-headline auto-segmentation.
   Fixed in `shows/models_agents.yaml` + prompt; chapters Ep143–162
   rebuilt from the on-disk scripts (timestamps reproduce the committed
   files exactly where titles were unchanged).
3. `scripts/review_snapshot.py` crashed (`UnboundLocalError`) on every
   show without `exclude_title_patterns` — the network's #2 show had no
   working snapshot. Fixed + guarded.

### SpaceX

4. **Closing verb** — `_price_sentence` chose "is trading at" whenever
   `fast_info` answered, but the run happens at ~03:30 New York, so that
   is always the prior close: 10/10 closings said "trading at";
   Ep084/085/086 aired Friday's $141.50 / +1 % as live on Sat, Sun and
   Mon. The verb now follows the market clock (`_market_is_open`); a
   zero move is "unchanged" (Ep080 said "down zero percent" from a
   `-0.0%` change string; rounding now precedes the sign).
5. **Market Watch chapter missing** when the tape line reads "finished
   the session higher" (Ep087) — pattern widened.
6. **Shorts cut from the stock line** — 5 of 68 EN Shorts since Ep060
   were titled "SPCX Trading at $141.50 Up 1%": the numeric-reveal scorer
   loves the quote sentence. `engine/shorts_selector.py` never opens a
   window on a price line (network-wide; Tesla's "closed at" line too).
7. **A two-year-old article as today's lead** — Ep088's "Falcon 9
   completes 23rd flight, new reuse record" (Ep089 then reported the 35th
   flight), Ep080's pre-IPO story ten weeks after listing. Google News
   search feeds re-surface old articles under fresh index dates.
   `engine/fetcher.py` now drops an article whose resolved publisher URL
   carries a `/YYYY/MM[/DD]/` path older than the fetch window
   (month-only paths resolve to the month's last day, so this can never
   false-positive on a recent month). Undated URLs (the accuweather case)
   still pass — see deferred.

### Tesla

8. **False close on Ep585** — the history source hard-coded REGULAR and
   read the in-progress bar during an 11:27 ET daily-audit retry. During
   the regular session with today's bar open the source now reports
   INTRADAY and the closer says "is trading at".
9. **Closer grammar** — "up, one dollars and thirty cents", "one cents",
   and the comma-joined amount/percent Whisper transcribed as "up 92.3%".
   Units singularise; the direction binds to the amount; "or" separates
   the percent.
10. **13F spam aired** (Ep590) — five more exclude patterns; guard replays
    the five leaked titles and three legitimate ones.
11. **Scaffold on the blog** — "Sign-off paragraph" (Ep590), the
    `@username` placeholder as a live link (Ep584), `Source/Post:` on
    8/10 posts, an unclosed ```claims fence rendered as `<pre>[]</pre>`
    (Ep585). Sanitizer rules + `extract_claims_block` accepts an unclosed
    trailing fence.

## P1 — shipped

- **M&A digests/blog carried the prompt's `### DEPTH OVER BREADTH (news
  items)` heading** (4/10 digests, 17 blog posts, as an `<h4>` + TOC
  entry). The prompt states it as a bracketed instruction now; the
  sanitizer scrubs any echo.
- **Fabricated continuity callbacks** — `engine/show_memory.py` supplied
  the quotable sentence "Remember, we covered [program] yesterday…" and
  M&A reproduced it verbatim in 8/10 episodes, each time naming a tracker
  *display name* ("Remember, we covered A I Compute and Inference
  yesterday") rather than real prior coverage. De-seeded by shape
  (shared by 8 memory shows — **A/B-listen**).
- **M&A closing pool** had two entries so one closing aired 7/10; now
  four (all match the Closing chapter marker — **A/B-listen**).
- **Tesla theme block** injected "reddit google", "insideevs google",
  "second quarter", "full self" (a fragment of "self driving") into every
  prompt — stopwords extended.
- **RSS item `<link>`** was the MP3 on the newest item and absent on
  every other (the re-add path never wrote it). Podcast apps render it as
  "episode website". New items link the episode's blog post; the link is
  preserved across rebuilds; a legacy MP3 link is not carried forward.
  Other `update_rss_feed` callers (Nerra Daily, Nerra Voices, recovery
  scripts) keep the legacy behaviour until they pass a page URL.
- **Feeds serialized oldest-first** — feedgen prepends by default, which
  inverted the newest-first loop; Tesla's first `<item>` was Ep343 from
  2025-12-03. `order="append"` at both call sites; guard asserts newest
  first.
- **Nightly whitelist** listed five literal `*_performance_tracker.json`
  paths; `scripts/update_performance_trackers.py` writes ten. MIT / DP
  Pod / Env Intel / Omni View / Age of AI / Offshore North trackers were
  discarded every night, so their "strong recent topics" prompt block
  could never fire. Now a glob.
- **Dashboard language card** turned OP3's "not indexed (404)" into
  `downloads 0, measured: true` for 6 of the 14 paid language feeds
  (every ZH feed + three FR) — the exact card the July-29 language-cull
  rule reads. Null now stays null, the rollup counts only measured shows
  and reports `unmeasured_shows`.
- **Pipeline p50 was a phantom** — `total_duration_s` summed the three
  `stage()` blocks only (spacex p50 99 s vs ~29 min real). `wall_duration_s`
  adds the timed counters; the dashboard prefers it.
- **Gallery manifest** (14.2 MB, 7,680 images) downloaded and parsed on
  every gallery-enabled show page. `build_gallery_manifest.py` now also
  writes `site/data/gallery/<slug>.json`; the embed fetches the show's
  slice and falls back to the full manifest; both committing workflows
  whitelist the new path.
- **Blog player unmeasured** — `<audio src>` was the bare R2 URL, so
  plays from the page search sends readers to never reached OP3. The
  blog now routes the network's own audio host through the OP3 prefix
  (already-prefixed and third-party URLs untouched).
- **656 regenerable intermediates tracked** (`*_square.jpg`,
  `*.social.json`, `*.chapters.ffmeta` under `youtube_tmp/`, 54 MB,
  growing ~1.6 MB / 4 days via `git add -A digests/`) — ignored and
  untracked (landmine #1 class).
- `Title:` labels backfilled out of 16 archived SpaceX digests + the
  summaries JSON (153 headings; the Aug-15 scrub was forward-only and the
  blog still rendered them). Blog regenerates nightly.
- SpaceX FAQ said "Every weekday" for a seven-day show; M&A page badge
  "~15 min" for a 7:38–11:14 show.

## Deferred / recommendations (not implemented)

**Operator decisions**

- Length plateau on all three shows (SpaceX 0/10 ≥ 1,500 w; Tesla 7/10
  < 1,400; M&A 9/10 < 1,500) — carried, escalated in every prior ledger.
  One observability gap worth closing first: the digest expansion retry
  fires on 9/10 Tesla, 9/10 SpaceX and 7/10 M&A episodes (one extra
  45–90 s LLM round trip each) and no metric records whether it reached
  the floor.
- SpaceX mega-story retell across sections (6/8 with the Aug-26 lever
  shipped): the prompt asks for 8–10 Top News items *and* routes AI
  stories into AI & Compute *and* makes the podcast cover both. The next
  attack should be data-side (a headline appearing in AI / Counterpoint /
  Deep Dive is excluded from Top News → one regeneration), not a third
  prompt rule.
- Two same-day double publishes in the window: M&A Ep155 + Ep156 (both
  2026-08-28, same Top Story, four near-duplicate YouTube uploads) and
  Tesla Ep586 + Ep587 (daily-audit midnight retry + scheduled run). The
  Aug-28 dispatch fix is documented in `run-show.yml:421-431`; whether to
  unpublish one of each pair is the operator's call (renumbering is unsafe
  — `get_next_episode_number` is pinned by the RSS max).
- Six language feeds OP3 will never index (ZH has no directory listing):
  submit them to Podcast Index or switch ZH off on tesla/spacex/FF and FR
  off on models_agents/first_principles/env_intel (~$28/mo unmeasurable).
- Stale ES/RU/ZH feeds for languages removed from the YAMLs
  (`podcast.es.rss`, `spacex_podcast.es.rss`, `models_agents_podcast.{ru,es,zh}.rss`,
  last items June 18) are still served.

**Engine / data-side (proposed, with the evidence to replay)**

- Chapter anchoring lands 1–3 sentences into the story (27 of 46 Tesla
  story chapters 8–25 s late; Ep584 four wrong-story titles): the
  podcast prompt mandates 1–2-sentence paragraphs, so the best-overlap
  paragraph is usually mid-story. Walk back to the first paragraph of
  the contiguous run sharing headline tokens; lower `min_segment_words`
  for one-sentence-paragraph shows; apply the hook exclusion in
  `_best_headline_for_segment`. Replay Ep584/589/592 as the guard.
- Tesla same-URL double-telling (8/10 digests: X Takeover / Short Spot
  items reuse Top-12 URLs, so Ep592 told five stories twice): drop any
  later-section item whose `Source:` URL already appears in Top 12,
  after digest generation (mirrors `dedup_read_more_sources`). Content
  removal → A/B one episode.
- Tesla Counterpoint chapter fires 2/10 because the marker keys on the
  prompt's two example transition phrases; anchor it on the Short Spot
  headline instead.
- Stale articles with undated URLs (the Ep088 accuweather case): read
  `article:published_time` from the resolved page at fetch time, or
  refuse "record / first / new high" claims below the narrative memory's
  last known figure.
- Required SpaceX anchors dropped (Counterpoint 2/10, Engineering 1/10,
  Teaser 1/10): a deterministic post-generation validator that locates the
  section by overlap and prepends the anchor, or one regeneration.
- Multilingual workflow resolves the wrong show on `workflow_run` (it
  parses `head_commit.message`, which is main's tip at trigger time, not
  the commit the run produced): translations ride the next show's
  completion (98 min on 09-03) and FF got three near-empty commits in a
  day. Use `git log --since=<run_started_at>` on a full checkout, or a
  `repository_dispatch` from the commit step.
- M&A 100-char title truncation on 10/10 RSS items (hooks run 93–163
  chars against the prompt's "under 120"): either tighten the hook spec
  (spoken cold open → A/B) or use the title bundle's optimized title for
  the feed (metadata-only). Decision needed on which surface owns it.
- `podcast:transcript` points at the raw Whisper JSON, which carries
  "Quinn" for Qwen, "Laura" for LoRA, "andthropic": post-correct the JSON
  with the garble map before publishing, or point at the reader text.
- RU/FR dub Short titles for `filled` windows are transcript fragments
  (8 of the last 10 Tesla entries; "cellules 8680" for 4680): translate
  the EN bundle title for the same window instead.

**Prompt-side (A/B-listen, not applied)**

- SpaceX: "A quick market note" still 3/10 despite the ban; the AI
  fallback sentence is seeded verbatim by the prompt's list (identical
  30-word sentence on Ep084/086); Counterpoint closer "Resolution would
  require…" 7/10 seeded by "what would resolve it"; zero-fact "No X was
  disclosed" padding (14 sentences in 3 episodes); Community Buzz as one
  paragraph overlapping Top News 8/10; entity naming for the xAI operator
  drifts across "xAI" / "SpaceXAI" / "Starshield AI" in one week.
- Tesla: the prompt still states four lengths (14–16 min, 10–13 min,
  ~1,400, 1,600–1,900); `**Title (One Line): Source Name**` placeholder
  at `tesla_digest.txt:118` drives five heading shapes in 10 digests;
  the story-outline preamble is being voiced (Ep584 six outline-then-
  expansion pairs); pure valuation items (Trefis / Motley Fool /
  Intellectia / MarketBeat alerts) ship as news — domain-level excludes
  are the operator's call.
- M&A: arXiv share hit 94 % on Ep162 (selection rebalance carried since
  July 2); Under the Hood asserts precise unsourced numbers (5/10) or
  duplicates a same-day item (5/10); 8 of 13 items on Ep159 had no
  Source line.
- Network: the AI reviewer flags idea-level repetition as "critical" on
  5/11 episodes; a data-side `script_digest_overlap_pct` (45–65 % on the
  worst episodes; blog posts then show the same sentence twice) would be
  the measurable version.

## Test results

Full suite: 7,314 passed / 12 skipped at HEAD before changes (the 69
non-passes in this sandbox were missing packages — yfinance, feedgen,
google-auth — and pass once installed). After the pass every touched
file's suite passes; new guards in `tests/test_flagship_pass_2026_09_04.py`,
`test_models_agents_quality_pass.py`, `test_spacex_show.py`,
`test_tesla_quality_pass.py`, `test_chapters.py`, `test_grok_imagine.py`,
`test_shorts_selector.py`, `test_publisher.py`, `test_newsletter_sanitizer.py`,
`test_show_memory.py`, `test_build_gallery_manifest.py`, `test_review_agent.py`.

## ⚠️ A/B-listen required (landmine #17)

Audio-affecting changes in this pass — listen to the first post-merge
episode on each show before trusting them:

- **Models & Agents:** digest + podcast prompt de-seed of the deep-dive
  opener; "pop the hood" now required in the deep dive's first sentence;
  two new closing variants; `DEPTH OVER BREADTH` no longer a heading
  (digest-side text); headline placeholder replaced (digest-side).
- **SpaceX:** closing sentence verb now follows the clock ("closed at" on
  every pre-market run; "unchanged on the session" on a flat day).
- **Tesla:** closer grammar ("one dollar", "…cents, or …percent"); "is
  trading at" on an in-session retry.
- **All memory shows (8):** continuity-callback shape guidance replaced
  the quotable example in `engine/show_memory.py`.

`GROK_API_KEY` was not set in this session, so no digest was regenerated
to show before/after output.
