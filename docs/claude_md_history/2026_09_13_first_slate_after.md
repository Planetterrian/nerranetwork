# Sep 13 2026 — first slate after both Sep 12 passes

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 13 2026 — first slate after both Sep 12 passes** (readout:
[`docs/reviews/youtube_review_2026_09_13.md`](docs/reviews/youtube_review_2026_09_13.md);
guards `tests/test_youtube_pass_2026_09_13.py`). All 12 episodes
published, 34 videos; the render-speed TRIAL is live —
`NERRA_X264_PRESET` defaults to `faster` in run-show.yml (repo variable
overrides; `medium` ends it; dubs stay on medium as the control),
register `x264-preset-faster-2026-09-13`, decision 09-20 on
`long_form_render_median_s_7d` vs 1,024 s. Three things the slate
exposed: (1) **`wall_duration_s` double-counted the render** since
09-11 (`long_form_render_duration_s` is recorded INSIDE
`youtube_publish_duration_s`; MAB read 3,257 s on a 2,225 s step) —
`engine.metrics._NESTED_DURATION_COUNTERS`; add a counter there when it
is nested. (2) **The finalize job spent 38 of 39 minutes re-downloading
10,642 gallery sidecars after EVERY episode** — `build_gallery_manifest`
is now incremental (the committed manifest is the sidecar cache; only
absent keys are fetched, vanished keys drop out) and parallel, the
nightly/standalone runs are `--full`, and a failed walk keeps the
committed manifest instead of writing an empty one. (3) **The price
line opened two SpaceX dub Shorts** — `is_price_line` was English-only
while the dubs pick windows on the RU/FR transcript; it now carries the
RU/FR close verbs and the split "dollars et cents" / bare "рост на n%"
shapes. Also on the record: combined generation engaged on ONE of 12
shows (M&A; PART 2 under-length, fell back) because the chained
flagships, the grok-4.6 script-stage shows and the RU shows are all
excluded by the pass's own rules — with the rewrite gate gone, Tesla /
FF / PT / SpaceX scripts copy 50-61% of the digest again (operator
decision, A/B-listen either way); and strip mode removed only
UNREACHABLE-source sentences (PT lost its lede), never a fabrication —
read `source_integrity_stripped_sentences` weekly.
