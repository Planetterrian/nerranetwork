# Multi-platform Shorts distribution (Instagram Reels / TikTok, May 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Multi-platform Shorts distribution (Instagram Reels / TikTok, May 2026)

Opt-in per show (`youtube.multi_platform_enabled`, default false → no-op). When
on, each published Short also gets: a **safe-zone variant MP4** (drops the
bottom URL pill + end-card and lifts captions via
`build_short_video(drop_url_pill=, caption_margin_v=)` so overlays clear the
IG/TikTok UI bands), a **`.social.json` sidecar** with per-platform
caption/hashtags (`engine/social_metadata.py`), optional **R2 hosting**
(`social_r2_prefix`; needed for IG's URL-based API), and best-effort
**auto-posting** (`engine/social_publisher.py` — IG Graph + TikTok Content
Posting; a clean no-op until `IG_ACCESS_TOKEN`/`IG_USER_ID` /
`TIKTOK_ACCESS_TOKEN` are set, and requires the operator's developer-app
approval). Orchestrated by `engine/social_distribution.py`, called once per
Short from `run_show.py`'s YouTube stage (additive, non-fatal). YouTube uploads
use the original Short, unchanged. Full setup + limitations:
[`docs/social_distribution.md`](docs/social_distribution.md). Drift guards:
`tests/test_social_distribution.py`.
