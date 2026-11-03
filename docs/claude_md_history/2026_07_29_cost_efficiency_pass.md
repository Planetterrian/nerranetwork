# Cost-efficiency pass (July 29 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Cost-efficiency pass (July 29 2026)

Six changes that cut spend without touching what a listener gets. The
rule for the whole pass was **measure first** — every item below was
justified from committed data, not from reasoning about where waste
"should" be. Drift guards: `tests/test_cost_efficiency_pass.py`.

Context: the dashboard's tracked figure (~$29/30d) was roughly a third of
real spend. Adding the pieces it did not count — multilingual (~$38/mo)
and Grok Imagine (~$50-60/mo, only counted since July 28) — the true
total is ~$110-125/mo. The two largest lines were the two least measured,
which is why measurement leads this list.

- **Per-language OP3 measurement.** Multilingual is ~1/3 of spend and its
  audience was measured NOWHERE: the per-language enclosures carry the
  OP3 prefix, but `fetch_op3_stats.py` only ever resolved each show's
  English feed, so `api/op3_stats.json` had zero language-track entries
  and a language with no listeners looked exactly like a popular one.
  The fetcher now also resolves the 14 feeds the network actually pays to
  produce (scoped to each show's `multilingual.languages`, not the 44
  feed files on disk) into a separate `language_feeds` section — separate
  because every consumer iterates `shows` keyed by slug. The dashboard
  gains `multilingual.by_language` (downloads vs approximate cost) and
  per-show `audience_by_language`. **This is a decision instrument, not a
  saving:** after 2-4 weeks, a language reading zero across several weeks
  is a candidate to switch off in the show YAML. Today's split is FR
  ~$20/mo (7 shows), RU ~$13/mo (4), ZH ~$8/mo (3); RU feeds @NerraRU and
  earns its keep regardless, ZH has no channel and no directory listing.
- **16:9 scene generation follows the render.** Shorts-only policy days
  still generated 4 fresh 16:9 Grok Imagine scenes, but those feed only
  the long-form slideshow, its thumbnail, and the gallery — Shorts use
  their own 9:16 set. On a shorts-only day for a show with no
  video-podcast feed, three of four paid images were never seen. Now 1
  (thumbnail base + gallery contribution); the 9:16 set is untouched, and
  `video_podcast.enabled` shows still get all four because they render
  long-form regardless of tier. ~$0.06/episode on tier-C shows.
- **xAI search-tool spend is counted.** Server-side `x_search` /
  `web_search` bill per SOURCE consulted; the Responses path returned
  only text, so every search-fetching show under-reported its spend
  (flagged as uncounted by the July 24 pass, still missing after the July
  28 cost fix). `digests/xai_grok.py` accumulates usage per process — the
  fetch layer has no tracker reference — and run_show drains it into the
  episode's credit file via `engine.tracking.record_search_usage`. Rate
  is `SEARCH_COST_PER_SOURCE` ($0.025), env-overridable with
  `XAI_SEARCH_COST_PER_SOURCE`. Also wired `record_render_seconds`, which
  the July 28 pass shipped with no caller.
- **Single-pass long-form render is now the default** (was opt-in behind
  a repo variable). A/B on both production shapes at 1920x1080: uniform
  stills 24.6s -> 16.2s (-34%), chapter-schedule + burned-in captions
  22.3s -> 17.2s (-23%), with outputs equivalent — identical duration,
  frame count, geometry and codecs, mean pixel difference < 0.3/255 at
  every sampled timestamp, identical scene timeline, matching brand pill
  / URL pill / caption rendering. `NERRA_SINGLE_PASS_RENDER=0` forces the
  legacy path, which also remains the automatic fallback on any fused-
  command failure. The escape hatch now covers the RU/FR dub renders too.
  Render-only, no audio — outside landmine #17.
- **The podcast-side expansion retry is off** wherever a digest-side
  lever exists (11 shows). See the superseded note in the June 2026
  network-pass section above for the measurement. **A/B-listen the first
  post-merge episode on a show that used to fire it** — when the retry
  fired, its output was what shipped.
- **`CLAUDE.md` trimmed ~185 KB -> ~124 KB** by moving the dated per-show
  quality-pass narratives verbatim to
  [`docs/show_review_history.md`](docs/show_review_history.md), keeping
  each show's structural facts plus a new "Live constraints" block for
  the rules that still bind (Colossus/Anthropic is real, length is
  digest-side only, de-seed by shape, the grok-4.3 plateau, MIT not
  live-trading ready). This file is loaded in full at the start of every
  Claude Code session and replayed across the agentic loop, so its size
  is a per-session cost on all future work — the June 2026 token review
  found exactly this pattern was the network's largest Anthropic line
  item before the review agent moved to Grok.
