# Sep 9 2026 — two numbers that lied, one each way

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 9 2026 — two numbers that lied, one each way.** (1) The Data
API `channels().list statistics.viewCount` stopped tracking Shorts
views on 2026-09-02 on all three channels (@NerraRU +19/day against
~4,000 Analytics views/day); the `detect_view_cliffs` alarm differenced
that counter and paged CHANNEL VIEW CLIFF for four nights while every
channel was UP (EN +56% WoW). **The Analytics `day_series` is the only
view-flow source for alarms and scorecards; `total_views` in
`api/youtube_channel_history.json` is a lower bound**
(`detect_counter_divergence` says so nightly). (2) A new metric set on
the publish result is NOT a metric until it is on the allowlist in
`engine.pipeline.record_youtube_outcomes` — `grok_image_px_max`
shipped 09-03 and recorded nothing for six days. 2K is confirmed from
the sidecars: 2816x1584 since 09-03.
