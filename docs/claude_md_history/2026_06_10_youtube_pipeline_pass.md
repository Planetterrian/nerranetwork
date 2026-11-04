# YouTube pipeline pass (June 10, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### YouTube pipeline pass (June 10, 2026)

Full video-pipeline review — writeup:
[`docs/youtube_review_2026_06_10.md`](docs/youtube_review_2026_06_10.md);
drift guards: `tests/test_youtube_quality_pass.py`. Headline: the
**silent config-drop class** — `_build_nested` discarded YAML keys the
dataclass didn't declare (now warns loudly + CI guard). Casualties fixed:
`shorts_min_score_threshold` (Tesla's 3.5 never applied anywhere — the
smart Shorts selector fell back to the voice start almost daily; the
single-Short path additionally never passed a threshold at all),
five NewsletterConfig fields (`requires_financial_disclaimer` was
ALWAYS False on the dataclass path), and `_defaults.yaml`'s network-wide
`min_audio_duration: 180` (dead inside the `audio:` block; now
top-level). Viewer-facing: long-form slideshow scenes now CYCLE (≤25 s
per image hold vs 168 s on Ep505) at zero added Grok-Imagine cost;
`channel: ru` without `YOUTUBE_REFRESH_TOKEN_RU` warns loudly;
`shorts_captions_path` metric records ASS vs SRT-fallback. Rejected with
reasons in the doc: bitrate floor, more images, `-preset slow`.
