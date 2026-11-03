# Sep 17 2026 — a partial analytics fetch is not a snapshot

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 17 2026 — a partial analytics fetch is not a snapshot** (readout:
[`docs/reviews/youtube_review_2026_09_17.md`](docs/reviews/youtube_review_2026_09_17.md);
guards `tests/test_youtube_pass_2026_09_17.py`). The 09-16 nightly got
HTTP 500 from the Analytics API on 13 video batches and the day series
on every channel; each failure was swallowed as an empty result, the
step "succeeded", and a file with 927 of 2,753 videos and NO day series
overwrote the healthy one — the policy read `video_count_14d: 0`
everywhere, the scorecard read zero views, and `channel_views_wow_en`
went null while the dashboard's freshness alert stayed quiet (the file
was fresh). `fetch_youtube_analytics.py` now retries 5xx (never 403),
records failed queries as `payload["degraded"]`, and **refuses to
overwrite a clean file** (`snapshot_regression`: failed queries, under
60% of the committed videos, or a lost day series → `::error::` and the
file stays); `track_early_reach.py` skips a degraded snapshot. Same
pass: the x264 `faster` trial measured **no effect** (30 renders, median
932 s vs 1,024 — the filter graph is the cost) and is closed;
`combined_script_matches_digest` accepts a digest whose lines are all
in the stash (run_show's trims only remove lines — M&A discarded its
combined script every day at 0.3-0.5 forward share) and the discard
warning logs both shares. Reading rule from the early-reach card: the
**second EN Short (`qualified`) earns a median 4 views at age 3 against
31 for the hook Short** — read it at age 7 before cutting it, and never
read a week whose snapshot was refused.
